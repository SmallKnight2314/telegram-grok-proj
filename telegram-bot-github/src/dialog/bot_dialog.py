# Import standard library modules for logging, JSON handling, regex, file operations, async tasks, and datetime
import logging
import json
import re
import os
import asyncio
import unicodedata
import csv
from datetime import datetime, timedelta
from threading import Lock

# Import Telegram Bot API classes for handling updates, keyboard buttons, and reply markups
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

# Import Telegram Bot API context types and conversation handler for state management
from telegram.ext import ContextTypes, ConversationHandler

# Import custom modules for form data, email service, and conversation states
from src.data.form_data import FormData
from src.services.email_service import EmailService
from src.states import States

# Initialize logger for this module, using the existing logging configuration
logger = logging.getLogger(__name__)

# Initialize a threading lock to prevent concurrent writes to blocked_users.txt
abuse_file_lock = Lock()

# Print to console to confirm bot_dialog.py module is loaded
print("Loading bot_dialog.py module")

# Define the BotDialog class to handle the conversation flow for the IT ticket bot
class BotDialog:
    # Initialize BotDialog with paths to config files, form data, email service, and recipient
    def __init__(self, topics_path: str, locations_path: str, form_data: FormData, email_service: EmailService, email_recipient: str):
        # Store form_data for managing ticket data
        self.form_data = form_data
        # Store email_service for sending ticket emails
        self.email_service = email_service
        # Store email_recipient for ticket submission
        self.email_recipient = email_recipient
        # Load IS_OTHER_ALLOWED env var (default: true) to allow/disallow 'Other' option
        self.is_other_allowed = os.getenv("IS_OTHER_ALLOWED", "true").lower() == "true"
        # Initialize dictionary to store blocked users
        self.blocked_users = {}
        # Load topics.json for categories, components, and issues
        try:
            with open(topics_path, 'r', encoding='utf-8') as f:
                self.topics = json.load(f)
            logger.debug(f"Loaded topics.json: {self.topics}")
            print(f"Loaded topics.json with categories: {list(self.topics['categories'].keys())}")
        except Exception as e:
            logger.error(f"Failed to load topics.json: {str(e)}")
            print(f"ERROR: Failed to load topics.json: {str(e)}")
            raise
        # Load locations.json for campus, building, floor, and department data
        try:
            with open(locations_path, 'r', encoding='utf-8') as f:
                self.locations = json.load(f)
            logger.debug(f"Loaded locations.json: {self.locations}")
            print(f"Loaded locations.json with campuses: {[c['name'] for c in self.locations['campuses']]}")
        except Exception as e:
            logger.error(f"Failed to load locations.json: {str(e)}")
            print(f"ERROR: Failed to load locations.json: {str(e)}")
            raise
        # Load blocked users from file
        try:
            self.load_blocked_users()
        except Exception as e:
            logger.error(f"Failed to load blocked_users.txt: {str(e)}")
            print(f"ERROR: Failed to load blocked_users.txt: {str(e)}")
        # Define constant for panic option
        self.panic_option = "PANIC"
        # Define constant for 'Other' option
        self.other_option = "Other"
        # Set max media file size (20MB)
        self.max_media_size = 20_000_000
        # Set max length for description field
        self.max_description_length = 1000
        # Set max length for address field
        self.max_address_length = 1000
        # Log initialization details
        logger.debug(f"BotDialog initialized with categories: {list(self.topics['categories'].keys())}")
        logger.debug(f"Blocked users: {self.blocked_users}")
        logger.debug(f"is_other_allowed: {self.is_other_allowed}")
        print(f"BotDialog initialized with is_other_allowed: {self.is_other_allowed}")

    # Load blocked users from blocked_users.txt
    def load_blocked_users(self):
        # Attempt to read blocked_users.txt
        try:
            with open('/app/logs/blocked_users.txt', 'r', encoding='utf-8') as f:
                # Read each line as a JSON object
                for line in f:
                    data = json.loads(line.strip())
                    user_id = data['user_id']
                    expiry = datetime.fromisoformat(data['expiry'])
                    # Store blocked user data in memory
                    self.blocked_users[user_id] = {
                        'expiry': expiry,
                        'reason': data.get('reason', 'N/A'),
                        'timestamp': data.get('timestamp', 'N/A'),
                        'ticket_data': data.get('ticket_data', {})
                    }
            logger.debug(f"Loaded blocked users: {self.blocked_users}")
            print(f"Loaded {len(self.blocked_users)} blocked users")
        except FileNotFoundError:
            # Handle case where blocked_users.txt doesn't exist
            logger.info("No blocked_users.txt found, starting with empty blocked_users")
            print("No blocked_users.txt found, starting with empty blocked_users")
        except Exception as e:
            # Log and raise any other errors
            logger.error(f"Error loading blocked_users.txt: {str(e)}")
            print(f"ERROR: Failed to load blocked_users.txt: {str(e)}")
            raise

    # Save a blocked user to blocked_users.txt
    def save_blocked_users(self, user_id: int, expiry: datetime, reason: str, timestamp: str, ticket_data: dict):
        # Create log entry for blocked user
        log_entry = {
            'user_id': user_id,
            'expiry': expiry.isoformat(),
            'reason': reason,
            'timestamp': timestamp,
            'ticket_data': ticket_data
        }
        # Use lock to prevent concurrent file writes
        with abuse_file_lock:
            try:
                # Append log entry to blocked_users.txt
                with open('/app/logs/blocked_users.txt', 'a', encoding='utf-8') as f:
                    f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
                logger.info(f"Saved block for user {user_id} until {expiry.isoformat()}")
                print(f"Blocked user {user_id} until {expiry.isoformat()} for reason: {reason}")
            except Exception as e:
                # Log and print error if saving fails
                logger.error(f"Failed to save block for user {user_id}: {str(e)}")
                print(f"ERROR: Failed to save block for user {user_id}: {str(e)}")

    # Check if a user is blocked
    def is_blocked(self, user_id: int) -> bool:
        # Check if user_id is in blocked_users
        if user_id in self.blocked_users:
            expiry = self.blocked_users[user_id]['expiry']
            # Check if block is still active
            if expiry is None or datetime.now() < expiry:
                logger.debug(f"User {user_id} is blocked until {expiry}")
                print(f"User {user_id} is blocked until {expiry}")
                return True
            else:
                # Remove expired block
                del self.blocked_users[user_id]
                logger.info(f"Block expired for user {user_id}")
                print(f"Block expired for user {user_id}")
        return False

    # Block a user for a specified duration
    def block_user(self, user_id: int, duration_seconds: int = 3600, reason: str = "Invalid input", ticket_data: dict = {}):
        # Calculate block expiry time
        expiry = datetime.now() + timedelta(seconds=duration_seconds)
        timestamp = datetime.now().isoformat()
        # Store block data in memory
        self.blocked_users[user_id] = {
            'expiry': expiry,
            'reason': reason,
            'timestamp': timestamp,
            'ticket_data': ticket_data
        }
        # Save block to file
        self.save_blocked_users(user_id, expiry, reason, timestamp, ticket_data)
        logger.info(f"User {user_id} blocked until {expiry.isoformat()} for reason: {reason}")
        print(f"User {user_id} blocked until {expiry.isoformat()} for reason: {reason}")

    # Handle /start command to initiate conversation
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        # Record start time for performance tracking
        start_time = datetime.now()
        # Get user ID from the message
        user_id = update.message.from_user.id
        logger.info(f"Received /start from user {user_id}")
        print(f"User {user_id} started conversation with /start")
        # Check if user is blocked
        if self.is_blocked(user_id):
            # Notify blocked user and end conversation
            await update.message.reply_text(
                "Ön túl sokszor próbálta a rendszert. Kérem, próbálja újra később.",
                reply_markup=ReplyKeyboardRemove()
            )
            logger.debug(f"Blocked user {user_id} attempted to start conversation")
            print(f"Blocked user {user_id} attempted to start conversation")
            return ConversationHandler.END
        # Clear user data to start fresh
        context.user_data.clear()
        # Get list of categories from topics.json
        categories = list(self.topics['categories'].keys())
        # Create keyboard buttons for categories
        buttons = [[cat] for cat in categories]
        if self.is_other_allowed:
            # Add 'Other' option if allowed
            buttons.append([self.other_option])
        # Add PANIC option
        buttons.append([self.panic_option])
        logger.debug(f"Generated start keyboard: {buttons}")
        print(f"Generated start keyboard with {len(buttons)} options")
        # Send welcome message with category selection
        await update.message.reply_text(
            "Üdvözöljük az ÉPC Informatikai hibabejelentő felületén! \n\n"
            "Felhívjuk figyelmét, hogy minden tevékenységet figyelünk a visszaélések elkerülése érdekében. \n\n"
            "Milyen típusú problémát tapasztal? Sürgős esetekben válassza a 'PANIC' opciót.",
            reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True)
        )
        # Log execution time
        logger.debug(f"start method took {(datetime.now() - start_time).total_seconds()} seconds")
        print(f"start method completed in {(datetime.now() - start_time).total_seconds()} seconds")
        # Transition to CATEGORY state
        return States.CATEGORY.value

    async def category(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        category = update.message.text.lower().strip()
        logger.info(f"Received category from user {user_id}: {category}")
        print(f"User {user_id} selected category: {category}")

        if category == self.panic_option.lower():
            print(f"User {user_id} triggered PANIC in category")
            return await self.panic(update, context)

        if category in self.topics['categories'] or (self.is_other_allowed and category == "other"):
            context.user_data['category'] = category
            if category == "other":
                context.user_data['team'] = "general team"
                context.user_data['component'] = "other"
                context.user_data['issue'] = "other"
                context.user_data['issue_id'] = "other"
                context.user_data['is_other_selected'] = True
                logger.debug(f"User {user_id} selected 'other' category")
                print(f"User {user_id} selected 'other' category")
                keyboard = [[c['name']] for c in self.locations['campuses']]
                if self.is_other_allowed:
                    keyboard.append([self.other_option])
                keyboard.append([self.panic_option])
                await update.message.reply_text(
                    self.locations['prompts']['campus']['hu'],
                    reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
                )
                print(f"Transitioning to CAMPUS state for user {user_id}")
                return States.CAMPUS.value
            context.user_data['team'] = self.topics['categories'][category]['team']
            components = list(self.topics['categories'][category]['options'].keys())
            buttons = [[self.topics['categories'][category]['options'][comp].get('display_name', comp)] for comp in components]
            if self.is_other_allowed:
                buttons.append([self.other_option])
            buttons.append([self.panic_option])
            reply_markup = ReplyKeyboardMarkup(buttons, one_time_keyboard=True)
            await update.message.reply_text(
                self.topics['categories'][category]['prompt'],
                reply_markup=reply_markup
            )
            print(f"Transitioning to COMPONENT state for user {user_id}")
            return States.COMPONENT.value

        buttons = [[cat] for cat in self.topics['categories'].keys()]
        if self.is_other_allowed:
            buttons.append([self.other_option])
        buttons.append([self.panic_option])
        await update.message.reply_text(
            f"Érvénytelen kategória. Kérem, válasszon egyet: {', '.join(self.topics['categories'].keys())}",
            reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True)
        )
        print(f"Invalid category input from user {user_id}, staying in CATEGORY state")
        return States.CATEGORY.value

    async def component(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        component = update.message.text.strip()
        category = context.user_data.get('category')
        logger.info(f"Received component from user {user_id}: {component}")
        print(f"User {user_id} selected component: {component}")

        if not category or category not in self.topics['categories']:
            logger.error(f"Invalid or missing category: {category}")
            print(f"ERROR: Invalid or missing category {category} for user {user_id}")
            context.user_data.pop('category', None)
            buttons = [[cat] for cat in self.topics['categories'].keys()]
            if self.is_other_allowed:
                buttons.append([self.other_option])
            buttons.append([self.panic_option])
            await update.message.reply_text(
                "Hiba: Kérem, válasszon egy kategóriát újra.",
                reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True)
            )
            print(f"Missing category, redirecting user {user_id} to CATEGORY state")
            return States.CATEGORY.value

        if component.lower() == self.panic_option.lower():
            print(f"User {user_id} triggered PANIC in component")
            return await self.panic(update, context)

        options = self.topics['categories'][category]['options']
        components = {(options[comp].get('display_name', comp)).lower(): comp for comp in options.keys()}
        if self.is_other_allowed and component.lower() == "other":
            context.user_data['component'] = "other"
            context.user_data['issue'] = f"{category} - Other"
            context.user_data['issue_id'] = "other"
            context.user_data['is_other_selected'] = True
            logger.debug(f"User {user_id} selected 'other' component")
            print(f"User {user_id} selected 'other' component")
            keyboard = [[c['name']] for c in self.locations['campuses']]
            if self.is_other_allowed:
                keyboard.append([self.other_option])
            keyboard.append([self.panic_option])
            await update.message.reply_text(
                self.locations['prompts']['campus']['hu'],
                reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            )
            print(f"Transitioning to CAMPUS state for user {user_id}")
            return States.CAMPUS.value

        if component.lower() in components:
            original_comp = components[component.lower()]
            context.user_data['component'] = original_comp
            issues = options[original_comp]['options']
            issue_keys = list(issues.keys())
            if self.is_other_allowed:
                issue_keys.append("other")
            keyboard = [[f"{issues.get(k, {}).get('description', k)} ({k})"] if k != "other" else ["Other"] for k in issue_keys] + [[self.panic_option]]
            await update.message.reply_text(
                options[original_comp]['prompt'],
                reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            )
            print(f"Transitioning to ISSUE state for user {user_id}")
            return States.ISSUE.value

        buttons = [[options[comp].get('display_name', comp)] for comp in options.keys()]
        if self.is_other_allowed:
            buttons.append(["Other"])
        buttons.append([self.panic_option])
        display_names = [options[comp].get('display_name', comp) for comp in options.keys()]
        if self.is_other_allowed:
            display_names.append("Other")
        await update.message.reply_text(
            f"Érvénytelen komponens. Kérem, válasszon egyet: {', '.join(display_names)}",
            reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True)
        )
        print(f"Invalid component input from user {user_id}, staying in COMPONENT state")
        return States.COMPONENT.value

    async def issue(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        issue = update.message.text.strip()
        category = context.user_data.get('category')
        component = context.user_data.get('component')
        logger.info(f"Received issue from user {user_id}: {issue}")
        print(f"User {user_id} selected issue: {issue}")

        if issue.lower() == self.panic_option.lower():
            print(f"User {user_id} triggered PANIC in issue")
            return await self.panic(update, context)

        try:
            issues = self.topics['categories'][category]['options'][component]['options']
        except KeyError as e:
            logger.error(f"KeyError in issue selection: {str(e)}, category: {category}, component: {component}")
            print(f"ERROR: KeyError in issue selection for user {user_id}: {str(e)}")
            await update.message.reply_text(
                "Hiba történt a probléma kiválasztása során. Kérem, kezdje újra.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END

        issue_id = next((k for k, v in issues.items() if issue.endswith(f" ({k})")), None)
        if self.is_other_allowed and issue.lower() == "other":
            display_name = self.topics['categories'][category]['options'][component].get('display_name', component)
            context.user_data['issue'] = f"{display_name} - Other"
            context.user_data['issue_id'] = "other"
            context.user_data['is_other_selected'] = True
            logger.debug(f"User {user_id} selected 'other' issue")
            print(f"User {user_id} selected 'other' issue")
            keyboard = [[c['name']] for c in self.locations['campuses']]
            if self.is_other_allowed:
                keyboard.append([self.other_option])
            keyboard.append([self.panic_option])
            await update.message.reply_text(
                self.locations['prompts']['campus']['hu'],
                reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            )
            print(f"Transitioning to CAMPUS state for user {user_id}")
            return States.CAMPUS.value

        if issue_id:
            display_name = self.topics['categories'][category]['options'][component].get('display_name', component)
            issue_description = issues[issue_id]['description']
            context.user_data['issue'] = f"{display_name} - {issue_description}"
            context.user_data['issue_id'] = issue_id
            keyboard = [[c['name']] for c in self.locations['campuses']]
            if self.is_other_allowed:
                keyboard.append([self.other_option])
            keyboard.append([self.panic_option])
            logger.debug(f"Generated campus keyboard: {keyboard}")
            print(f"Generated campus keyboard for user {user_id}")
            await update.message.reply_text(
                self.locations['prompts']['campus']['hu'],
                reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            )
            print(f"Transitioning to CAMPUS state for user {user_id}")
            return States.CAMPUS.value

        issue_keys = list(issues.keys())
        if self.is_other_allowed:
            issue_keys.append("other")
        keyboard = [[f"{issues.get(k, {}).get('description', k)} ({k})"] if k != "other" else ["Other"] for k in issue_keys] + [[self.panic_option]]
        await update.message.reply_text(
            f"Érvénytelen probléma. Kérem, válasszon egyet:",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )
        print(f"Invalid issue input from user {user_id}, staying in ISSUE state")
        return States.ISSUE.value

    async def campus(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        campus = update.message.text.strip()
        logger.info(f"Received campus from user {user_id}: {campus}")
        print(f"User {user_id} selected campus: {campus}")
        logger.debug(f"Available campuses: {[c['name'] for c in self.locations['campuses']]}")

        if campus.lower() == self.panic_option.lower():
            logger.debug(f"User {user_id} selected PANIC in campus")
            print(f"User {user_id} triggered PANIC in campus")
            return await self.panic(update, context)

        try:
            campuses = [c['name'] for c in self.locations['campuses']]
        except KeyError as e:
            logger.error(f"KeyError in campus data: {str(e)}")
            print(f"ERROR: KeyError in campus data for user {user_id}: {str(e)}")
            await update.message.reply_text(
                "Hiba történt a kampusz adatok betöltése során. Kérem, próbálja újra vagy válassza a 'PANIC' opciót.",
                reply_markup=ReplyKeyboardMarkup([[self.panic_option]], one_time_keyboard=True)
            )
            return ConversationHandler.END

        if self.is_other_allowed and campus.lower() == "other":
            context.user_data['is_other_location'] = True
            logger.debug(f"User {user_id} selected 'other' location")
            print(f"User {user_id} selected 'other' location in campus")
            await update.message.reply_text(
                self.locations['prompts']['address']['hu'],
                reply_markup=ReplyKeyboardRemove()
            )
            print(f"Transitioning to ADDRESS state for user {user_id}")
            return States.ADDRESS.value

        if campus in campuses:
            context.user_data['campus'] = campus
            try:
                buildings = [b['name'] for b in next(c['buildings'] for c in self.locations['campuses'] if c['name'] == campus)]
                keyboard = [[b] for b in buildings]
                if self.is_other_allowed:
                    keyboard.append([self.other_option])
                keyboard.append([self.panic_option])
                logger.debug(f"Generated building keyboard for campus {campus}: {keyboard}")
                print(f"Generated building keyboard for user {user_id}")
                await update.message.reply_text(
                    self.locations['prompts']['building']['hu'],
                    reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
                )
                print(f"Transitioning to BUILDING state for user {user_id}")
                return States.BUILDING.value
            except StopIteration:
                logger.error(f"No buildings found for campus: {campus}")
                print(f"ERROR: No buildings found for campus {campus} for user {user_id}")
                await update.message.reply_text(
                    f"Hiba: Nincs épület definiálva a {campus} kampuszhoz. Kérem, lépjen kapcsolatba az IT-val.",
                    reply_markup=ReplyKeyboardMarkup([[self.panic_option]], one_time_keyboard=True)
                )
                return ConversationHandler.END
            except KeyError as e:
                logger.error(f"KeyError in building data: {str(e)}")
                print(f"ERROR: KeyError in building data for user {user_id}: {str(e)}")
                await update.message.reply_text(
                    "Hiba történt az épület adatok betöltése során. Kérem, próbálja újra vagy válassza a 'PANIC' opciót.",
                    reply_markup=ReplyKeyboardMarkup([[self.panic_option]], one_time_keyboard=True)
                )
                return ConversationHandler.END

        keyboard = [[c['name']] for c in self.locations['campuses']]
        if self.is_other_allowed:
            keyboard.append([self.other_option])
        keyboard.append([self.panic_option])
        logger.debug(f"Generated campus error keyboard: {keyboard}")
        print(f"Invalid campus input from user {user_id}, staying in CAMPUS state")
        await update.message.reply_text(
            f"Érvénytelen kampusz. {self.locations['prompts']['campus']['hu']}",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )
        return States.CAMPUS.value

    async def building(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        building = update.message.text.strip()
        logger.info(f"Received building from user {user_id}: {building}")
        print(f"User {user_id} selected building: {building}")
        campus = context.user_data.get('campus')
        logger.debug(f"Processing building for campus: {campus}")

        if not campus:
            logger.error(f"Missing campus in user data for user {user_id}")
            print(f"ERROR: Missing campus for user {user_id}")
            await update.message.reply_text(
                "Hiba: Kampusz adat hiányzik. Kérem, kezdje újra.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END

        if building.lower() == self.panic_option.lower():
            logger.debug(f"User {user_id} selected PANIC in building")
            print(f"User {user_id} triggered PANIC in building")
            return await self.panic(update, context)

        try:
            buildings = next(c['buildings'] for c in self.locations['campuses'] if c['name'] == campus)
            building_names = [b['name'] for b in buildings]
            logger.debug(f"Available buildings for campus {campus}: {building_names}")
        except StopIteration:
            logger.error(f"No buildings found for campus: {campus}")
            print(f"ERROR: No buildings found for campus {campus} for user {user_id}")
            await update.message.reply_text(
                f"Hiba: Nincs épület definiálva a {campus} kampuszhoz. Kérem, lépjen kapcsolatba az IT-val.",
                reply_markup=ReplyKeyboardMarkup([[self.panic_option]], one_time_keyboard=True)
            )
            return ConversationHandler.END
        except KeyError as e:
            logger.error(f"KeyError in building data: {str(e)}")
            print(f"ERROR: KeyError in building data for user {user_id}: {str(e)}")
            await update.message.reply_text(
                "Hiba történt az épület adatok betöltése során. Kérem, próbálja újra vagy válassza a 'PANIC' opciót.",
                reply_markup=ReplyKeyboardMarkup([[self.panic_option]], one_time_keyboard=True)
            )
            return ConversationHandler.END

        if self.is_other_allowed and building.lower() == "other":
            context.user_data['is_other_location'] = True
            logger.debug(f"User {user_id} selected 'other' location in building")
            print(f"User {user_id} selected 'other' location in building")
            await update.message.reply_text(
                self.locations['prompts']['address']['hu'],
                reply_markup=ReplyKeyboardRemove()
            )
            print(f"Transitioning to ADDRESS state for user {user_id}")
            return States.ADDRESS.value

        if building in building_names:
            context.user_data['building'] = building
            try:
                floors = [f['name'] for f in next(b['floors'] for b in buildings if b['name'] == building)]
                keyboard = [[f] for f in floors]
                if self.is_other_allowed:
                    keyboard.append([self.other_option])
                keyboard.append([self.panic_option])
                logger.debug(f"Generated floor keyboard for building {building}: {keyboard}")
                print(f"Generated floor keyboard for user {user_id}")
                await update.message.reply_text(
                    self.locations['prompts']['floor']['hu'],
                    reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
                )
                print(f"Transitioning to FLOOR state for user {user_id}")
                return States.FLOOR.value
            except StopIteration:
                logger.error(f"No floors found for building: {building}")
                print(f"ERROR: No floors found for building {building} for user {user_id}")
                await update.message.reply_text(
                    f"Hiba: Nincs emelet definiálva a {building} épülethez. Kérem, lépjen kapcsolatba az IT-val.",
                    reply_markup=ReplyKeyboardMarkup([[self.panic_option]], one_time_keyboard=True)
                )
                return ConversationHandler.END
            except KeyError as e:
                logger.error(f"KeyError in floor data: {str(e)}")
                print(f"ERROR: KeyError in floor data for user {user_id}: {str(e)}")
                await update.message.reply_text(
                    "Hiba történt az emelet adatok betöltése során. Kérem, próbálja újra vagy válassza a 'PANIC' opciót.",
                    reply_markup=ReplyKeyboardMarkup([[self.panic_option]], one_time_keyboard=True)
                )
                return ConversationHandler.END

        keyboard = [[b] for b in building_names]
        if self.is_other_allowed:
            keyboard.append([self.other_option])
        keyboard.append([self.panic_option])
        logger.debug(f"Generated building error keyboard: {keyboard}")
        print(f"Invalid building input from user {user_id}, staying in BUILDING state")
        await update.message.reply_text(
            f"Érvénytelen épület. {self.locations['prompts']['building']['hu']}",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )
        return States.BUILDING.value

    async def floor(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        floor = update.message.text.strip()
        logger.info(f"Received floor from user {user_id}: {floor}")
        print(f"User {user_id} selected floor: {floor}")
        campus = context.user_data.get('campus')
        building = context.user_data.get('building')
        logger.debug(f"Processing floor for campus: {campus}, building: {building}")

        if not campus or not building:
            logger.error(f"Missing campus or building in user data for user {user_id}: campus={campus}, building={building}")
            print(f"ERROR: Missing campus or building for user {user_id}")
            await update.message.reply_text(
                "Hiba: Kampusz vagy épület adat hiányzik. Kérem, kezdje újra.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END

        if floor.lower() == self.panic_option.lower():
            logger.debug(f"User {user_id} selected PANIC in floor")
            print(f"User {user_id} triggered PANIC in floor")
            return await self.panic(update, context)

        try:
            buildings = next(c['buildings'] for c in self.locations['campuses'] if c['name'] == campus)
            floors = next(b['floors'] for b in buildings if b['name'] == building)
            floor_names = [f['name'] for f in floors]
            logger.debug(f"Available floors for building {building}: {floor_names}")
        except StopIteration:
            logger.error(f"No floors found for building: {building}")
            print(f"ERROR: No floors found for building {building} for user {user_id}")
            await update.message.reply_text(
                f"Hiba: Nincs emelet definiálva a {building} épülethez. Kérem, lépjen kapcsolatba az IT-val.",
                reply_markup=ReplyKeyboardMarkup([[self.panic_option]], one_time_keyboard=True)
            )
            return ConversationHandler.END
        except KeyError as e:
            logger.error(f"KeyError in floor data: {str(e)}")
            print(f"ERROR: KeyError in floor data for user {user_id}: {str(e)}")
            await update.message.reply_text(
                "Hiba történt az emelet adatok betöltése során. Kérem, próbálja újra vagy válassza a 'PANIC' opciót.",
                reply_markup=ReplyKeyboardMarkup([[self.panic_option]], one_time_keyboard=True)
            )
            return ConversationHandler.END

        if self.is_other_allowed and floor.lower() == "other":
            context.user_data['is_other_location'] = True
            logger.debug(f"User {user_id} selected 'other' location in floor")
            print(f"User {user_id} selected 'other' location in floor")
            await update.message.reply_text(
                self.locations['prompts']['address']['hu'],
                reply_markup=ReplyKeyboardRemove()
            )
            print(f"Transitioning to ADDRESS state for user {user_id}")
            return States.ADDRESS.value

        if floor in floor_names:
            context.user_data['floor'] = floor
            try:
                departments = [d['name'] for d in next(f['departments'] for f in floors if f['name'] == floor)]
                keyboard = [[d] for d in departments]
                if self.is_other_allowed:
                    keyboard.append([self.other_option])
                keyboard.append([self.panic_option])
                logger.debug(f"Generated department keyboard for floor {floor}: {keyboard}")
                print(f"Generated department keyboard for user {user_id}")
                await update.message.reply_text(
                    self.locations['prompts']['department']['hu'],
                    reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
                )
                print(f"Transitioning to DEPARTMENT state for user {user_id}")
                return States.DEPARTMENT.value
            except StopIteration:
                logger.error(f"No departments found for floor: {floor}")
                print(f"ERROR: No departments found for floor {floor} for user {user_id}")
                await update.message.reply_text(
                    f"Hiba: Nincs osztály definiálva a {floor} emelethez. Kérem, lépjen kapcsolatba az IT-val.",
                    reply_markup=ReplyKeyboardMarkup([[self.panic_option]], one_time_keyboard=True)
                )
                return ConversationHandler.END
            except KeyError as e:
                logger.error(f"KeyError in department data: {str(e)}")
                print(f"ERROR: KeyError in department data for user {user_id}: {str(e)}")
                await update.message.reply_text(
                    "Hiba történt az osztály adatok betöltése során. Kérem, próbálja újra vagy válassza a 'PANIC' opciót.",
                    reply_markup=ReplyKeyboardMarkup([[self.panic_option]], one_time_keyboard=True)
                )
                return ConversationHandler.END

        keyboard = [[f] for f in floor_names]
        if self.is_other_allowed:
            keyboard.append([self.other_option])
        keyboard.append([self.panic_option])
        logger.debug(f"Generated floor error keyboard: {keyboard}")
        print(f"Invalid floor input from user {user_id}, staying in FLOOR state")
        await update.message.reply_text(
            f"Érvénytelen emelet. {self.locations['prompts']['floor']['hu']}",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )
        return States.FLOOR.value

    async def department(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        department = update.message.text.strip()
        logger.info(f"Received department from user {user_id}: {department}")
        print(f"User {user_id} selected department: {department}")
        campus = context.user_data.get('campus')
        building = context.user_data.get('building')
        floor = context.user_data.get('floor')
        logger.debug(f"Processing department for campus: {campus}, building: {building}, floor: {floor}")

        if not campus or not building or not floor:
            logger.error(f"Missing campus, building, or floor in user data for user {user_id}: campus={campus}, building={building}, floor={floor}")
            print(f"ERROR: Missing campus, building, or floor for user {user_id}")
            await update.message.reply_text(
                "Hiba: Kampusz, épület vagy emelet adat hiányzik. Kérem, kezdje újra.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END

        if department.lower() == self.panic_option.lower():
            logger.debug(f"User {user_id} selected PANIC in department")
            print(f"User {user_id} triggered PANIC in department")
            return await self.panic(update, context)

        try:
            buildings = next(c['buildings'] for c in self.locations['campuses'] if c['name'] == campus)
            floors = next(b['floors'] for b in buildings if b['name'] == building)
            departments = next(f['departments'] for f in floors if f['name'] == floor)
            department_names = [d['name'] for d in departments]
            logger.debug(f"Available departments for floor {floor}: {department_names}")
        except StopIteration:
            logger.error(f"No departments found for floor: {floor}")
            print(f"ERROR: No departments found for floor {floor} for user {user_id}")
            await update.message.reply_text(
                f"Hiba: Nincs osztály definiálva a {floor} emelethez. Kérem, lépjen kapcsolatba az IT-val.",
                reply_markup=ReplyKeyboardMarkup([[self.panic_option]], one_time_keyboard=True)
            )
            return ConversationHandler.END
        except KeyError as e:
            logger.error(f"KeyError in department data: {str(e)}")
            print(f"ERROR: KeyError in department data for user {user_id}: {str(e)}")
            await update.message.reply_text(
                "Hiba történt az osztály adatok betöltése során. Kérem, próbálja újra vagy válassza a 'PANIC' opciót.",
                reply_markup=ReplyKeyboardMarkup([[self.panic_option]], one_time_keyboard=True)
            )
            return ConversationHandler.END

        if department in department_names:
            context.user_data['department'] = department
            await update.message.reply_text(
                self.locations['prompts']['room']['hu'],
                reply_markup=ReplyKeyboardRemove()
            )
            print(f"Transitioning to ROOM state for user {user_id}")
            return States.ROOM.value

        keyboard = [[d] for d in department_names]
        if self.is_other_allowed:
            keyboard.append([self.other_option])
        keyboard.append([self.panic_option])
        logger.debug(f"Generated department error keyboard: {keyboard}")
        print(f"Invalid department input from user {user_id}, staying in DEPARTMENT state")
        await update.message.reply_text(
            f"Érvénytelen osztály. {self.locations['prompts']['department']['hu']}",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )
        return States.DEPARTMENT.value

    async def room(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        room = update.message.text.strip()
        logger.info(f"Received room from user {user_id}: {room}")
        print(f"User {user_id} entered room: {room}")

        try:
            room_regex = self.locations['validation']['room']
        except KeyError as e:
            logger.error(f"KeyError in room validation regex: {str(e)}")
            print(f"ERROR: KeyError in room validation regex for user {user_id}: {str(e)}")
            await update.message.reply_text(
                "Hiba történt a szoba validáció során. Kérem, lépjen kapcsolatba az IT-val.",
                reply_markup=ReplyKeyboardMarkup([[self.panic_option]], one_time_keyboard=True)
            )
            return ConversationHandler.END

        if re.match(room_regex, room):
            context.user_data['room'] = room
            keyboard = [[KeyboardButton("Hely megosztása", request_location=True)], ["Kihagy"]]
            logger.debug(f"Generated geolocation keyboard: {keyboard}")
            print(f"Generated geolocation keyboard for user {user_id}")
            await update.message.reply_text(
                self.locations['prompts']['geolocation']['hu'],
                reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            )
            print(f"Transitioning to GEOLOCATION state for user {user_id}")
            return States.GEOLOCATION.value

        logger.debug(f"Invalid room input: {room}, expected format: {room_regex}")
        print(f"Invalid room input from user {user_id}: {room}")
        await update.message.reply_text(
            "Érvénytelen szoba szám. Kérem, adjon meg egy érvényes szoba vagy iroda számot (pl. 204-es szoba).",
            reply_markup=ReplyKeyboardRemove()
        )
        return States.ROOM.value

    async def address(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        address = update.message.text.strip()
        logger.info(f"Received address from user {user_id}: {address}")
        print(f"User {user_id} entered address: {address}")

        if len(address) > self.max_address_length:
            logger.warning(f"Address too long from user {user_id}: {len(address)} characters")
            print(f"WARNING: Address too long from user {user_id}: {len(address)} characters")
            await update.message.reply_text(
                f"A cím túl hosszú (max. {self.max_address_length} karakter). Kérem, rövidebben fogalmazza meg.",
                reply_markup=ReplyKeyboardRemove()
            )
            return States.ADDRESS.value

        if not address:
            logger.warning(f"User {user_id} provided empty address for 'Other' location")
            print(f"WARNING: Empty address from user {user_id} for 'Other' location")
            ticket_data = {
                'category': context.user_data.get('category', 'N/A'),
                'component': context.user_data.get('component', 'N/A'),
                'issue': context.user_data.get('issue', 'N/A'),
                'description': context.user_data.get('description', 'N/A'),
                'team': context.user_data.get('team', 'N/A'),
                'address': address or 'Empty',
                'campus': context.user_data.get('campus', 'N/A'),
                'building': context.user_data.get('building', 'N/A'),
                'floor': context.user_data.get('floor', 'N/A'),
                'department': context.user_data.get('department', 'N/A'),
                'room': context.user_data.get('room', 'N/A'),
                'latitude': context.user_data.get('latitude', None),
                'longitude': context.user_data.get('longitude', None),
                'media': context.user_data.get('media', None),
                'name': context.user_data.get('name', 'N/A'),
                'phone': context.user_data.get('phone', 'N/A')
            }
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'user_id': user_id,
                'address': address or 'Empty',
                'ticket_data': ticket_data,
                'reason': 'Invalid address for Other location'
            }
            with abuse_file_lock:
                try:
                    with open('/app/logs/abuse_attempts.txt', 'a', encoding='utf-8') as f:
                        f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
                    logger.info(f"Logged abuse attempt for user {user_id}: Invalid address for Other")
                    print(f"Logged abuse attempt for user {user_id}: Invalid address for Other")
                except Exception as e:
                    logger.error(f"Failed to log abuse attempt for user {user_id}: {str(e)}")
                    print(f"ERROR: Failed to log abuse attempt for user {user_id}: {str(e)}")
            self.block_user(user_id, reason="Invalid address for Other location", ticket_data=ticket_data)
            await update.message.reply_text(
                "A cím megadása kötelező, ha az 'Egyéb' opciót választotta. Kérem, adja meg a pontos címet.",
                reply_markup=ReplyKeyboardRemove()
            )
            return States.ADDRESS.value

        context.user_data['address'] = address
        keyboard = [[KeyboardButton("Hely megosztása", request_location=True)], ["Kihagy"]]
        logger.debug(f"Generated geolocation keyboard: {keyboard}")
        print(f"Generated geolocation keyboard for user {user_id}")
        await update.message.reply_text(
            self.locations['prompts']['geolocation']['hu'],
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )
        print(f"Transitioning to GEOLOCATION state for user {user_id}")
        return States.GEOLOCATION.value

    async def geolocation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        logger.info(f"Processing geolocation for user {user_id}")
        print(f"Processing geolocation for user {user_id}")

        if update.message.text:
            text = unicodedata.normalize('NFKC', update.message.text.strip()).lower()
            if text == "kihagy":
                logger.info(f"User {user_id} skipped geolocation")
                print(f"User {user_id} skipped geolocation")
                context.user_data['latitude'] = None
                context.user_data['longitude'] = None
                await update.message.reply_text(
                    "Adja meg a nevét:",
                    reply_markup=ReplyKeyboardRemove()
                )
                print(f"Transitioning to NAME state for user {user_id}")
                return States.NAME.value

        if update.message.location:
            location = update.message.location
            logger.info(f"Received geolocation from user {user_id}: ({location.latitude}, {location.longitude})")
            print(f"User {user_id} shared geolocation: ({location.latitude}, {location.longitude})")
            context.user_data['latitude'] = location.latitude
            context.user_data['longitude'] = location.longitude
            await update.message.reply_text(
                "Adja meg a nevét:",
                reply_markup=ReplyKeyboardRemove()
            )
            print(f"Transitioning to NAME state for user {user_id}")
            return States.NAME.value

        keyboard = [[KeyboardButton("Hely megosztása", request_location=True)], ["Kihagy"]]
        logger.debug(f"Generated geolocation error keyboard: {keyboard}")
        print(f"Invalid geolocation input from user {user_id}, staying in GEOLOCATION state")
        await update.message.reply_text(
            "OPCIONÁLIS: Kérem, ossza meg a hiba pontos helyszínét, vagy válassza a 'Kihagy' opciót.",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )
        return States.GEOLOCATION.value

    async def name(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        context.user_data['name'] = update.message.text.strip()
        logger.info(f"Received name from user {user_id}: {context.user_data['name']}")
        print(f"User {user_id} entered name: {context.user_data['name']}")
        keyboard = [[KeyboardButton("Kapcsolat megosztása", request_contact=True)]]
        await update.message.reply_text(
            "Kérem adja meg a mellékét vagy a telefonszámát (vagy használja a kapcsolat megosztás opcióját):",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )
        print(f"Transitioning to PHONE state for user {user_id}")
        return States.PHONE.value

    async def phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        if update.message.contact:
            context.user_data['phone'] = update.message.contact.phone_number
        else:
            context.user_data['phone'] = update.message.text.strip()
        logger.info(f"Received phone from user {user_id}: {context.user_data['phone']}")
        print(f"User {user_id} entered phone: {context.user_data['phone']}")
        keyboard = [["Kihagy"]] if not context.user_data.get('is_other_selected') else []
        prompt = "Kérem, adja meg a probléma részletes leírását:" if context.user_data.get('is_other_selected') else \
                 "OPCIONÁLIS: Adjon meg további részleteket (vagy nyomja meg a 'Kihagy' gombot a folytatáshoz):"
        await update.message.reply_text(
            prompt,
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True) if keyboard else ReplyKeyboardRemove()
        )
        print(f"Transitioning to DESCRIPTION state for user {user_id}")
        return States.DESCRIPTION.value

    async def description(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        description = update.message.text.strip()
        logger.info(f"Received description from user {user_id}: {description}")
        print(f"User {user_id} entered description: {description}")

        if description and len(description) > self.max_description_length:
            logger.warning(f"Description too long from user {user_id}: {len(description)} characters")
            print(f"WARNING: Description too long from user {user_id}: {len(description)} characters")
            keyboard = [["Kihagy"]] if not context.user_data.get('is_other_selected') else []
            await update.message.reply_text(
                f"A leírás túl hosszú (max. {self.max_description_length} karakter). Kérem, rövidebben fogalmazza meg.",
                reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True) if keyboard else ReplyKeyboardRemove()
            )
            return States.DESCRIPTION.value

        if context.user_data.get('is_other_selected'):
            if not description or description.strip().lower() == "kihagy":
                logger.warning(f"User {user_id} provided empty or 'Kihagy' description for 'Other' selection")
                print(f"WARNING: Invalid description for 'Other' from user {user_id}")
                ticket_data = {
                    'category': context.user_data.get('category', 'N/A'),
                    'component': context.user_data.get('component', 'N/A'),
                    'issue': context.user_data.get('issue', 'N/A'),
                    'description': description or 'Empty',
                    'team': context.user_data.get('team', 'N/A'),
                    'address': context.user_data.get('address', 'N/A'),
                    'campus': context.user_data.get('campus', 'N/A'),
                    'building': context.user_data.get('building', 'N/A'),
                    'floor': context.user_data.get('floor', 'N/A'),
                    'department': context.user_data.get('department', 'N/A'),
                    'room': context.user_data.get('room', 'N/A'),
                    'latitude': context.user_data.get('latitude', None),
                    'longitude': context.user_data.get('longitude', None),
                    'media': context.user_data.get('media', None),
                    'name': context.user_data.get('name', 'N/A'),
                    'phone': context.user_data.get('phone', 'N/A')
                }
                log_entry = {
                    'timestamp': datetime.now().isoformat(),
                    'user_id': user_id,
                    'description': description or 'Empty',
                    'ticket_data': ticket_data,
                    'reason': 'Invalid description for Other selection'
                }
                with abuse_file_lock:
                    try:
                        with open('/app/logs/abuse_attempts.txt', 'a', encoding='utf-8') as f:
                            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
                        logger.info(f"Logged abuse attempt for user {user_id}: Invalid description for Other")
                        print(f"Logged abuse attempt for user {user_id}: Invalid description for Other")
                    except Exception as e:
                        logger.error(f"Failed to log abuse attempt for user {user_id}: {str(e)}")
                        print(f"ERROR: Failed to log abuse attempt for user {user_id}: {str(e)}")
                self.block_user(user_id, reason="Invalid description for Other selection", ticket_data=ticket_data)
                await update.message.reply_text(
                    "A probléma leírása kötelező, ha az 'Egyéb' opciót választotta. Kérem, írja le a hiba részleteit.",
                    reply_markup=ReplyKeyboardRemove()
                )
                return States.DESCRIPTION.value
            context.user_data['description'] = description
        else:
            if description:
                text = unicodedata.normalize('NFKC', description.strip()).lower()
                if text == "kihagy":
                    context.user_data['description'] = 'Nincs további részlet megadva'
                else:
                    context.user_data['description'] = description
            else:
                context.user_data['description'] = 'Nincs további részlet megadva'

        keyboard = [["Kihagy"]]
        await update.message.reply_text(
            self.locations['prompts']['media']['hu'],
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )
        print(f"Transitioning to MEDIA state for user {user_id}")
        return States.MEDIA.value

    async def media(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        logger.info(f"Processing media for user {user_id}")
        print(f"Processing media for user {user_id}")

        if update.message.text:
            text = unicodedata.normalize('NFKC', update.message.text.strip()).lower()
            if text == "kihagy":
                logger.info(f"User {user_id} skipped media upload")
                print(f"User {user_id} skipped media upload")
                context.user_data['media'] = None
                await update.message.reply_text(
                    "Kérem, adja meg email címét:\n",
                    reply_markup=ReplyKeyboardRemove()
                )
                print(f"Transitioning to AUTH state for user {user_id}")
                return States.AUTH.value

        if update.message.photo or update.message.video:
            media = update.message.photo[-1] if update.message.photo else update.message.video
            file_size = media.file_size
            if file_size > self.max_media_size:
                logger.warning(f"Media file too large from user {user_id}: {file_size} bytes")
                print(f"WARNING: Media file too large from user {user_id}: {file_size} bytes")
                keyboard = [["Kihagy"]]
                await update.message.reply_text(
                    f"A fájl túl nagy (max. 20MB, kapott {file_size // 1_000_000}MB). Kérem, töltsön fel kisebb fájlt vagy nyomja meg a Kihagy gombot.",
                    reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
                )
                return States.MEDIA.value

            try:
                file = await context.bot.get_file(media.file_id)
                ext = '.jpg' if update.message.photo else '.mp4'
                file_path = f"/app/tmp/{user_id}_{datetime.now().strftime('%Y%m%dT%H%M%S')}{ext}"
                await asyncio.wait_for(file.download_to_drive(file_path), timeout=10.0)
                context.user_data['media'] = file_path
                logger.info(f"Media file downloaded for user {user_id}: {file_path}")
                print(f"Media file downloaded for user {user_id}: {file_path}")
                await update.message.reply_text(
                    "Kérem, adja meg email címét:\n",
                    reply_markup=ReplyKeyboardRemove()
                )
                print(f"Transitioning to AUTH state for user {user_id}")
                return States.AUTH.value

            except asyncio.TimeoutError:
                logger.error(f"Media download timed out for user {user_id}")
                print(f"ERROR: Media download timed out for user {user_id}")
                keyboard = [["Kihagy"]]
                await update.message.reply_text(
                    "A tartalom feltöltése időtúllépés miatt nem sikerült. Kérem, próbálja újra vagy nyomja meg a Kihagy gombot.",
                    reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
                )
                return States.MEDIA.value

            except Exception as e:
                logger.error(f"Failed to download media for user {user_id}: {str(e)}")
                print(f"ERROR: Failed to download media for user {user_id}: {str(e)}")
                keyboard = [["Kihagy"]]
                await update.message.reply_text(
                    "Nem sikerült a tartalom feldolgozása. Kérem, próbálja újra vagy nyomja meg a Kihagy gombot.",
                    reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
                )
                return States.MEDIA.value

        keyboard = [["Kihagy"]]
        await update.message.reply_text(
            "OPCIONÁLIS: Kérem, töltsön fel egy képet vagy videót (max. 20MB), vagy nyomja meg a Kihagy gombot.",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )
        print(f"Invalid media input from user {user_id}, staying in MEDIA state")
        return States.MEDIA.value

    async def auth(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        email = update.message.text.strip()
        logger.info(f"Received authentication email from user {user_id}: {email}")
        print(f"User {user_id} entered email: {email}")

        if not re.match(r'^[\w\.-]+@teszt-domain\.com$', email):
            logger.warning(f"Invalid email format from user {user_id}: {email}")
            print(f"WARNING: Invalid email format from user {user_id}: {email}")
            ticket_data = {
                'category': context.user_data.get('category', 'N/A'),
                'component': context.user_data.get('component', 'N/A'),
                'issue': context.user_data.get('issue', 'N/A'),
                'description': context.user_data.get('description', 'N/A'),
                'team': context.user_data.get('team', 'N/A'),
                'address': context.user_data.get('address', 'N/A'),
                'campus': context.user_data.get('campus', 'N/A'),
                'building': context.user_data.get('building', 'N/A'),
                'floor': context.user_data.get('floor', 'N/A'),
                'department': context.user_data.get('department', 'N/A'),
                'room': context.user_data.get('room', 'N/A'),
                'latitude': context.user_data.get('latitude', None),
                'longitude': context.user_data.get('longitude', None),
                'media': context.user_data.get('media', None),
                'name': context.user_data.get('name', 'N/A'),
                'phone': context.user_data.get('phone', 'N/A')
            }
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'user_id': user_id,
                'email': email,
                'ticket_data': ticket_data
            }
            with abuse_file_lock:
                try:
                    with open('/app/logs/abuse_attempts.txt', 'a', encoding='utf-8') as f:
                        f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
                    logger.info(f"Logged abuse attempt for user {user_id}: {email} with ticket data")
                    print(f"Logged abuse attempt for user {user_id}: Invalid email")
                except Exception as e:
                    logger.error(f"Failed to log abuse attempt for user {user_id}: {str(e)}")
                    print(f"ERROR: Failed to log abuse attempt for user {user_id}: {str(e)}")
            self.block_user(user_id, reason="Invalid email", ticket_data=ticket_data)
            await update.message.reply_text(
                "Sajnáljuk, csak ÉPC-s email címmel jogosult a bejelentő felület használatára. \n"
                "Amennyiben nem rendelkezik ÉPC-s email címmel, kérem vegye fel a kapcsolatot az informatikai osztállyal.",
                reply_markup=ReplyKeyboardRemove()
            )
            print(f"User {user_id} blocked for invalid email, ending conversation")
            return ConversationHandler.END

        try:
            with open('/app/config/authorized_emails.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                authorized_emails = {row['email'].lower().strip() for row in reader}
            logger.debug(f"Loaded authorized emails: {authorized_emails}")
            print(f"Loaded authorized emails for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to read authorized_emails.csv: {str(e)}")
            print(f"ERROR: Failed to read authorized_emails.csv for user {user_id}: {str(e)}")
            await update.message.reply_text(
                "Hiba történt az bejelentés során. Kérem, lépjen kapcsolatba az informatikai osztállyal.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END

        if email.lower().strip() in authorized_emails:
            logger.info(f"User {user_id} authenticated successfully with email: {email}")
            print(f"User {user_id} authenticated successfully with email: {email}")
            context.user_data['authenticated_email'] = email
            print(f"Transitioning to submit_ticket for user {user_id}")
            return await self.submit_ticket(update, context)
        else:
            logger.warning(f"Unauthorized email from user {user_id}: {email}")
            print(f"WARNING: Unauthorized email from user {user_id}: {email}")
            ticket_data = {
                'category': context.user_data.get('category', 'N/A'),
                'component': context.user_data.get('component', 'N/A'),
                'issue': context.user_data.get('issue', 'N/A'),
                'description': context.user_data.get('description', 'N/A'),
                'team': context.user_data.get('team', 'N/A'),
                'address': context.user_data.get('address', 'N/A'),
                'campus': context.user_data.get('campus', 'N/A'),
                'building': context.user_data.get('building', 'N/A'),
                'floor': context.user_data.get('floor', 'N/A'),
                'department': context.user_data.get('department', 'N/A'),
                'room': context.user_data.get('room', 'N/A'),
                'latitude': context.user_data.get('latitude', None),
                'longitude': context.user_data.get('longitude', None),
                'media': context.user_data.get('media', None),
                'name': context.user_data.get('name', 'N/A'),
                'phone': context.user_data.get('phone', 'N/A')
            }
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'user_id': user_id,
                'email': email,
                'ticket_data': ticket_data
            }
            with abuse_file_lock:
                try:
                    with open('/app/logs/abuse_attempts.txt', 'a', encoding='utf-8') as f:
                        f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
                    logger.info(f"Logged abuse attempt for user {user_id}: {email} with ticket data")
                    print(f"Logged abuse attempt for user {user_id}: Unauthorized email")
                except Exception as e:
                    logger.error(f"Failed to log abuse attempt for user {user_id}: {str(e)}")
                    print(f"ERROR: Failed to log abuse attempt for user {user_id}: {str(e)}")
            self.block_user(user_id, reason="Unauthorized email", ticket_data=ticket_data)
            await update.message.reply_text(
                "Sajnáljuk, csak ÉPC-s email címmel jogosult a bejelentő felület használatára. \n"
                "Amennyiben nem rendelkezik ÉPC-s email címmel, kérem vegye fel a kapcsolatot az informatikai osztállyal.",
                reply_markup=ReplyKeyboardRemove()
            )
            print(f"User {user_id} blocked for unauthorized email, ending conversation")
            return ConversationHandler.END

    async def submit_ticket(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        logger.info(f"Submitting ticket for user {user_id}")
        print(f"Submitting ticket for user {user_id}")

        required_fields = ['category', 'issue', 'description', 'team', 'name', 'phone', 'authenticated_email']
        if context.user_data.get('is_other_location'):
            required_fields.append('address')
        else:
            required_fields.extend(['campus', 'building', 'floor', 'department', 'room'])
        missing_fields = [field for field in required_fields if field not in context.user_data]
        if missing_fields:
            logger.error(f"Missing required fields for user {user_id}: {missing_fields}")
            print(f"ERROR: Missing required fields for user {user_id}: {missing_fields}")
            await update.message.reply_text(
                f"Hiba: Hiányzó adatok ({', '.join(missing_fields)}). Kérem, próbálja újra vagy válassza a 'PANIC' opciót.",
                reply_markup=ReplyKeyboardMarkup([[self.panic_option]], one_time_keyboard=True)
            )
            return States.MEDIA.value

        try:
            self.form_data.store(user_id, 'category', context.user_data['category'])
            self.form_data.store(user_id, 'component', context.user_data.get('component', 'N/A'))
            self.form_data.store(user_id, 'issue_id', context.user_data.get('issue_id', 'N/A'))
            self.form_data.store(user_id, 'issue', context.user_data['issue'])
            self.form_data.store(user_id, 'description', context.user_data['description'])
            self.form_data.store(user_id, 'team', context.user_data['team'])
            self.form_data.store(user_id, 'is_other_location', context.user_data.get('is_other_location', False))
            if context.user_data.get('is_other_location'):
                self.form_data.store(user_id, 'address', context.user_data['address'])
                self.form_data.store(user_id, 'campus', 'N/A')
                self.form_data.store(user_id, 'building', 'N/A')
                self.form_data.store(user_id, 'floor', 'N/A')
                self.form_data.store(user_id, 'department', 'N/A')
                self.form_data.store(user_id, 'room', 'N/A')
            else:
                self.form_data.store(user_id, 'campus', context.user_data['campus'])
                self.form_data.store(user_id, 'building', context.user_data['building'])
                self.form_data.store(user_id, 'floor', context.user_data['floor'])
                self.form_data.store(user_id, 'department', context.user_data['department'])
                self.form_data.store(user_id, 'room', context.user_data['room'])
            self.form_data.store(user_id, 'latitude', context.user_data.get('latitude'))
            self.form_data.store(user_id, 'longitude', context.user_data.get('longitude'))
            self.form_data.store(user_id, 'media', context.user_data.get('media'))
            self.form_data.store(user_id, 'name', context.user_data['name'])
            self.form_data.store(user_id, 'phone', context.user_data['phone'])
            self.form_data.store(user_id, 'email', context.user_data['authenticated_email'])
            self.form_data.store(user_id, 'date', datetime.now().isoformat())

            form_data = self.form_data.get_form_data(user_id)
            logger.debug(f"Form data for user {user_id}: {form_data}")
            print(f"Form data collected for user {user_id}")
            media_path = context.user_data.get('media')
            try:
                logger.info(f"Attempting to send email for user {user_id} to {self.email_recipient}")
                print(f"Sending email for user {user_id} to {self.email_recipient}")
                result = self.email_service.send_email(
                    form_data=form_data,
                    user_id=user_id,
                    from_email=context.user_data['authenticated_email'],
                    to_email=self.email_recipient,
                    user_name=context.user_data['name'],
                    media_path=media_path
                )
                if result:
                    logger.info(f"Ticket successfully sent for user {user_id}")
                    print(f"Ticket successfully sent for user {user_id}")
                    await update.message.reply_text(
                        "A bejelentést sikeresen rögzítettük, az IT munkatársak hamarosan megvizsgálják a jelzett problémát. Köszönjük közreműködését!",
                        reply_markup=ReplyKeyboardRemove()
                    )
                else:
                    logger.error(f"Email sending returned False for user {user_id}")
                    print(f"ERROR: Email sending failed for user {user_id}")
                    await update.message.reply_text(
                        "Nem sikerült a jegy elküldése. Kérem, próbálja újra vagy lépjen kapcsolatba közvetlenül az informatikai osztállyal.",
                        reply_markup=ReplyKeyboardRemove()
                    )
            except Exception as e:
                logger.error(f"Email sending failed for user {user_id}: {str(e)}", exc_info=True)
                print(f"ERROR: Email sending failed for user {user_id}: {str(e)}")
                await update.message.reply_text(
                    "Hiba történt az email küldése során. Kérem, próbálja újra vagy lépjen kapcsolatba közvetlenül az informatikai osztállyal.",
                    reply_markup=ReplyKeyboardRemove()
                )
            finally:
                if media_path and os.path.exists(media_path):
                    try:
                        os.remove(media_path)
                        logger.info(f"Deleted temporary media file: {media_path}")
                        print(f"Deleted temporary media file: {media_path}")
                    except Exception as e:
                        logger.error(f"Failed to delete media file {media_path}: {str(e)}")
                        print(f"ERROR: Failed to delete media file {media_path}: {str(e)}")
            self.form_data.clear(user_id)
            print(f"Cleared form data for user {user_id}")
            return ConversationHandler.END
        except Exception as e:
            logger.error(f"Error in ticket submission for user {user_id}: {str(e)}", exc_info=True)
            print(f"ERROR: Ticket submission failed for user {user_id}: {str(e)}")
            await update.message.reply_text(
                "Hiba történt. Kérem, próbálja újra vagy válassza a 'PANIC' opciót az IT-val való kapcsolatfelvételhez.",
                reply_markup=ReplyKeyboardMarkup([[self.panic_option]], one_time_keyboard=True)
            )
            return States.MEDIA.value

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        logger.info(f"Received /cancel from user {user_id}")
        print(f"User {user_id} triggered /cancel")
        media_path = context.user_data.get('media')
        if media_path and os.path.exists(media_path):
            try:
                os.remove(media_path)
                logger.info(f"Deleted temporary media file: {media_path}")
                print(f"Deleted temporary media file: {media_path}")
            except Exception as e:
                logger.error(f"Failed to delete media file {media_path}: {str(e)}")
                print(f"ERROR: Failed to delete media file {media_path}: {str(e)}")
        self.form_data.clear(user_id)
        await update.message.reply_text(
            "A hibajegy felvétele megszakítva.",
            reply_markup=ReplyKeyboardRemove()
        )
        print(f"Conversation cancelled for user {user_id}")
        return ConversationHandler.END

    async def panic(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        logger.info(f"User {user_id} triggered PANIC button")
        print(f"User {user_id} triggered PANIC")
        self.form_data.clear(user_id)
        await update.message.reply_text(
            "Sürgős problémák esetén kérjük, hívja az Informatikai diszpécserszolgálatot a 72-444 melléken.",
            reply_markup=ReplyKeyboardRemove()
        )
        print(f"Conversation ended with PANIC for user {user_id}")
        return ConversationHandler.END
