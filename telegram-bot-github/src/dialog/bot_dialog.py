import logging  # Annotation: Imports the logging module for debug, info, warning, and error logging to monitor bot dialog interactions.
import json  # Annotation: Imports the json module to load configuration files (topics.json, locations.json) for category and location data.
import re  # Annotation: Imports the re module for regular expression validation of email and room number inputs.
import os  # Annotation: Imports the os module for file operations, such as checking and deleting temporary media files.
import asyncio  # Annotation: Imports the asyncio module for asynchronous operations, like downloading media files with timeout handling.
import unicodedata  # Annotation: Imports unicodedata for normalizing text inputs (e.g., case-insensitive "Kihagy" handling).
import csv  # Annotation: Imports the csv module to read authorized_emails.csv for email authentication.
from datetime import datetime  # Annotation: Imports datetime for timestamping logs and ticket submissions.
from threading import Lock  # Annotation: Imports Lock for thread-safe writing to /app/logs/abuse_attempts.txt.
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove  # Annotation: Imports Telegram API classes: Update for message handling, KeyboardButton for custom buttons (e.g., location/contact sharing), ReplyKeyboardMarkup for custom keyboards, and ReplyKeyboardRemove to clear keyboards.
from telegram.ext import ContextTypes, ConversationHandler  # Annotation: Imports ContextTypes for type hints in method signatures and ConversationHandler for managing multi-step conversation flows (referenced in it_ticket_bot.py).
from src.data.form_data import FormData  # Annotation: Imports FormData class from form_data.py to store and retrieve ticket data.
from src.services.email_service import EmailService  # Annotation: Imports EmailService class from email_service.py for sending ticket emails.
from src.states import States  # Annotation: Imports States enum from states.py to define conversation states (e.g., AUTH, CATEGORY).

# Configure logging for debugging and monitoring
logger = logging.getLogger(__name__)  # Annotation: Creates a logger instance for this module to log dialog-specific events.

# Thread-safe file lock for abuse logging
abuse_file_lock = Lock()  # Annotation: Initializes a Lock for thread-safe appending to /app/logs/abuse_attempts.txt in case of concurrent unauthorized access attempts.

