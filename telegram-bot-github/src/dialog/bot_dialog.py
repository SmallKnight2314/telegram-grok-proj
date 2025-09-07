import logging
import json
import re
import os
import asyncio
import unicodedata
import csv
from datetime import datetime, timedelta
from threading import Lock
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from src.data.form_data import FormData
from src.services.email_service import EmailService
from src.states import States

logger = logging.getLogger(__name__)
abuse_file_lock = Lock()

class BotDialog:
    def __init__(self, form_data: FormData, email_service: EmailService, email_recipient: str):
        self.form_data = form_data
        self.email_service = email_service
        self.email_recipient = email_recipient
        self.is_other_allowed = os.getenv("IS_OTHER_ALLOWED", "true").lower() == "true"
        self.blocked_users = {}
        try:
            with open('config/topics.json') as f:
                self.topics = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load topics.json: {str(e)}")
            raise
        try:
            with open('config/locations.json') as f:
                self.locations = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load locations.json: {str(e)}")
            raise
        try:
            self.load_blocked_users()
        except Exception as e:
            logger.error(f"Failed to load blocked_users.txt: {str(e)}")
        self.panic_option = "PANIC"
        self.other_option = "Other"
        self.max_media_size = 20_000_000
        self.max_description_length = 1000  # New: Maximum description length
        logger.debug(f"BotDialog initialized with categories: {list(self.topics['categories'].keys())}")
        logger.debug(f"Blocked users: {self.blocked_users}")
        logger.debug(f"is_other_allowed: {self.is_other_allowed}")

    def load_blocked_users(self):
        try:
            with open('/app/logs/blocked_users.txt', 'r') as f:
                for line in f:
                    user_id, expiry = line.strip().split(',')
                    self.blocked_users[int(user_id)] = datetime.fromisoformat(expiry)
        except FileNotFoundError:
            logger.info("No blocked_users.txt found, starting with empty blocked_users")
        except Exception as e:
            logger.error(f"Error loading blocked_users.txt: {str(e)}")
            raise

    def save_blocked_users(self, user_id: int, expiry: datetime):
        with abuse_file_lock:
            try:
                with open('/app/logs/blocked_users.txt', 'a') as f:
                    f.write(f"{user_id},{expiry.isoformat()}\n")
                logger.info(f"Saved block for user {user_id} until {expiry.isoformat()}")
            except Exception as e:
                logger.error(f"Failed to save block for user {user_id}: {str(e)}")

    def is_blocked(self, user_id: int) -> bool:
        if user_id in self.blocked_users:
            expiry = self.blocked_users[user_id]
            if expiry is None or datetime.now() < expiry:
                logger.debug(f"User {user_id} is blocked until {expiry}")
                return True
            else:
                del self.blocked_users[user_id]
                logger.info(f"Block expired for user {user_id}")
        return False

    def block_user(self, user_id: int, duration_seconds: int = 3600):
        expiry = datetime.now() + timedelta(seconds=duration_seconds)
        self.blocked_users[user_id] = expiry
        self.save_blocked_users(user_id, expiry)
        logger.info(f"User {user_id} blocked until {expiry.isoformat()}")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        logger.info(f"Received /start from user {user_id}")
        if self.is_blocked(user_id):
            await update.message.reply_text(
                "Ön túl sokszor próbálta a rendszert. Kérem, próbálja újra később.",
                reply_markup=ReplyKeyboardRemove()
            )
            logger.debug(f"Blocked user {user_id} attempted to start conversation")
            return ConversationHandler.END
        context.user_data.clear()
        categories = list(self.topics['categories'].keys())
        buttons = [[cat] for cat in categories]
        if self.is_other_allowed:
            buttons.append([self.other_option])
        buttons.append([self.panic_option])
        logger.debug(f"Generated start keyboard: {buttons}")
        await update.message.reply_text(
            "Üdvözöljük a Kórházi IT Támogató Botban! Kezdjük a jegy létrehozását.\n"
            "Milyen típusú problémát tapasztal? Sürgős esetekben válassza a 'PANIC' opciót.",
            reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True)
        )
        logger.debug(f"start method took {(datetime.now() - start_time).total_seconds()} seconds")
        return States.CATEGORY.value

    async def auth(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        email = update.message.text.strip()
        logger.info(f"Received authentication email from user {user_id}: {email}")

        if not re.match(r'^[\w\.-]+@teszt-domain\.com$', email):
            logger.warning(f"Invalid email format from user {user_id}: {email}")
            try:
                ticket_data = {
                    'category': context.user_data.get('category', 'N/A'),
                    'component': context.user_data.get('component', 'N/A'),
                    'issue': context.user_data.get('issue', 'N/A'),
                    'description': context.user_data.get('description', 'N/A'),
                    'team': context.user_data.get('team', 'N/A'),
                    'campus': context.user_data.get('campus', 'N/A'),
                    'department': context.user_data.get('department', 'N/A'),
                    'building': context.user_data.get('building', 'N/A'),
                    'floor': context.user_data.get('floor', 'N/A'),
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
                    with open('/app/logs/abuse_attempts.txt', 'a', encoding='utf-8') as f:
                        f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
                logger.info(f"Logged abuse attempt for user {user_id}: {email} with ticket data")
                self.block_user(user_id)
            except Exception as e:
                logger.error(f"Failed to log abuse attempt for user {user_id}: {str(e)}")
            await update.message.reply_text(
                "Sajnáljuk, ez az email cím nem jogosult a bot használatára. Kérem, lépjen kapcsolatba az IT-val.\n"
                "Felhívjuk figyelmét, hogy minden tevékenységet figyelünk a visszaélések elkerülése érdekében.",
                reply_markup=ReplyKeyboardRemove()
            )
            logger.debug(f"auth method (invalid email) took {(datetime.now() - start_time).total_seconds()} seconds")
            return ConversationHandler.END

        try:
            with open('/app/config/authorized_emails.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                authorized_emails = {row['email'].lower().strip() for row in reader}
        except Exception as e:
            logger.error(f"Failed to read authorized_emails.csv: {str(e)}")
            await update.message.reply_text(
                "Hiba történt az autentikáció során. Kérem, lépjen kapcsolatba az IT-val.",
                reply_markup=ReplyKeyboardRemove()
            )
            logger.debug(f"auth method took {(datetime.now() - start_time).total_seconds()} seconds")
            return ConversationHandler.END

        if email.lower().strip() in authorized_emails:
            logger.info(f"User {user_id} authenticated successfully with email: {email}")
            context.user_data['authenticated_email'] = email
            logger.debug(f"auth method took {(datetime.now() - start_time).total_seconds()} seconds")
            return await self.submit_ticket(update, context)
        else:
            logger.warning(f"Unauthorized email from user {user_id}: {email}")
            try:
                ticket_data = {
                    'category': context.user_data.get('category', 'N/A'),
                    'component': context.user_data.get('component', 'N/A'),
                    'issue': context.user_data.get('issue', 'N/A'),
                    'description': context.user_data.get('description', 'N/A'),
                    'team': context.user_data.get('team', 'N/A'),
                    'campus': context.user_data.get('campus', 'N/A'),
                    'department': context.user_data.get('department', 'N/A'),
                    'building': context.user_data.get('building', 'N/A'),
                    'floor': context.user_data.get('floor', 'N/A'),
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
                    with open('/app/logs/abuse_attempts.txt', 'a', encoding='utf-8') as f:
                        f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
                logger.info(f"Logged abuse attempt for user {user_id}: {email} with ticket data")
                self.block_user(user_id)
            except Exception as e:
                logger.error(f"Failed to log abuse attempt for user {user_id}: {str(e)}")
            await update.message.reply_text(
                "Sajnáljuk, ez az email cím nem jogosult a bot használatára. Kérem, lépjen kapcsolatba az IT-val.\n"
                "Felhívjuk figyelmét, hogy minden tevékenységet figyelünk a visszaélések elkerülése érdekében.",
                reply_markup=ReplyKeyboardRemove()
            )
            logger.debug(f"auth method took {(datetime.now() - start_time).total_seconds()} seconds")
            return ConversationHandler.END

    async def category(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        category = update.message.text.lower().strip()
        logger.info(f"Received category from user {user_id}: {category}")

        if category == self.panic_option.lower():
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
                keyboard = [[c['name']] for c in self.locations['campuses']] + [[self.panic_option]]
                await update.message.reply_text(
                    self.locations['prompts']['campus']['hu'],
                    reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
                )
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
            return States.COMPONENT.value

        buttons = [[cat] for cat in self.topics['categories'].keys()]
        if self.is_other_allowed:
            buttons.append([self.other_option])
        buttons.append([self.panic_option])
        await update.message.reply_text(
            f"Érvénytelen kategória. Kérem, válasszon egyet: {', '.join(self.topics['categories'].keys())}",
            reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True)
        )
        return States.CATEGORY.value

    async def component(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        component = update.message.text.strip()
        category = context.user_data.get('category')
        logger.info(f"Received component from user {user_id}: {component}")

        if not category or category not in self.topics['categories']:
            logger.error(f"Invalid or missing category: {category}")
            context.user_data.pop('category', None)
            buttons = [[cat] for cat in self.topics['categories'].keys()]
            if self.is_other_allowed:
                buttons.append([self.other_option])
            buttons.append([self.panic_option])
            await update.message.reply_text(
                "Hiba: Kérem, válasszon egy kategóriát újra.",
                reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True)
            )
            return States.CATEGORY.value

        if component.lower() == self.panic_option.lower():
            return await self.panic(update, context)

        options = self.topics['categories'][category]['options']
        components = {(options[comp].get('display_name', comp)).lower(): comp for comp in options.keys()}
        if self.is_other_allowed and component.lower() == "other":
            context.user_data['component'] = "other"
            context.user_data['issue'] = f"{category} - Other"
            context.user_data['issue_id'] = "other"
            context.user_data['is_other_selected'] = True
            logger.debug(f"User {user_id} selected 'other' component")
            keyboard = [[c['name']] for c in self.locations['campuses']] + [[self.panic_option]]
            await update.message.reply_text(
                self.locations['prompts']['campus']['hu'],
                reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            )
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
        return States.COMPONENT.value

    async def panic(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        logger.info(f"User {user_id} triggered PANIC button")
        self.form_data.clear(user_id)
        await update.message.reply_text(
            "Sürgős problémák esetén kérjük, hívja az Informatikai diszpécserszolgálatot a +36-1-555-1234 telefonszámon.",
            reply_markup=ReplyKeyboardRemove()
        )
        logger.debug(f"panic method took {(datetime.now() - start_time).total_seconds()} seconds")
        return ConversationHandler.END

    async def issue(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        issue = update.message.text.strip()
        category = context.user_data.get('category')
        component = context.user_data.get('component')
        logger.info(f"Received issue from user {user_id}: {issue}")

        if issue.lower() == self.panic_option.lower():
            return await self.panic(update, context)

        issues = self.topics['categories'][category]['options'][component]['options']
        issue_id = next((k for k, v in issues.items() if issue.endswith(f" ({k})")), None)
        if self.is_other_allowed and issue.lower() == "other":
            display_name = self.topics['categories'][category]['options'][component].get('display_name', component)
            context.user_data['issue'] = f"{display_name} - Other"
            context.user_data['issue_id'] = "other"
            context.user_data['is_other_selected'] = True
            logger.debug(f"User {user_id} selected 'other' issue")
            keyboard = [[c['name']] for c in self.locations['campuses']] + [[self.panic_option]]
            await update.message.reply_text(
                self.locations['prompts']['campus']['hu'],
                reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            )
            return States.CAMPUS.value

        if issue_id:
            display_name = self.topics['categories'][category]['options'][component].get('display_name', component)
            issue_description = issues[issue_id]['description']
            context.user_data['issue'] = f"{display_name} - {issue_description}"
            context.user_data['issue_id'] = issue_id
            keyboard = [[c['name']] for c in self.locations['campuses']] + [[self.panic_option]]
            logger.debug(f"Generated campus keyboard: {keyboard}")
            await update.message.reply_text(
                self.locations['prompts']['campus']['hu'],
                reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            )
            logger.debug(f"issue method took {(datetime.now() - start_time).total_seconds()} seconds")
            return States.CAMPUS.value

        issue_keys = list(issues.keys())
        if self.is_other_allowed:
            issue_keys.append("other")
        keyboard = [[f"{issues.get(k, {}).get('description', k)} ({k})"] if k != "other" else ["Other"] for k in issue_keys] + [[self.panic_option]]
        logger.debug(f"Generated issue error keyboard: {keyboard}")
        await update.message.reply_text(
            f"Érvénytelen probléma. Kérem, válasszon egyet:",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )
        logger.debug(f"issue method took {(datetime.now() - start_time).total_seconds()} seconds")
        return States.ISSUE.value

    async def campus(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        campus = update.message.text
        logger.info(f"Received campus from user {user_id}: {campus}")

        campuses = [c['name'] for c in self.locations['campuses']]
        if campus in campuses:
            context.user_data['campus'] = campus
            departments = [d['name'] for d in next(c['departments'] for c in self.locations['campuses'] if c['name'] == campus)]
            keyboard = [[d] for d in departments] + [[self.panic_option]]
            logger.debug(f"Generated department keyboard: {keyboard}")
            await update.message.reply_text(
                self.locations['prompts']['department']['hu'],
                reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            )
            logger.debug(f"campus method took {(datetime.now() - start_time).total_seconds()} seconds")
            return States.DEPARTMENT.value

        keyboard = [[c['name']] for c in self.locations['campuses']] + [[self.panic_option]]
        logger.debug(f"Generated campus error keyboard: {keyboard}")
        await update.message.reply_text(
            f"Érvénytelen kampusz. {self.locations['prompts']['campus']['hu']}",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )
        logger.debug(f"campus method took {(datetime.now() - start_time).total_seconds()} seconds")
        return States.CAMPUS.value

    async def department(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        department = update.message.text
        logger.info(f"Received department from user {user_id}: {department}")
        campus = context.user_data.get('campus')
        departments = next(c['departments'] for c in self.locations['campuses'] if c['name'] == campus)
        department_names = [d['name'] for d in departments]
        if department in department_names:
            context.user_data['department'] = department
            dept_data = next(d for d in departments if d['name'] == department)
            context.user_data['building'] = dept_data['building']
            context.user_data['floor'] = dept_data['floor']
            await update.message.reply_text(
                self.locations['prompts']['room']['hu'],
                reply_markup=ReplyKeyboardRemove()
            )
            logger.debug(f"department method took {(datetime.now() - start_time).total_seconds()} seconds")
            return States.ROOM.value

        keyboard = [[d] for d in department_names] + [[self.panic_option]]
        logger.debug(f"Generated department error keyboard: {keyboard}")
        await update.message.reply_text(
            f"Érvénytelen osztály. {self.locations['prompts']['department']['hu']}",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )
        logger.debug(f"department method took {(datetime.now() - start_time).total_seconds()} seconds")
        return States.DEPARTMENT.value

    async def room(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        room = update.message.text.strip()
        logger.info(f"Received room from user {user_id}: {room}")
        if re.match(self.locations['validation']['room'], room):
            context.user_data['room'] = room
            keyboard = [[KeyboardButton("Hely megosztása", request_location=True)], ["Kihagy"]]
            logger.debug(f"Generated geolocation keyboard: {keyboard}")
            await update.message.reply_text(
                self.locations['prompts']['geolocation']['hu'],
                reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            )
            logger.debug(f"room method took {(datetime.now() - start_time).total_seconds()} seconds")
            return States.GEOLOCATION.value

        await update.message.reply_text(
            "Érvénytelen szoba szám. Kérem, adjon meg egy érvényes szoba vagy iroda számot (pl. 204-es szoba).",
            reply_markup=ReplyKeyboardRemove()
        )
        logger.debug(f"room method took {(datetime.now() - start_time).total_seconds()} seconds")
        return States.ROOM.value

    async def geolocation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        logger.info(f"Processing geolocation for user {user_id}")

        if update.message.text:
            text = unicodedata.normalize('NFKC', update.message.text.strip()).lower()
            logger.debug(f"Normalized geolocation input: {text}")
            if text == "kihagy":
                logger.info(f"User {user_id} skipped geolocation")
                context.user_data['latitude'] = None
                context.user_data['longitude'] = None
                await update.message.reply_text(
                    "Adja meg a nevét:",
                    reply_markup=ReplyKeyboardRemove()
                )
                logger.debug(f"geolocation method (kihagy) took {(datetime.now() - start_time).total_seconds()} seconds")
                return States.NAME.value

        if update.message.location:
            location = update.message.location
            logger.info(f"Received geolocation from user {user_id}: ({location.latitude}, {location.longitude})")
            context.user_data['latitude'] = location.latitude
            context.user_data['longitude'] = location.longitude
            await update.message.reply_text(
                "Adja meg a nevét:",
                reply_markup=ReplyKeyboardRemove()
            )
            logger.debug(f"geolocation method (location) took {(datetime.now() - start_time).total_seconds()} seconds")
            return States.NAME.value

        keyboard = [[KeyboardButton("Hely megosztása", request_location=True)], ["Kihagy"]]
        logger.debug(f"Generated geolocation error keyboard: {keyboard}")
        await update.message.reply_text(
            "Kérem, ossza meg a helyet vagy válassza a 'Kihagy' opciót.",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )
        logger.debug(f"geolocation method (invalid) took {(datetime.now() - start_time).total_seconds()} seconds")
        return States.GEOLOCATION.value

    async def name(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        context.user_data['name'] = update.message.text
        logger.info(f"Received name from user {user_id}: {context.user_data['name']}")
        keyboard = [[KeyboardButton("Kapcsolat megosztása", request_contact=True)]]
        logger.debug(f"Generated phone keyboard: {keyboard}")
        await update.message.reply_text(
            "Kérem adja meg a mellékét vagy a telefonszámát (vagy használja a kapcsolat megosztás opcióját):",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )
        logger.debug(f"name method took {(datetime.now() - start_time).total_seconds()} seconds")
        return States.PHONE.value

    async def phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        if update.message.contact:
            context.user_data['phone'] = update.message.contact.phone_number
        else:
            context.user_data['phone'] = update.message.text
        logger.info(f"Received phone from user {user_id}: {context.user_data['phone']}")
        keyboard = [["Kihagy"]] if not context.user_data.get('is_other_selected') else []
        prompt = "Kérem, adja meg a probléma részletes leírását:" if context.user_data.get('is_other_selected') else \
                 "OPCIONÁLIS: Adjon meg további részleteket (vagy nyomja meg a 'Kihagy' gombot a folytatáshoz):"
        await update.message.reply_text(
            prompt,
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True) if keyboard else ReplyKeyboardRemove()
        )
        logger.debug(f"phone method took {(datetime.now() - start_time).total_seconds()} seconds")
        return States.DESCRIPTION.value

    async def description(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        description = update.message.text
        logger.info(f"Received description from user {user_id}: {description}")

        # Check character limit
        if description and len(description) > self.max_description_length:
            logger.warning(f"Description too long from user {user_id}: {len(description)} characters")
            keyboard = [["Kihagy"]] if not context.user_data.get('is_other_selected') else []
            await update.message.reply_text(
                f"A leírás túl hosszú (max. {self.max_description_length} karakter). Kérem, rövidebben fogalmazza meg.",
                reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True) if keyboard else ReplyKeyboardRemove()
            )
            logger.debug(f"description method (too long) took {(datetime.now() - start_time).total_seconds()} seconds")
            return States.DESCRIPTION.value

        if context.user_data.get('is_other_selected'):
            if not description or description.strip().lower() == "kihagy":
                logger.warning(f"User {user_id} provided empty or 'Kihagy' description for 'Other' selection")
                try:
                    ticket_data = {
                        'category': context.user_data.get('category', 'N/A'),
                        'component': context.user_data.get('component', 'N/A'),
                        'issue': context.user_data.get('issue', 'N/A'),
                        'description': description or 'Empty',
                        'team': context.user_data.get('team', 'N/A'),
                        'campus': context.user_data.get('campus', 'N/A'),
                        'department': context.user_data.get('department', 'N/A'),
                        'building': context.user_data.get('building', 'N/A'),
                        'floor': context.user_data.get('floor', 'N/A'),
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
                        with open('/app/logs/abuse_attempts.txt', 'a', encoding='utf-8') as f:
                            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
                    logger.info(f"Logged abuse attempt for user {user_id}: Invalid description for Other")
                    self.block_user(user_id)
                except Exception as e:
                    logger.error(f"Failed to log abuse attempt for user {user_id}: {str(e)}")
                await update.message.reply_text(
                    "A probléma leírása kötelező, ha az 'Egyéb' opciót választotta. Kérem, adja meg a részleteket.",
                    reply_markup=ReplyKeyboardRemove()
                )
                logger.debug(f"description method (invalid for Other) took {(datetime.now() - start_time).total_seconds()} seconds")
                return States.DESCRIPTION.value
            context.user_data['description'] = description
        else:
            if description:
                text = unicodedata.normalize('NFKC', description.strip()).lower()
                logger.debug(f"Normalized description input: {text}")
                if text == "kihagy":
                    context.user_data['description'] = 'Nincs további részlet megadva'
                else:
                    context.user_data['description'] = description
            else:
                context.user_data['description'] = 'Nincs további részlet megadva'

        keyboard = [["Kihagy"]]
        logger.debug(f"Generated media keyboard: {keyboard}")
        await update.message.reply_text(
            self.locations['prompts']['media']['hu'],
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )
        logger.debug(f"description method took {(datetime.now() - start_time).total_seconds()} seconds")
        return States.MEDIA.value

    async def media(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        logger.info(f"Processing media for user {user_id}")

        if update.message.text:
            text = unicodedata.normalize('NFKC', update.message.text.strip()).lower()
            logger.debug(f"Normalized media input: {text}")
            if text == "kihagy":
                logger.info(f"User {user_id} skipped media upload")
                context.user_data['media'] = None
                await update.message.reply_text(
                    "Adja meg email címét az autentikációhoz:\n"
                    "Felhívjuk figyelmét, hogy minden tevékenységet figyelünk a visszaélések elkerülése érdekében.",
                    reply_markup=ReplyKeyboardRemove()
                )
                logger.debug(f"media method (kihagy) took {(datetime.now() - start_time).total_seconds()} seconds")
                return States.AUTH.value

        if update.message.photo or update.message.video:
            media = update.message.photo[-1] if update.message.photo else update.message.video
            file_size = media.file_size
            if file_size > self.max_media_size:
                logger.warning(f"Media file too large from user {user_id}: {file_size} bytes")
                keyboard = [["Kihagy"]]
                logger.debug(f"Generated media error keyboard (too large): {keyboard}")
                await update.message.reply_text(
                    f"A fájl túl nagy (max. 20MB, kapott {file_size // 1_000_000}MB). Kérem, töltsön fel kisebb fájlt vagy nyomja meg a Kihagy gombot.",
                    reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
                )
                logger.debug(f"media method (too large) took {(datetime.now() - start_time).total_seconds()} seconds")
                return States.MEDIA.value

            try:
                file = await context.bot.get_file(media.file_id)
                ext = '.jpg' if update.message.photo else '.mp4'
                file_path = f"/app/tmp/{user_id}_{datetime.now().strftime('%Y%m%dT%H%M%S')}{ext}"
                await asyncio.wait_for(file.download_to_drive(file_path), timeout=10.0)
                context.user_data['media'] = file_path
                logger.info(f"Media file downloaded for user {user_id}: {file_path}")
                await update.message.reply_text(
                    "Adja meg email címét az autentikációhoz:\n"
                    "Felhívjuk figyelmét, hogy minden tevékenységet figyelünk a visszaélések elkerülése érdekében.",
                    reply_markup=ReplyKeyboardRemove()
                )
                logger.debug(f"media method (download) took {(datetime.now() - start_time).total_seconds()} seconds")
                return States.AUTH.value

            except asyncio.TimeoutError:
                logger.error(f"Media download timed out for user {user_id}")
                keyboard = [["Kihagy"]]
                logger.debug(f"Generated media error keyboard (timeout): {keyboard}")
                await update.message.reply_text(
                    "A média letöltése időtúllépés miatt nem sikerült. Kérem, próbálja újra vagy nyomja meg a Kihagy gombot.",
                    reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
                )
                logger.debug(f"media method (timeout) took {(datetime.now() - start_time).total_seconds()} seconds")
                return States.MEDIA.value

            except Exception as e:
                logger.error(f"Failed to download media for user {user_id}: {str(e)}")
                keyboard = [["Kihagy"]]
                logger.debug(f"Generated media error keyboard (error): {keyboard}")
                await update.message.reply_text(
                    "Nem sikerült a média feldolgozása. Kérem, próbálja újra vagy nyomja meg a Kihagy gombot.",
                    reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
                )
                logger.debug(f"media method (error) took {(datetime.now() - start_time).total_seconds()} seconds")
                return States.MEDIA.value

        keyboard = [["Kihagy"]]
        logger.debug(f"Generated media error keyboard (invalid): {keyboard}")
        await update.message.reply_text(
            "Kérem, töltsön fel egy képet vagy videót (max. 20MB), vagy nyomja meg a Kihagy gombot.",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )
        logger.debug(f"media method (invalid) took {(datetime.now() - start_time).total_seconds()} seconds")
        return States.MEDIA.value

    async def submit_ticket(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        logger.info(f"Submitting ticket for user {user_id}")

        required_fields = ['category', 'issue', 'description', 'team', 'campus', 'department', 'building', 'floor', 'room', 'name', 'phone', 'authenticated_email']
        missing_fields = [field for field in required_fields if field not in context.user_data]
        if missing_fields:
            logger.error(f"Missing required fields for user {user_id}: {missing_fields}")
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
            self.form_data.store(user_id, 'campus', context.user_data['campus'])
            self.form_data.store(user_id, 'department', context.user_data.get('department'))
            self.form_data.store(user_id, 'building', context.user_data['building'])
            self.form_data.store(user_id, 'floor', context.user_data['floor'])
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
            media_path = context.user_data.get('media')
            try:
                logger.info(f"Attempting to send email for user {user_id} to {self.email_recipient}")
                if self.email_service.send_email(
                    form_data=form_data,
                    user_id=user_id,
                    from_email=context.user_data['authenticated_email'],
                    to_email=self.email_recipient,
                    user_name=context.user_data['name'],
                    media_path=media_path
                ):
                    logger.info(f"Ticket successfully sent for user {user_id}")
                    await update.message.reply_text(
                        "A bejelentést sikeresen rögzítettük, az IT munkatársak hamarosan megvizsgálják a jelzett problémát. Köszönjük közreműködését!",
                        reply_markup=ReplyKeyboardRemove()
                    )
                else:
                    logger.error(f"Email sending returned False for user {user_id}")
                    await update.message.reply_text(
                        "Nem sikerült a jegy elküldése. Kérem, próbálja újra vagy lépjen kapcsolatba közvetlenül az IT-val.",
                        reply_markup=ReplyKeyboardRemove()
                    )
            except Exception as e:
                logger.error(f"Email sending failed for user {user_id}: {str(e)}")
                await update.message.reply_text(
                    "Hiba történt az email küldése során. Kérem, próbálja újra vagy lépjen kapcsolatba az IT-val.",
                    reply_markup=ReplyKeyboardRemove()
                )
            finally:
                if media_path and os.path.exists(media_path):
                    try:
                        os.remove(media_path)
                        logger.info(f"Deleted temporary media file: {media_path}")
                    except Exception as e:
                        logger.error(f"Failed to delete media file {media_path}: {str(e)}")
            self.form_data.clear(user_id)
            logger.debug(f"submit_ticket method (success) took {(datetime.now() - start_time).total_seconds()} seconds")
            return ConversationHandler.END
        except Exception as e:
            logger.error(f"Error in ticket submission for user {user_id}: {str(e)}")
            await update.message.reply_text(
                "Hiba történt. Kérem, próbálja újra vagy válassza a 'PANIC' opciót az IT-val való kapcsolatfelvételhez.",
                reply_markup=ReplyKeyboardMarkup([[self.panic_option]], one_time_keyboard=True)
            )
            logger.debug(f"submit_ticket method (error) took {(datetime.now() - start_time).total_seconds()} seconds")
            return States.MEDIA.value

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        start_time = datetime.now()
        user_id = update.message.from_user.id
        logger.info(f"Received /cancel from user {user_id}")
        media_path = context.user_data.get('media')
        if media_path and os.path.exists(media_path):
            try:
                os.remove(media_path)
                logger.info(f"Deleted temporary media file: {media_path}")
            except Exception as e:
                logger.error(f"Failed to delete media file {media_path}: {str(e)}")
        self.form_data.clear(user_id)
        await update.message.reply_text(
            "A jegy benyújtása megszakítva.",
            reply_markup=ReplyKeyboardRemove()
        )
        logger.debug(f"cancel method took {(datetime.now() - start_time).total_seconds()} seconds")
        return ConversationHandler.END
