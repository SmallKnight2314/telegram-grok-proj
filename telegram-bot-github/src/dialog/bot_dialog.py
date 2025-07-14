# bot_dialog.py
import telegram
from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ConversationHandler, MessageHandler, filters
from enum import Enum
import logging
from datetime import datetime
import re

logger = logging.getLogger(__name__)

class States(Enum):
    SUBJECT = 1
    OTHER_SUBJECT = 2
    NAME = 3
    DEPARTMENT = 4
    OTHER_DEPARTMENT = 5
    CAMPUS = 6
    OTHER_CAMPUS = 7
    BUILDING = 8
    FLOOR = 9
    ROOM = 10
    PHONE = 11
    EMAIL = 12
    DESCRIPTION = 13
    CALLBACK = 14

class BotDialog:
    def __init__(self, form_data, email_service):
        self.form_data = form_data
        self.email_service = email_service
        self.subjects = ["Hálózati probléma", "Szoftver összeomlás", "Hardver hiba", "Hozzáférés megtagadva", "Nyomtató probléma", "Egyéb"]
        self.departments = ["Emberi erőforrások", "IT", "Pénzügy", "Értékesítés", "Műveletek", "Egyéb"]
        self.campuses = ["Fő kampusz", "A épület", "B épület", "Távoli", "Egyéb"]
        self.callback_options = ["Igen", "Nem"]

    async def start(self, update, context):
        user_id = update.message.from_user.id
        logger.info(f"Received /start from user {user_id}")
        keyboard = [[KeyboardButton(subject)] for subject in self.subjects]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder="Válasszon problématípust")
        await update.message.reply_text(
            "Üdvözöljük az IT támogatási jegykezelő botban! Hozzuk létre az új jegyet.\n"
            "Kérjük, válassza ki a probléma típusát az alábbi gombok segítségével:\n"
            f"Lehetőségek: {', '.join(self.subjects)}",
            reply_markup=reply_markup
        )
        logger.info(f"Sent subject keyboard to user {user_id}")
        return States.SUBJECT.value

    async def get_subject(self, update, context):
        user_id = update.message.from_user.id
        subject = update.message.text
        logger.info(f"Received subject input from user {user_id}: {subject}")
        if subject in self.subjects:
            if subject == "Egyéb":
                await update.message.reply_text(
                    "Kérjük, adja meg a probléma típusát:", reply_markup=ReplyKeyboardRemove()
                )
                return States.OTHER_SUBJECT.value
            else:
                self.form_data.store(user_id, 'subject', subject)
                self.form_data.store(user_id, 'date', datetime.now().strftime("%Y.%m.%d %H:%M"))
                await update.message.reply_text(
                    "Köszönjük! Kérjük, adja meg a teljes nevét.", reply_markup=ReplyKeyboardRemove()
                )
                return States.NAME.value
        else:
            keyboard = [[KeyboardButton(subject)] for subject in self.subjects]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder="Válasszon problématípust")
            await update.message.reply_text(
                f"Érvénytelen bemenet. Kérjük, válasszon érvényes problématípust az alábbi gombok segítségével:\n"
                f"Lehetőségek: {', '.join(self.subjects)}",
                reply_markup=reply_markup
            )
            logger.info(f"Sent subject keyboard again to user {user_id} due to invalid input")
            return States.SUBJECT.value

    async def get_other_subject(self, update, context):
        user_id = update.message.from_user.id
        logger.info(f"Received other subject input from user {user_id}: {update.message.text}")
        self.form_data.store(user_id, 'subject', update.message.text)
        self.form_data.store(user_id, 'date', datetime.now().strftime("%Y.%m.%d %H:%M"))
        await update.message.reply_text("Köszönjük! Kérjük, adja meg a teljes nevét.")
        return States.NAME.value

    async def get_name(self, update, context):
        user_id = update.message.from_user.id
        logger.info(f"Received name input from user {user_id}: {update.message.text}")
        self.form_data.store(user_id, 'name', update.message.text)
        keyboard = [[KeyboardButton(dept)] for dept in self.departments]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder="Válasszon osztályt")
        await update.message.reply_text(
            "Kérjük, válassza ki az osztályát az alábbi gombok segítségével:\n"
            f"Lehetőségek: {', '.join(self.departments)}",
            reply_markup=reply_markup
        )
        logger.info(f"Sent department keyboard to user {user_id}")
        return States.DEPARTMENT.value

    async def get_department(self, update, context):
        user_id = update.message.from_user.id
        department = update.message.text
        logger.info(f"Received department input from user {user_id}: {department}")
        if department in self.departments:
            if department == "Egyéb":
                await update.message.reply_text(
                    "Kérjük, adja meg az osztályát:", reply_markup=ReplyKeyboardRemove()
                )
                return States.OTHER_DEPARTMENT.value
            else:
                self.form_data.store(user_id, 'department', department)
                keyboard = [[KeyboardButton(campus)] for campus in self.campuses] + [[KeyboardButton("Helymegosztás", request_location=True)]]
                reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder="Válasszon kampuszt vagy ossza meg a geolokációt")
                await update.message.reply_text(
                    "Kérjük, válassza ki a kampuszt vagy ossza meg a geolokációját az alábbi gombok segítségével:\n"
                    f"Lehetőségek: {', '.join(self.campuses)}",
                    reply_markup=reply_markup
                )
                logger.info(f"Sent campus keyboard to user {user_id}")
                return States.CAMPUS.value
        else:
            keyboard = [[KeyboardButton(dept)] for dept in self.departments]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder="Válasszon osztályt")
            await update.message.reply_text(
                f"Érvénytelen bemenet. Kérjük, válasszon érvényes osztályt az alábbi gombok segítségével:\n"
                f"Lehetőségek: {', '.join(self.departments)}",
                reply_markup=reply_markup
            )
            logger.info(f"Sent department keyboard again to user {user_id} due to invalid input")
            return States.DEPARTMENT.value

    async def get_other_department(self, update, context):
        user_id = update.message.from_user.id
        logger.info(f"Received other department input from user {user_id}: {update.message.text}")
        self.form_data.store(user_id, 'department', update.message.text)
        keyboard = [[KeyboardButton(campus)] for campus in self.campuses] + [[KeyboardButton("Helymegosztás", request_location=True)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder="Válasszon kampuszt vagy ossza meg a geolokációt")
        await update.message.reply_text(
            "Kérjük, válassza ki a kampuszt vagy ossza meg a geolokációját az alábbi gombok segítségével:\n"
            f"Lehetőségek: {', '.join(self.campuses)}",
            reply_markup=reply_markup
        )
        logger.info(f"Sent campus keyboard to user {user_id}")
        return States.CAMPUS.value

    async def get_campus(self, update, context):
        user_id = update.message.from_user.id
        if update.message.location:
            location = f"Geolokáció: ({update.message.location.latitude}, {update.message.location.longitude})"
            logger.info(f"Received geolocation from user {user_id}: {location}")
            self.form_data.store(user_id, 'campus', location)
            keyboard = [[KeyboardButton("Telefonszám megosztása", request_contact=True)]]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder="Ossza meg vagy írja be a telefonszámát")
            await update.message.reply_text(
                "Köszönjük! Kérjük, ossza meg a telefonszámát a gombbal vagy írja be manuálisan (mobil vagy belső IP telefon, pl. +36201234567 vagy 12345):",
                reply_markup=reply_markup
            )
            logger.info(f"Sent phone number keyboard to user {user_id}")
            return States.PHONE.value
        elif update.message.text in self.campuses:
            logger.info(f"Received campus input from user {user_id}: {update.message.text}")
            if update.message.text == "Egyéb":
                await update.message.reply_text(
                    "Kérjük, adja meg a kampusz nevét:", reply_markup=ReplyKeyboardRemove()
                )
                return States.OTHER_CAMPUS.value
            else:
                self.form_data.store(user_id, 'campus', update.message.text)
                await update.message.reply_text(
                    "Kérjük, adja meg az épület nevét (pl. Irodaház 1):", reply_markup=ReplyKeyboardRemove()
                )
                return States.BUILDING.value
        else:
            keyboard = [[KeyboardButton(campus)] for campus in self.campuses] + [[KeyboardButton("Helymegosztás", request_location=True)]]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder="Válasszon kampuszt vagy ossza meg a geolokációt")
            await update.message.reply_text(
                f"Érvénytelen bemenet. Kérjük, válasszon érvényes kampuszt vagy ossza meg a geolokációját az alábbi gombok segítségével:\n"
                f"Lehetőségek: {', '.join(self.campuses)}",
                reply_markup=reply_markup
            )
            logger.info(f"Sent campus keyboard again to user {user_id} due to invalid input")
            return States.CAMPUS.value

    async def get_other_campus(self, update, context):
        user_id = update.message.from_user.id
        logger.info(f"Received other campus input from user {user_id}: {update.message.text}")
        self.form_data.store(user_id, 'campus', update.message.text)
        keyboard = [[KeyboardButton("Telefonszám megosztása", request_contact=True)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder="Ossza meg vagy írja be a telefonszámát")
        await update.message.reply_text(
            "Köszönjük! Kérjük, ossza meg a telefonszámát a gombbal vagy írja be manuálisan (mobil vagy belső IP telefon, pl. +36201234567 vagy 12345):",
            reply_markup=reply_markup
        )
        logger.info(f"Sent phone number keyboard to user {user_id}")
        return States.PHONE.value

    async def get_building(self, update, context):
        user_id = update.message.from_user.id
        logger.info(f"Received building input from user {user_id}: {update.message.text}")
        self.form_data.store(user_id, 'building', update.message.text)
        await update.message.reply_text(
            "Kérjük, adja meg az emeletet (pl. 3. emelet):", reply_markup=ReplyKeyboardRemove()
        )
        return States.FLOOR.value

    async def get_floor(self, update, context):
        user_id = update.message.from_user.id
        logger.info(f"Received floor input from user {user_id}: {update.message.text}")
        self.form_data.store(user_id, 'floor', update.message.text)
        await update.message.reply_text(
            "Kérjük, adja meg a szoba számát vagy a recepciót (pl. 305 vagy Recepció):", reply_markup=ReplyKeyboardRemove()
        )
        return States.ROOM.value

    async def get_room(self, update, context):
        user_id = update.message.from_user.id
        logger.info(f"Received room input from user {user_id}: {update.message.text}")
        self.form_data.store(user_id, 'room', update.message.text)
        keyboard = [[KeyboardButton("Telefonszám megosztása", request_contact=True)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder="Ossza meg vagy írja be a telefonszámát")
        await update.message.reply_text(
            "Köszönjük! Kérjük, ossza meg a telefonszámát a gombbal vagy írja be manuálisan (mobil vagy belső IP telefon, pl. +36201234567 vagy 12345):",
            reply_markup=reply_markup
        )
        logger.info(f"Sent phone number keyboard to user {user_id}")
        return States.PHONE.value

    async def get_phone(self, update, context):
        user_id = update.message.from_user.id
        phone_input = None
        if update.message.contact:
            phone_input = update.message.contact.phone_number
            logger.info(f"Received phone number via contact from user {user_id}: {phone_input}")
        elif update.message.text:
            phone_input = update.message.text.strip()
            logger.info(f"Received typed phone number from user {user_id}: {phone_input}")
            # Basic validation: at least 4 characters, must include digits
            if not re.match(r'^\+?[\d\s\-\.\(\)]{4,}$', phone_input) or not any(char.isdigit() for char in phone_input):
                keyboard = [[KeyboardButton("Telefonszám megosztása", request_contact=True)]]
                reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder="Ossza meg vagy írja be a telefonszámát")
                await update.message.reply_text(
                    "Érvénytelen telefonszám. Kérjük, adjon meg legalább 4 karakteres telefonszámot, amely tartalmaz számjegyeket (pl. +36201234567 vagy 12345), vagy használja a 'Telefonszám megosztása' gombot:",
                    reply_markup=reply_markup
                )
                logger.info(f"Invalid phone number input from user {user_id}: {phone_input}")
                return States.PHONE.value
        else:
            logger.info(f"Received unexpected input from user {user_id}: {update.message}")
            keyboard = [[KeyboardButton("Telefonszám megosztása", request_contact=True)]]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder="Ossza meg vagy írja be a telefonszámát")
            await update.message.reply_text(
                "Kérjük, ossza meg a telefonszámát a gombbal vagy írja be manuálisan (mobil vagy belső IP telefon, pl. +36201234567 vagy 12345):",
                reply_markup=reply_markup
            )
            logger.info(f"Sent phone number keyboard again to user {user_id} due to unexpected input")
            return States.PHONE.value

        logger.info(f"Storing valid phone number for user {user_id}: {phone_input}")
        self.form_data.store(user_id, 'phone', phone_input)
        await update.message.reply_text(
            "Kérjük, adja meg a munkahelyi e-mail címét:", reply_markup=ReplyKeyboardRemove()
        )
        logger.info(f"Advancing to EMAIL state for user {user_id}")
        return States.EMAIL.value

    async def get_email(self, update, context):
        user_id = update.message.from_user.id
        email = update.message.text
        logger.info(f"Received email input from user {user_id}: {email}")
        if "@" in email and "." in email:
            self.form_data.store(user_id, 'email', email)
            await update.message.reply_text(
                "Kérjük, adja meg a probléma rövid leírását (vagy írja be, hogy 'kihagy'):",
                reply_markup=ReplyKeyboardRemove()
            )
            return States.DESCRIPTION.value
        else:
            await update.message.reply_text(
                "Kérjük, adjon meg érvényes e-mail címet (pl. user@company.com).",
                reply_markup=ReplyKeyboardRemove()
            )
            return States.EMAIL.value

    async def get_description(self, update, context):
        user_id = update.message.from_user.id
        description = update.message.text
        logger.info(f"Received description input from user {user_id}: {description}")
        if description.lower() != 'kihagy':
            self.form_data.store(user_id, 'description', description)
        else:
            self.form_data.store(user_id, 'description', 'Nem adott meg leírást')
        keyboard = [[KeyboardButton(option)] for option in self.callback_options]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder="Válasszon: Igen vagy Nem")
        await update.message.reply_text(
            "Kéri a támogatási csapattól a visszahívást? Válasszon 'Igen' vagy 'Nem' az alábbi gombok segítségével:\n"
            "Lehetőségek: Igen, Nem",
            reply_markup=reply_markup
        )
        logger.info(f"Sent callback keyboard to user {user_id}")
        return States.CALLBACK.value

    async def get_callback(self, update, context):
        user_id = update.message.from_user.id
        callback = update.message.text
        logger.info(f"Received callback input from user {user_id}: {callback}")
        if callback in self.callback_options:
            self.form_data.store(user_id, 'callback', callback)
            form_data = self.form_data.get_form_data(user_id)
            if self.email_service.send_email(form_data):
                await update.message.reply_text(
                    "Köszönjük! Az IT támogatási jegye sikeresen benyújtva és elküldve a támogatási csapatnak.",
                    reply_markup=ReplyKeyboardRemove()
                )
                logger.info(f"Ticket submitted successfully for user {user_id}")
            else:
                await update.message.reply_text(
                    "Hiba történt a jegy benyújtása során. Kérjük, próbálja újra később.",
                    reply_markup=ReplyKeyboardRemove()
                )
                logger.error(f"Failed to send email for user {user_id}")
            self.form_data.clear(user_id)
            return ConversationHandler.END
        else:
            keyboard = [[KeyboardButton(option)] for option in self.callback_options]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True, input_field_placeholder="Válasszon: Igen vagy Nem")
            await update.message.reply_text(
                f"Érvénytelen bemenet. Kérjük, válasszon 'Igen' vagy 'Nem' az alábbi gombok segítségével:\n"
                "Lehetőségek: Igen, Nem",
                reply_markup=reply_markup
            )
            logger.info(f"Sent callback keyboard again to user {user_id} due to invalid input")
            return States.CALLBACK.value

    async def cancel(self, update, context):
        user_id = update.message.from_user.id
        logger.info(f"Received /cancel from user {user_id}")
        self.form_data.clear(user_id)
        await update.message.reply_text(
            "A jegy benyújtása megszakítva.", reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END