class BotDialog:
    def __init__(self, form_data: FormData, email_service: EmailService, email_recipient: str):
        # Initialize dialog with dependencies and load configuration files
        self.form_data = form_data  # Annotation: Stores FormData instance (from it_ticket_bot.py) for ticket data storage.
        self.email_service = email_service  # Annotation: Stores EmailService instance (from it_ticket_bot.py) for sending emails.
        self.email_recipient = email_recipient  # Annotation: Stores the recipient email address for ticket submissions (from it_ticket_bot.py).
        try:
            with open('config/topics.json') as f:
                self.topics = json.load(f)  # Annotation: Loads topics.json (categories, components, issues, teams) into self.topics; raises exception if file is missing or invalid.
        except Exception as e:
            logger.error(f"Failed to load topics.json: {str(e)}")  # Annotation: Logs error if topics.json cannot be loaded.
            raise  # Annotation: Re-raises the exception to halt initialization.
        try:
            with open('config/locations.json') as f:
                self.locations = json.load(f)  # Annotation: Loads locations.json (campuses, departments, prompts, validation regex) into self.locations; raises exception if file is missing or invalid.
        except Exception as e:
            logger.error(f"Failed to load locations.json: {str(e)}")  # Annotation: Logs error if locations.json cannot be loaded.
            raise  # Annotation: Re-raises the exception to halt initialization.
        self.panic_option = "PANIC"  # Annotation: Defines the label for the emergency PANIC button.
        self.max_media_size = 20_000_000  # Annotation: Sets maximum media file size (20MB) for uploads in the media method.
        logger.debug(f"BotDialog initialized with categories: {list(self.topics['categories'].keys())}")  # Annotation: Logs available categories from topics.json for debugging.
        logger.debug(f"BotDialog methods: {dir(self)}")  # Annotation: Logs available methods in BotDialog for debugging.

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()  # Annotation: Records start time to measure method execution duration.
        user_id = update.message.from_user.id  # Annotation: Extracts Telegram user ID from the update for logging and data storage.
        logger.info(f"Received /start from user {user_id}")  # Annotation: Logs receipt of the /start command.
        buttons = [[cat] for cat in self.topics['categories'].keys()] + [[self.panic_option]]  # Annotation: Creates a vertical keyboard with category names from topics.json and a PANIC button.
        logger.debug(f"Generated start keyboard: {buttons}")  # Annotation: Logs the generated keyboard for debugging.
        await update.message.reply_text(
            "Üdvözöljük a Kórházi IT Támogató Botban! Kezdjük a jegy létrehozását.\n"
            "Milyen típusú problémát tapasztal? Sürgős esetekben válassza a 'PANIC' opciót.",
            reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True)
        )  # Annotation: Sends a welcome message in Hungarian with a category keyboard; one_time_keyboard hides it after selection.
        logger.debug(f"start method took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time for performance monitoring.
        return States.CATEGORY.value  # Annotation: Returns CATEGORY state (from states.py) to transition to category selection.

    async def auth(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()  # Annotation: Records start time to measure method execution duration.
        user_id = update.message.from_user.id  # Annotation: Extracts Telegram user ID for logging and data storage.
        email = update.message.text.strip()  # Annotation: Strips whitespace from the input email.
        logger.info(f"Received authentication email from user {user_id}: {email}")  # Annotation: Logs the received email.

        # Validate email format
        if not re.match(r'^[\w\.-]+@teszt-domain\.com$', email):  # Annotation: Validates email against a regex requiring @teszt-domain.com domain.
            logger.warning(f"Invalid email format from user {user_id}: {email}")  # Annotation: Logs a warning for invalid email format.
            # Log abuse attempt with ticket contents
            try:
                # Determine issue_description based on issue_id
                issue_description = None  # Annotation: Initializes issue_description for abuse logging.
                if context.user_data.get('issue_id') and context.user_data.get('category') and context.user_data.get('component'):
                    category = context.user_data['category']  # Annotation: Retrieves stored category from context.user_data.
                    component = context.user_data['component']  # Annotation: Retrieves stored component.
                    issue_id = context.user_data['issue_id']  # Annotation: Retrieves stored issue ID.
                    if issue_id != 'other' and category in self.topics['categories'] and component in self.topics['categories'][category]['options']:
                        issue_description = self.topics['categories'][category]['options'][component]['options'].get(issue_id, {}).get('description')  # Annotation: Gets predefined issue description from topics.json.
                    else:
                        issue_description = context.user_data.get('description')  # Annotation: Uses custom description if issue_id is 'other'.
                ticket_data = {
                    'category': context.user_data.get('category', None),
                    'component': context.user_data.get('component', None),
                    'issue_id': context.user_data.get('issue_id', None),
                    'issue_description': issue_description,
                    'description': context.user_data.get('description', None),
                    'team': context.user_data.get('team', None),
                    'campus': context.user_data.get('campus', None),
                    'department': context.user_data.get('department', None),
                    'building': context.user_data.get('building', None),
                    'floor': context.user_data.get('floor', None),
                    'room': context.user_data.get('room', None),
                    'latitude': context.user_data.get('latitude', None),
                    'longitude': context.user_data.get('longitude', None),
                    'media': context.user_data.get('media', None),
                    'name': context.user_data.get('name', None),
                    'phone': context.user_data.get('phone', None)
                }  # Annotation: Collects all ticket data for abuse logging.
                log_entry = {
                    'timestamp': datetime.now().isoformat(),
                    'user_id': user_id,
                    'email': email,
                    'ticket_data': ticket_data
                }  # Annotation: Creates a JSON log entry for the abuse attempt.
                with abuse_file_lock:
                    with open('/app/logs/abuse_attempts.txt', 'a', encoding='utf-8') as f:
                        f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')  # Annotation: Appends JSON log entry to abuse_attempts.txt with thread safety.
                logger.info(f"Logged abuse attempt for user {user_id}: {email} with ticket data")  # Annotation: Logs successful abuse logging.
            except Exception as e:
                logger.error(f"Failed to log abuse attempt for user {user_id}: {str(e)}")  # Annotation: Logs failure to write abuse log.
            await update.message.reply_text(
                "Sajnáljuk, ez az email cím nem jogosult a bot használatára. Kérem, lépjen kapcsolatba az IT-val.\n"
                "Felhívjuk figyelmét, hogy minden tevékenységet figyelünk a visszaélések elkerülése érdekében.",
                reply_markup=ReplyKeyboardRemove()
            )  # Annotation: Sends unauthorized message with disclaimer and removes keyboard.
            logger.debug(f"auth method (invalid email) took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
            return ConversationHandler.END  # Annotation: Ends the conversation for invalid email.

        # Check if email is in authorized_emails.csv
        try:
            with open('/app/config/authorized_emails.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                authorized_emails = {row['email'].lower().strip() for row in reader}  # Annotation: Reads authorized_emails.csv into a set of lowercase emails for fast lookup.
        except Exception as e:
            logger.error(f"Failed to read authorized_emails.csv: {str(e)}")  # Annotation: Logs error if CSV file reading fails.
            await update.message.reply_text(
                "Hiba történt az autentikáció során. Kérem, lépjen kapcsolatba az IT-val.",
                reply_markup=ReplyKeyboardRemove()
            )  # Annotation: Sends error message and removes keyboard.
            logger.debug(f"auth method took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
            return ConversationHandler.END  # Annotation: Ends the conversation on CSV read failure.

        if email.lower().strip() in authorized_emails:  # Annotation: Checks if the lowercase email is in the authorized set.
            logger.info(f"User {user_id} authenticated successfully with email: {email}")  # Annotation: Logs successful authentication.
            context.user_data['authenticated_email'] = email  # Annotation: Stores the authenticated email in context.user_data for submit_ticket.
            logger.debug(f"auth method took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
            return await self.submit_ticket(update, context)  # Annotation: Calls submit_ticket to proceed with ticket submission.
        else:
            logger.warning(f"Unauthorized email from user {user_id}: {email}")  # Annotation: Logs unauthorized email attempt.
            # Log abuse attempt with ticket contents
            try:
                issue_description = None
                if context.user_data.get('issue_id') and context.user_data.get('category') and context.user_data.get('component'):
                    category = context.user_data['category']
                    component = context.user_data['component']
                    issue_id = context.user_data['issue_id']
                    if issue_id != 'other' and category in self.topics['categories'] and component in self.topics['categories'][category]['options']:
                        issue_description = self.topics['categories'][category]['options'][component]['options'].get(issue_id, {}).get('description')
                    else:
                        issue_description = context.user_data.get('description')
                ticket_data = {
                    'category': context.user_data.get('category', None),
                    'component': context.user_data.get('component', None),
                    'issue_id': context.user_data.get('issue_id', None),
                    'issue_description': issue_description,
                    'description': context.user_data.get('description', None),
                    'team': context.user_data.get('team', None),
                    'campus': context.user_data.get('campus', None),
                    'department': context.user_data.get('department', None),
                    'building': context.user_data.get('building', None),
                    'floor': context.user_data.get('floor', None),
                    'room': context.user_data.get('room', None),
                    'latitude': context.user_data.get('latitude', None),
                    'longitude': context.user_data.get('longitude', None),
                    'media': context.user_data.get('media', None),
                    'name': context.user_data.get('name', None),
                    'phone': context.user_data.get('phone', None)
                }  # Annotation: Collects ticket data for abuse logging.
                log_entry = {
                    'timestamp': datetime.now().isoformat(),
                    'user_id': user_id,
                    'email': email,
                    'ticket_data': ticket_data
                }  # Annotation: Creates a JSON log entry for the abuse attempt.
                with abuse_file_lock:
                    with open('/app/logs/abuse_attempts.txt', 'a', encoding='utf-8') as f:
                        f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')  # Annotation: Appends JSON log entry to abuse_attempts.txt.
                logger.info(f"Logged abuse attempt for user {user_id}: {email} with ticket data")  # Annotation: Logs successful abuse logging.
            except Exception as e:
                logger.error(f"Failed to log abuse attempt for user {user_id}: {str(e)}")  # Annotation: Logs failure to write abuse log.
            await update.message.reply_text(
                "Sajnáljuk, ez az email cím nem jogosult a bot használatára. Kérem, lépjen kapcsolatba az IT-val.\n"
                "Felhívjuk figyelmét, hogy minden tevékenységet figyelünk a visszaélések elkerülése érdekében.",
                reply_markup=ReplyKeyboardRemove()
            )  # Annotation: Sends unauthorized message with disclaimer and removes keyboard.
            logger.debug(f"auth method took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
            return ConversationHandler.END  # Annotation: Ends the conversation for unauthorized email.

    async def category(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()  # Annotation: Records start time to measure method execution duration.
        user_id = update.message.from_user.id  # Annotation: Extracts Telegram user ID for logging.
        category = update.message.text.lower().strip()  # Annotation: Normalizes category input to lowercase and removes whitespace.
        logger.info(f"Received category from user {user_id}: {category}")  # Annotation: Logs the received category.

        if category == self.panic_option.lower():  # Annotation: Checks if the input is "panic" (case-insensitive).
            return await self.panic(update, context)  # Annotation: Calls panic method for emergency handling.

        if category in self.topics['categories']:  # Annotation: Verifies if the category exists in topics.json.
            context.user_data['category'] = category  # Annotation: Stores the category in context.user_data.
            context.user_data['team'] = self.topics['categories'][category]['team']  # Annotation: Stores the team from topics.json.
            components = list(self.topics['categories'][category]['options'].keys())  # Annotation: Retrieves component keys for the selected category.
            logger.debug(f"Generating keyboard for category {category}: {components}")  # Annotation: Logs components for debugging.
            buttons = [[self.topics['categories'][category]['options'][comp]['display_name'] or comp] for comp in components] + [[self.panic_option]]  # Annotation: Creates a keyboard with component display names (or keys) and a PANIC button.
            reply_markup = ReplyKeyboardMarkup(buttons, one_time_keyboard=True)  # Annotation: Creates a one-time keyboard.
            await update.message.reply_text(
                self.topics['categories'][category]['prompt'],
                reply_markup=reply_markup
            )  # Annotation: Sends the prompt for component selection from topics.json.
            logger.debug(f"category method took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
            return States.COMPONENT.value  # Annotation: Transitions to COMPONENT state.

        buttons = [[cat] for cat in self.topics['categories'].keys()] + [[self.panic_option]]  # Annotation: Creates a keyboard with all categories and PANIC for error handling.
        logger.debug(f"Generated category error keyboard: {buttons}")  # Annotation: Logs the error keyboard.
        await update.message.reply_text(
            f"Érvénytelen kategória. Kérem, válasszon egyet: {', '.join(self.topics['categories'].keys())}",
            reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True)
        )  # Annotation: Sends invalid category message with category keyboard.
        logger.debug(f"category method took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
        return States.CATEGORY.value  # Annotation: Returns to CATEGORY state for retry.

    async def component(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()  # Annotation: Records start time to measure method execution duration.
        user_id = update.message.from_user.id  # Annotation: Extracts Telegram user ID for logging.
        component = update.message.text.strip()  # Annotation: Strips whitespace from component input.
        category = context.user_data.get('category')  # Annotation: Retrieves stored category from context.user_data.
        logger.info(f"Received component from user {user_id}: {component}")  # Annotation: Logs the received component.

        if not category or category not in self.topics['categories']:  # Annotation: Checks if category is valid or exists.
            logger.error(f"Invalid or missing category: {category}")  # Annotation: Logs error for invalid/missing category.
            buttons = [[cat] for cat in self.topics['categories'].keys()] + [[self.panic_option]]  # Annotation: Creates a category keyboard for error handling.
            logger.debug(f"Generated component error keyboard (category invalid): {buttons}")  # Annotation: Logs the error keyboard.
            await update.message.reply_text(
                "Hiba: Kérem, válasszon egy kategóriát újra.",
                reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True)
            )  # Annotation: Sends error message to restart category selection.
            return States.CATEGORY.value  # Annotation: Returns to CATEGORY state.

        if component.lower() == self.panic_option.lower():  # Annotation: Checks if input is "panic" (case-insensitive).
            return await self.panic(update, context)  # Annotation: Calls panic method for emergency handling.

        components = {key.lower(): key for key in self.topics['categories'][category]['options'].keys()}  # Annotation: Creates a case-insensitive mapping of component keys.
        logger.debug(f"Available components for {category}: {list(components.values())}")  # Annotation: Logs available components.
        if component.lower() in components:  # Annotation: Checks if the component is valid.
            context.user_data['component'] = components[component.lower()]  # Annotation: Stores the original component key.
            issues = self.topics['categories'][category]['options'][components[component.lower()]]['options']  # Annotation: Retrieves issues for the component from topics.json.
            keyboard = [[f"{v['description']} ({k})"] for k, v in issues.items() if k != 'other'] + [['other'], [self.panic_option]]  # Annotation: Creates a keyboard with issue descriptions and an 'other' option.
            logger.debug(f"Generated issue keyboard: {keyboard}")  # Annotation: Logs the issue keyboard.
            await update.message.reply_text(
                self.topics['categories'][category]['options'][components[component.lower()]]['prompt'],
                reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            )  # Annotation: Sends the issue selection prompt from topics.json.
            logger.debug(f"component method took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
            return States.ISSUE.value  # Annotation: Transitions to ISSUE state.

        buttons = [[self.topics['categories'][category]['options'][comp]['display_name'] or comp] for comp in self.topics['categories'][category]['options'].keys()] + [[self.panic_option]]  # Annotation: Creates a keyboard with valid components for error handling.
        display_names = [self.topics['categories'][category]['options'][comp]['display_name'] or comp for comp in self.topics['categories'][category]['options'].keys()]  # Annotation: Lists display names for error message.
        logger.debug(f"Generated component error keyboard: {buttons}")  # Annotation: Logs the error keyboard.
        await update.message.reply_text(
            f"Érvénytelen komponens. Kérem, válasszon egyet: {', '.join(display_names)}",
            reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True)
        )  # Annotation: Sends invalid component message with component keyboard.
        logger.debug(f"component method took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
        return States.COMPONENT.value  # Annotation: Returns to COMPONENT state for retry.

    async def panic(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()  # Annotation: Records start time to measure method execution duration.
        user_id = update.message.from_user.id  # Annotation: Extracts Telegram user ID for logging.
        logger.info(f"User {user_id} triggered PANIC button")  # Annotation: Logs that the PANIC button was triggered.
        self.form_data.clear(user_id)  # Annotation: Clears user data using FormData.clear (form_data.py).
        await update.message.reply_text(
            "Sürgős problémák esetén kérjük, hívja az IT-t a +36-1-555-1234 telefonszámon.",
            reply_markup=ReplyKeyboardRemove()
        )  # Annotation: Sends emergency contact instructions and removes keyboard.
        logger.debug(f"panic method took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
        return ConversationHandler.END  # Annotation: Ends the conversation.

    async def issue(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()  # Annotation: Records start time to measure method execution duration.
        user_id = update.message.from_user.id  # Annotation: Extracts Telegram user ID for logging.
        issue = update.message.text  # Annotation: Retrieves issue input (e.g., "Login Issue (1)" or "other").
        category = context.user_data.get('category')  # Annotation: Retrieves stored category.
        component = context.user_data.get('component')  # Annotation: Retrieves stored component.
        logger.info(f"Received issue from user {user_id}: {issue}")  # Annotation: Logs the issue input.

        if issue.lower() == self.panic_option.lower():  # Annotation: Checks for PANIC option.
            return await self.panic(update, context)  # Annotation: Calls panic method.

        issues = self.topics['categories'][category]['options'][component]['options']  # Annotation: Retrieves issues from topics.json.
        issue_id = next((k for k, v in issues.items() if issue.endswith(f"({k})")), None)  # Annotation: Extracts issue_id from input (e.g., "1" from "Login Issue (1)").
        if issue == 'other':  # Annotation: Handles 'other' issue selection.
            await update.message.reply_text(
                issues['other']['prompt'],
                reply_markup=ReplyKeyboardMarkup([[self.panic_option]], one_time_keyboard=True)
            )  # Annotation: Sends prompt for custom issue description.
            logger.debug(f"issue method took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
            return States.OTHER_ISSUE.value  # Annotation: Transitions to OTHER_ISSUE state.

        elif issue_id and issue_id != 'other':  # Annotation: Handles valid predefined issue selection.
            context.user_data['issue_id'] = issue_id  # Annotation: Stores issue_id.
            context.user_data['description'] = issues[issue_id]['description']  # Annotation: Stores predefined description.
            component_display_name = self.topics['categories'][category]['options'][component].get('display_name', component)  # Annotation: Gets component display_name or falls back to component key.
            context.user_data['issue'] = f"{component_display_name} - {issues[issue_id]['description']} ({issue_id})"  # Annotation: Sets 'issue' as "component_display_name - description (id)".
            keyboard = [[c['name']] for c in self.locations['campuses']] + [[self.panic_option]]  # Annotation: Creates campus keyboard.
            logger.debug(f"Generated campus keyboard: {keyboard}")  # Annotation: Logs campus keyboard.
            await update.message.reply_text(
                self.locations['prompts']['campus']['hu'],
                reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            )  # Annotation: Sends campus prompt.
            logger.debug(f"issue method took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
            return States.CAMPUS.value  # Annotation: Transitions to CAMPUS state.

        keyboard = [[f"{v['description']} ({k})"] for k, v in issues.items() if k != 'other'] + [['other'], [self.panic_option]]  # Annotation: Creates error keyboard.
        logger.debug(f"Generated issue error keyboard: {keyboard}")  # Annotation: Logs error keyboard.
        await update.message.reply_text(
            f"Érvénytelen probléma. Kérem, válasszon egyet:",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )  # Annotation: Sends invalid issue message.
        logger.debug(f"issue method took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
        return States.ISSUE.value  # Annotation: Returns to ISSUE state.

    async def other_issue(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()  # Annotation: Records start time to measure method execution duration.
        user_id = update.message.from_user.id  # Annotation: Extracts Telegram user ID for logging.
        description = update.message.text.strip()  # Annotation: Retrieves and strips custom description input.
        logger.info(f"Received other issue from user {user_id}: {description}")  # Annotation: Logs custom description.

        if description.lower() == self.panic_option.lower():  # Annotation: Checks for PANIC option.
            return await self.panic(update, context)  # Annotation: Calls panic method.

        context.user_data['issue_id'] = 'other'  # Annotation: Stores 'other' as issue_id.
        context.user_data['description'] = description  # Annotation: Stores custom description.
        context.user_data['issue'] = description  # Annotation: Stores custom description as 'issue' for 'other' case.
        keyboard = [[c['name']] for c in self.locations['campuses']] + [[self.panic_option]]  # Annotation: Creates campus keyboard.
        logger.debug(f"Generated campus keyboard: {keyboard}")  # Annotation: Logs campus keyboard.
        await update.message.reply_text(
            self.locations['prompts']['campus']['hu'],
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )  # Annotation: Sends campus prompt.
        logger.debug(f"other_issue method took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
        return States.CAMPUS.value  # Annotation: Transitions to CAMPUS state.

    async def campus(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()  # Annotation: Records start time to measure method execution duration.
        user_id = update.message.from_user.id  # Annotation: Extracts Telegram user ID for logging.
        campus = update.message.text  # Annotation: Retrieves campus input.
        logger.info(f"Received campus from user {user_id}: {campus}")  # Annotation: Logs the received campus.

        campuses = [c['name'] for c in self.locations['campuses']]  # Annotation: Lists campus names from locations.json.
        if campus in campuses:  # Annotation: Checks if the campus is valid.
            context.user_data['campus'] = campus  # Annotation: Stores the campus in context.user_data.
            departments = [d['name'] for d in next(c['departments'] for c in self.locations['campuses'] if c['name'] == campus)]  # Annotation: Retrieves department names for the selected campus.
            keyboard = [[d] for d in departments] + [[self.panic_option]]  # Annotation: Creates a keyboard with department names and PANIC.
            logger.debug(f"Generated department keyboard: {keyboard}")  # Annotation: Logs the department keyboard.
            await update.message.reply_text(
                self.locations['prompts']['department']['hu'],
                reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            )  # Annotation: Sends department selection prompt from locations.json.
            logger.debug(f"campus method took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
            return States.DEPARTMENT.value  # Annotation: Transitions to DEPARTMENT state.

        keyboard = [[c['name']] for c in self.locations['campuses']] + [[self.panic_option]]  # Annotation: Creates a keyboard with valid campuses for error handling.
        logger.debug(f"Generated campus error keyboard: {keyboard}")  # Annotation: Logs the error keyboard.
        await update.message.reply_text(
            f"Érvénytelen kampusz. {self.locations['prompts']['campus']['hu']}",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )  # Annotation: Sends invalid campus message with campus keyboard.
        logger.debug(f"campus method took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
        return States.CAMPUS.value  # Annotation: Returns to CAMPUS state for retry.

    async def department(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()  # Annotation: Records start time to measure method execution duration.
        user_id = update.message.from_user.id  # Annotation: Extracts Telegram user ID for logging.
        department = update.message.text  # Annotation: Retrieves department input.
        logger.info(f"Received department from user {user_id}: {department}")  # Annotation: Logs the received department.
        campus = context.user_data['campus']  # Annotation: Retrieves stored campus.
        departments = next(c['departments'] for c in self.locations['campuses'] if c['name'] == campus)  # Annotation: Retrieves departments for the campus.
        department_names = [d['name'] for d in departments]  # Annotation: Lists department names.
        if department in department_names:  # Annotation: Checks if the department is valid.
            context.user_data['department'] = department  # Annotation: Stores the department in context.user_data.
            dept_data = next(d for d in departments if d['name'] == department)  # Annotation: Retrieves department data.
            context.user_data['building'] = dept_data['building']  # Annotation: Stores building from department data.
            context.user_data['floor'] = dept_data['floor']  # Annotation: Stores floor from department data.
            await update.message.reply_text(
                self.locations['prompts']['room']['hu'],
                reply_markup=ReplyKeyboardRemove()
            )  # Annotation: Sends room prompt from locations.json and removes keyboard.
            logger.debug(f"department method took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
            return States.ROOM.value  # Annotation: Transitions to ROOM state.

        keyboard = [[d] for d in department_names] + [[self.panic_option]]  # Annotation: Creates a keyboard with valid departments for error handling.
        logger.debug(f"Generated department error keyboard: {keyboard}")  # Annotation: Logs the error keyboard.
        await update.message.reply_text(
            f"Érvénytelen osztály. {self.locations['prompts']['department']['hu']}",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )  # Annotation: Sends invalid department message with department keyboard.
        logger.debug(f"department method took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
        return States.DEPARTMENT.value  # Annotation: Returns to DEPARTMENT state for retry.

    async def room(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()  # Annotation: Records start time to measure method execution duration.
        user_id = update.message.from_user.id  # Annotation: Extracts Telegram user ID for logging.
        room = update.message.text.strip()  # Annotation: Strips whitespace from room input.
        logger.info(f"Received room from user {user_id}: {room}")  # Annotation: Logs the received room number.
        if re.match(self.locations['validation']['room'], room):  # Annotation: Validates room number against regex from locations.json.
            context.user_data['room'] = room  # Annotation: Stores the room number in context.user_data.
            keyboard = [[KeyboardButton("Hely megosztása", request_location=True)], ["Kihagy"]]  # Annotation: Creates a keyboard with location sharing and skip options.
            logger.debug(f"Generated geolocation keyboard: {keyboard}")  # Annotation: Logs the geolocation keyboard.
            await update.message.reply_text(
                self.locations['prompts']['geolocation']['hu'],
                reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            )  # Annotation: Sends geolocation prompt from locations.json.
            logger.debug(f"room method took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
            return States.GEOLOCATION.value  # Annotation: Transitions to GEOLOCATION state.

        await update.message.reply_text(
            "Érvénytelen szoba szám. Kérem, adjon meg egy érvényes szoba vagy iroda számot (pl. 204-es szoba).",
            reply_markup=ReplyKeyboardRemove()
        )  # Annotation: Sends invalid room number message and removes keyboard.
        logger.debug(f"room method took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
        return States.ROOM.value  # Annotation: Returns to ROOM state for retry.

    async def geolocation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()  # Annotation: Records start time to measure method execution duration.
        user_id = update.message.from_user.id  # Annotation: Extracts Telegram user ID for logging.
        logger.info(f"Processing geolocation for user {user_id}")  # Annotation: Logs geolocation processing start.

        if update.message.text:  # Annotation: Checks if user sent a text message.
            text = unicodedata.normalize('NFKC', update.message.text.strip()).lower()  # Annotation: Normalizes text input for case-insensitive comparison.
            logger.debug(f"Normalized geolocation input: {text}")  # Annotation: Logs normalized input.
            if text == "kihagy":  # Annotation: Checks if user chose to skip geolocation.
                logger.info(f"User {user_id} skipped geolocation")  # Annotation: Logs skip action.
                context.user_data['latitude'] = None  # Annotation: Stores None for latitude.
                context.user_data['longitude'] = None  # Annotation: Stores None for longitude.
                await update.message.reply_text(
                    "Adja meg a nevét:",
                    reply_markup=ReplyKeyboardRemove()
                )  # Annotation: Sends name prompt and removes keyboard.
                logger.debug(f"geolocation method (kihagy) took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
                return States.NAME.value  # Annotation: Transitions to NAME state.

        if update.message.location:  # Annotation: Checks if user shared a location.
            location = update.message.location  # Annotation: Retrieves location object.
            logger.info(f"Received geolocation from user {user_id}: ({location.latitude}, {location.longitude})")  # Annotation: Logs received coordinates.
            context.user_data['latitude'] = location.latitude  # Annotation: Stores latitude.
            context.user_data['longitude'] = location.longitude  # Annotation: Stores longitude.
            await update.message.reply_text(
                "Adja meg a nevét:",
                reply_markup=ReplyKeyboardRemove()
            )  # Annotation: Sends name prompt and removes keyboard.
            logger.debug(f"geolocation method (location) took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
            return States.NAME.value  # Annotation: Transitions to NAME state.

        keyboard = [[KeyboardButton("Hely megosztása", request_location=True)], ["Kihagy"]]  # Annotation: Creates a keyboard for retrying location sharing.
        logger.debug(f"Generated geolocation error keyboard: {keyboard}")  # Annotation: Logs the error keyboard.
        await update.message.reply_text(
            "Kérem, ossza meg a helyet vagy válassza a 'Kihagy' opciót.",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )  # Annotation: Sends invalid input message with retry keyboard.
        logger.debug(f"geolocation method (invalid) took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
        return States.GEOLOCATION.value  # Annotation: Returns to GEOLOCATION state for retry.

    async def name(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()  # Annotation: Records start time to measure method execution duration.
        user_id = update.message.from_user.id  # Annotation: Extracts Telegram user ID for logging.
        context.user_data['name'] = update.message.text  # Annotation: Stores the user's name in context.user_data.
        logger.info(f"Received name from user {user_id}: {context.user_data['name']}")  # Annotation: Logs the received name.
        keyboard = [[KeyboardButton("Kapcsolat megosztása", request_contact=True)]]  # Annotation: Creates a keyboard with contact sharing button.
        logger.debug(f"Generated phone keyboard: {keyboard}")  # Annotation: Logs the phone keyboard.
        await update.message.reply_text(
            "Adja meg telefonszámát (vagy használja a Telegram kapcsolat megosztás opcióját):",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )  # Annotation: Sends phone number prompt with contact sharing option.
        logger.debug(f"name method took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
        return States.PHONE.value  # Annotation: Transitions to PHONE state.

    async def phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()  # Annotation: Records start time to measure method execution duration.
        user_id = update.message.from_user.id  # Annotation: Extracts Telegram user ID for logging.
        if update.message.contact:  # Annotation: Checks if user shared a contact.
            context.user_data['phone'] = update.message.contact.phone_number  # Annotation: Stores phone number from contact.
        else:
            context.user_data['phone'] = update.message.text  # Annotation: Stores phone number from text input.
        logger.info(f"Received phone from user {user_id}: {context.user_data['phone']}")  # Annotation: Logs the received phone number.
        keyboard = [["Kihagy"]]  # Annotation: Creates a keyboard with skip option for description.
        logger.debug(f"Generated description keyboard: {keyboard}")  # Annotation: Logs the description keyboard.
        await update.message.reply_text(
            "Adjon meg további részleteket (opcionális, nyomja meg a 'Kihagy' gombot a folytatáshoz):",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )  # Annotation: Sends description prompt with skip option.
        logger.debug(f"phone method took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
        return States.DESCRIPTION.value  # Annotation: Transitions to DESCRIPTION state.

    async def description(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()  # Annotation: Records start time to measure method execution duration.
        user_id = update.message.from_user.id  # Annotation: Extracts Telegram user ID for logging.
        description = update.message.text  # Annotation: Retrieves description input.
        logger.info(f"Received description from user {user_id}: {description}")  # Annotation: Logs the received description.
        if description:  # Annotation: Checks if description is provided.
            text = unicodedata.normalize('NFKC', description.strip()).lower()  # Annotation: Normalizes description for case-insensitive comparison.
            logger.debug(f"Normalized description input: {text}")  # Annotation: Logs normalized description.
            if text == "kihagy":  # Annotation: Checks if user chose to skip.
                if context.user_data.get('issue_id') != 'other':  # Annotation: Preserves predefined description for non-'other' issues.
                    context.user_data['description'] = context.user_data.get('description', 'Nincs további részlet megadva')
                else:  # Annotation: Sets default for 'other' issues if skipped.
                    context.user_data['description'] = 'Nincs további részlet megadva'
            else:
                context.user_data['description'] = description  # Annotation: Stores the provided description.
        else:  # Annotation: Handles empty input (e.g., non-text message).
            if context.user_data.get('issue_id') != 'other':  # Annotation: Preserves predefined description for non-'other' issues.
                context.user_data['description'] = context.user_data.get('description', 'Nincs további részlet megadva')
            else:  # Annotation: Sets default for 'other' issues.
                context.user_data['description'] = 'Nincs további részlet megadva'
        keyboard = [["Kihagy"]]  # Annotation: Creates a keyboard with skip option for media.
        logger.debug(f"Generated media keyboard: {keyboard}")  # Annotation: Logs the media keyboard.
        await update.message.reply_text(
            self.locations['prompts']['media']['hu'],
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )  # Annotation: Sends media prompt from locations.json.
        logger.debug(f"description method took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
        return States.MEDIA.value  # Annotation: Transitions to MEDIA state.

    async def media(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()  # Annotation: Records start time to measure method execution duration.
        user_id = update.message.from_user.id  # Annotation: Extracts Telegram user ID for logging.
        logger.info(f"Processing media for user {user_id}")  # Annotation: Logs media processing start.

        if update.message.text:  # Annotation: Checks if user sent a text message.
            text = unicodedata.normalize('NFKC', update.message.text.strip()).lower()  # Annotation: Normalizes text input.
            logger.debug(f"Normalized media input: {text}")  # Annotation: Logs normalized input.
            if text == "kihagy":  # Annotation: Checks if user chose to skip media.
                logger.info(f"User {user_id} skipped media upload")  # Annotation: Logs skip action.
                context.user_data['media'] = None  # Annotation: Stores None for media.
                await update.message.reply_text(
                    "Adja meg email címét az autentikációhoz:\n"
                    "Felhívjuk figyelmét, hogy minden tevékenységet figyelünk a visszaélések elkerülése érdekében.",
                    reply_markup=ReplyKeyboardRemove()
                )  # Annotation: Sends email authentication prompt and removes keyboard.
                logger.debug(f"media method (kihagy) took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
                return States.AUTH.value  # Annotation: Transitions to AUTH state.

        if update.message.photo or update.message.video:  # Annotation: Checks if user sent a photo or video.
            media = update.message.photo[-1] if update.message.photo else update.message.video  # Annotation: Selects the highest resolution photo or the video.
            file_size = media.file_size  # Annotation: Retrieves the file size.
            if file_size > self.max_media_size:  # Annotation: Checks if file exceeds 20MB limit.
                logger.warning(f"Media file too large from user {user_id}: {file_size} bytes")  # Annotation: Logs warning for oversized file.
                keyboard = [["Kihagy"]]  # Annotation: Creates a skip keyboard for retry.
                logger.debug(f"Generated media error keyboard (too large): {keyboard}")  # Annotation: Logs the error keyboard.
                await update.message.reply_text(
                    f"A fájl túl nagy (max. 20MB, kapott {file_size // 1_000_000}MB). Kérem, töltsön fel kisebb fájlt vagy nyomja meg a Kihagy gombot.",
                    reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
                )  # Annotation: Sends oversized file message with retry keyboard.
                logger.debug(f"media method (too large) took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
                return States.MEDIA.value  # Annotation: Returns to MEDIA state for retry.

            try:
                file = await context.bot.get_file(media.file_id)  # Annotation: Retrieves the file object from Telegram.
                ext = '.jpg' if update.message.photo else '.mp4'  # Annotation: Sets extension based on media type.
                file_path = f"/app/tmp/{user_id}_{datetime.now().strftime('%Y%m%dT%H%M%S')}{ext}"  # Annotation: Generates a unique file path for temporary storage.
                await asyncio.wait_for(file.download_to_drive(file_path), timeout=10.0)  # Annotation: Downloads the file with a 10-second timeout.
                context.user_data['media'] = file_path  # Annotation: Stores the file path in context.user_data.
                logger.info(f"Media file downloaded for user {user_id}: {file_path}")  # Annotation: Logs successful download.
                await update.message.reply_text(
                    "Adja meg email címét az autentikációhoz:\n"
                    "Felhívjuk figyelmét, hogy minden tevékenységet figyelünk a visszaélések elkerülése érdekében.",
                    reply_markup=ReplyKeyboardRemove()
                )  # Annotation: Sends email authentication prompt and removes keyboard.
                logger.debug(f"media method (download) took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
                return States.AUTH.value  # Annotation: Transitions to AUTH state.

            except asyncio.TimeoutError:
                logger.error(f"Media download timed out for user {user_id}")  # Annotation: Logs timeout error.
                keyboard = [["Kihagy"]]  # Annotation: Creates a skip keyboard for retry.
                logger.debug(f"Generated media error keyboard (timeout): {keyboard}")  # Annotation: Logs the error keyboard.
                await update.message.reply_text(
                    "A média letöltése időtúllépés miatt nem sikerült. Kérem, próbálja újra vagy nyomja meg a Kihagy gombot.",
                    reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
                )  # Annotation: Sends timeout error message with retry keyboard.
                logger.debug(f"media method (timeout) took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
                return States.MEDIA.value  # Annotation: Returns to MEDIA state for retry.

            except Exception as e:
                logger.error(f"Failed to download media for user {user_id}: {str(e)}")  # Annotation: Logs general download error.
                keyboard = [["Kihagy"]]  # Annotation: Creates a skip keyboard for retry.
                logger.debug(f"Generated media error keyboard (error): {keyboard}")  # Annotation: Logs the error keyboard.
                await update.message.reply_text(
                    "Nem sikerült a média feldolgozása. Kérem, próbálja újra vagy nyomja meg a Kihagy gombot.",
                    reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
                )  # Annotation: Sends general error message with retry keyboard.
                logger.debug(f"media method (error) took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
                return States.MEDIA.value  # Annotation: Returns to MEDIA state for retry.

        keyboard = [["Kihagy"]]  # Annotation: Creates a skip keyboard for invalid input.
        logger.debug(f"Generated media error keyboard (invalid): {keyboard}")  # Annotation: Logs the error keyboard.
        await update.message.reply_text(
            "Kérem, töltsön fel egy képet vagy videót (max. 20MB), vagy nyomja meg a Kihagy gombot.",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )  # Annotation: Sends invalid input message with retry keyboard.
        logger.debug(f"media method (invalid) took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
        return States.MEDIA.value  # Annotation: Returns to MEDIA state for retry.

    async def submit_ticket(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()  # Annotation: Records start time to measure method execution duration.
        user_id = update.message.from_user.id  # Annotation: Extracts Telegram user ID for logging and data storage.
        try:
            self.form_data.store(user_id, 'category', context.user_data['category'])  # Annotation: Stores category using FormData.store (form_data.py).
            self.form_data.store(user_id, 'component', context.user_data['component'])  # Annotation: Stores component.
            self.form_data.store(user_id, 'issue_id', context.user_data['issue_id'])  # Annotation: Stores issue ID.
            self.form_data.store(user_id, 'issue', context.user_data['issue'])  # Annotation: Stores computed 'issue' string (e.g., "Login Error (Unable to log in)" or custom description).
            self.form_data.store(user_id, 'description', context.user_data['description'])  # Annotation: Stores issue description (predefined or custom).
            self.form_data.store(user_id, 'team', context.user_data['team'])  # Annotation: Stores team from topics.json.
            self.form_data.store(user_id, 'campus', context.user_data['campus'])  # Annotation: Stores campus from locations.json.
            self.form_data.store(user_id, 'department', context.user_data['department'])  # Annotation: Stores department.
            self.form_data.store(user_id, 'building', context.user_data['building'])  # Annotation: Stores building.
            self.form_data.store(user_id, 'floor', context.user_data['floor'])  # Annotation: Stores floor.
            self.form_data.store(user_id, 'room', context.user_data['room'])  # Annotation: Stores room number.
            self.form_data.store(user_id, 'latitude', context.user_data.get('latitude'))  # Annotation: Stores optional latitude.
            self.form_data.store(user_id, 'longitude', context.user_data.get('longitude'))  # Annotation: Stores optional longitude.
            self.form_data.store(user_id, 'media', context.user_data.get('media'))  # Annotation: Stores optional media file path.
            self.form_data.store(user_id, 'name', context.user_data['name'])  # Annotation: Stores user's name.
            self.form_data.store(user_id, 'phone', context.user_data['phone'])  # Annotation: Stores phone number.
            self.form_data.store(user_id, 'email', context.user_data['authenticated_email'])  # Annotation: Stores authenticated email.
            self.form_data.store(user_id, 'date', datetime.now().isoformat())  # Annotation: Stores submission timestamp in ISO format.
            form_data = self.form_data.get_form_data(user_id)  # Annotation: Retrieves formatted ticket data using FormData.get_form_data.
            media_path = context.user_data.get('media')  # Annotation: Retrieves media file path (if any).
            try:
                if self.email_service.send_email(
                    form_data=form_data,
                    user_id=user_id,
                    from_email=context.user_data['authenticated_email'],
                    to_email=self.email_recipient,
                    user_name=context.user_data['name'],
                    media_path=media_path
                ):  # Annotation: Calls EmailService.send_email (email_service.py) to send ticket data and optional media.
                    logger.info(f"Ticket successfully sent for user {user_id}")  # Annotation: Logs successful ticket submission.
                    await update.message.reply_text(
                        "A jegy sikeresen elküldve, az IT munkatársak hamarosan felülvizsgálják. Köszönjük!",
                        reply_markup=ReplyKeyboardRemove()
                    )  # Annotation: Sends success message and removes keyboard.
                else:
                    logger.error(f"Email sending failed for user {user_id}: Unknown error")  # Annotation: Logs email sending failure.
                    await update.message.reply_text(
                        "Nem sikerült a jegy elküldése. Kérem, próbálja újra vagy lépjen kapcsolatba közvetlenül az IT-val.",
                        reply_markup=ReplyKeyboardRemove()
                    )  # Annotation: Sends failure message and removes keyboard.
            except Exception as e:
                logger.error(f"Email sending failed for user {user_id}: {str(e)}")  # Annotation: Logs email sending error.
                await update.message.reply_text(
                    "Hiba történt a jegy elküldése során. Kérem, próbálja újra vagy lépjen kapcsolatba közvetlenül az IT-val.",
                    reply_markup=ReplyKeyboardRemove()
                )  # Annotation: Sends error message and removes keyboard.
            finally:
                if media_path and os.path.exists(media_path):  # Annotation: Checks if media file exists.
                    try:
                        os.remove(media_path)  # Annotation: Deletes temporary media file.
                        logger.info(f"Deleted temporary media file: {media_path}")  # Annotation: Logs successful deletion.
                    except Exception as e:
                        logger.error(f"Failed to delete media file {media_path}: {str(e)}")  # Annotation: Logs deletion failure.
            self.form_data.clear(user_id)  # Annotation: Clears user data using FormData.clear.
            logger.debug(f"submit_ticket method took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
            return ConversationHandler.END  # Annotation: Ends the conversation.
        except Exception as e:
            logger.error(f"Error in ticket submission for user {user_id}: {str(e)}")  # Annotation: Logs general submission error.
            await update.message.reply_text(
                "Hiba történt. Kérem, próbálja újra vagy válassza a 'PANIC' opciót az IT-val való kapcsolatfelvételhez.",
                reply_markup=ReplyKeyboardMarkup([[self.panic_option]], one_time_keyboard=True)
            )  # Annotation: Sends error message with PANIC button.
            logger.debug(f"submit_ticket method took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
            return States.MEDIA.value  # Annotation: Returns to MEDIA state for retry.

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()  # Annotation: Records start time to measure method execution duration.
        user_id = update.message.from_user.id  # Annotation: Extracts Telegram user ID for logging.
        logger.info(f"Received /cancel from user {user_id}")  # Annotation: Logs receipt of /cancel command.
        media_path = context.user_data.get('media')  # Annotation: Retrieves stored media file path.
        if media_path and os.path.exists(media_path):  # Annotation: Checks if media file exists.
            try:
                os.remove(media_path)  # Annotation: Deletes temporary media file.
                logger.info(f"Deleted temporary media file: {media_path}")  # Annotation: Logs successful deletion.
            except Exception as e:
                logger.error(f"Failed to delete media file {media_path}: {str(e)}")  # Annotation: Logs deletion failure.
        self.form_data.clear(user_id)  # Annotation: Clears user data using FormData.clear.
        await update.message.reply_text(
            "A jegy benyújtása megszakítva.",
            reply_markup=ReplyKeyboardRemove()
        )  # Annotation: Sends cancellation confirmation and removes keyboard.
        logger.debug(f"cancel method took {(datetime.now() - start_time).total_seconds()} seconds")  # Annotation: Logs execution time.
        return ConversationHandler.END  # Annotation: Ends the conversation.
