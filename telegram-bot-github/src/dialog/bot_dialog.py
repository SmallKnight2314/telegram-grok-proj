# bot_dialog.py
import telegram
from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ConversationHandler, MessageHandler, filters
from enum import Enum
import logging
import json
import re
from datetime import datetime

logger = logging.getLogger(__name__)

class States(Enum):
    CATEGORY = 1
    COMPONENT = 2
    ISSUE = 3
    OTHER_ISSUE = 4
    CAMPUS = 5
    DEPARTMENT = 6
    ROOM = 7
    NAME = 8
    PHONE = 9
    EMAIL = 10
    DESCRIPTION = 11

class BotDialog:
    def __init__(self, form_data, email_service, email_recipient):
        self.form_data = form_data
        self.email_service = email_service
        self.email_recipient = email_recipient
        with open('config/topics.json') as f:
            self.topics = json.load(f)
        with open('config/locations.json') as f:
            self.locations = json.load(f)
        self.panic_option = "PANIC"

    async def start(self, update, context):
        user_id = update.message.from_user.id
        logger.info(f"Received /start from user {user_id}")
        keyboard = [[cat] for cat in self.topics['categories'].keys()] + [[self.panic_option]]
        await update.message.reply_text(
            "Welcome to the Hospital IT Support Bot! Let's create your ticket.\n"
            "What type of problem are you experiencing? For urgent issues, select 'PANIC'.",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )
        return States.CATEGORY.value

    async def panic(self, update, context):
        user_id = update.message.from_user.id
        logger.info(f"User {user_id} triggered PANIC button")
        self.form_data.clear(user_id)
        await update.message.reply_text(
            "For urgent issues, please call IT at +1-555-123-4567.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    async def category(self, update, context):
        user_id = update.message.from_user.id
        category = update.message.text
        logger.info(f"Received category from user {user_id}: {category}")
        if category == self.panic_option:
            return await self.panic(update, context)
        if category.lower() in self.topics['categories']:
            context.user_data['category'] = category.lower()
            context.user_data['team'] = self.topics['categories'][category.lower()]['team']
            keyboard = [[comp] for comp in self.topics['categories'][category.lower()]['options'].keys()] + [[self.panic_option]]
            await update.message.reply_text(
                self.topics['categories'][category.lower()]['prompt'],
                reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            )
            return States.COMPONENT.value
        await update.message.reply_text(
            "Invalid category. Please select one:",
            reply_markup=ReplyKeyboardMarkup([[cat] for cat in self.topics['categories'].keys()] + [[self.panic_option]], one_time_keyboard=True)
        )
        return States.CATEGORY.value

    async def component(self, update, context):
        user_id = update.message.from_user.id
        component = update.message.text
        category = context.user_data.get('category')
        logger.info(f"Received component from user {user_id}: {component}")
        if component == self.panic_option:
            return await self.panic(update, context)
        if category and component.lower() in self.topics['categories'][category]['options']:
            context.user_data['component'] = component.lower()
            keyboard = [[f"{v['description']} ({k})" for k, v in self.topics['categories'][category]['options'][component.lower()]['options'].items() if k != 'other']] + [['other'], [self.panic_option]]
            await update.message.reply_text(
                self.topics['categories'][category]['options'][component.lower()]['prompt'],
                reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            )
            return States.ISSUE.value
        await update.message.reply_text(
            "Invalid component. Please select one:",
            reply_markup=ReplyKeyboardMarkup([[comp] for comp in self.topics['categories'][category]['options'].keys()] + [[self.panic_option]], one_time_keyboard=True)
        )
        return States.COMPONENT.value

    async def issue(self, update, context):
        user_id = update.message.from_user.id
        issue = update.message.text
        category = context.user_data.get('category')
        component = context.user_data.get('component')
        logger.info(f"Received issue from user {user_id}: {issue}")
        if issue == self.panic_option:
            return await self.panic(update, context)
        issues = self.topics['categories'][category]['options'][component]['options']
        issue_id = next((k for k, v in issues.items() if v.get('description') == issue.split(' (')[0]), None)
        if issue == 'other':
            await update.message.reply_text(
                issues['other']['prompt'],
                reply_markup=ReplyKeyboardMarkup([[self.panic_option]], one_time_keyboard=True)
            )
            return States.OTHER_ISSUE.value
        elif issue_id:
            context.user_data['issue_id'] = issue_id
            context.user_data['description'] = issues[issue_id]['description']
            keyboard = [[c['name'] for c in self.locations['campuses']]]
            await update.message.reply_text(
                self.locations['prompts']['campus']['en'],
                reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            )
            return States.CAMPUS.value
        await update.message.reply_text(
            "Invalid issue. Please select one:",
            reply_markup=ReplyKeyboardMarkup([[f"{v['description']} ({k})" for k, v in issues.items() if k != 'other']] + [['other'], [self.panic_option]], one_time_keyboard=True)
        )
        return States.ISSUE.value

    async def other_issue(self, update, context):
        user_id = update.message.from_user.id
        description = update.message.text
        logger.info(f"Received other issue from user {user_id}: {description}")
        if description == self.panic_option:
            return await self.panic(update, context)
        context.user_data['issue_id'] = 'other'
        context.user_data['description'] = description
        keyboard = [[c['name'] for c in self.locations['campuses']]]
        await update.message.reply_text(
            self.locations['prompts']['campus']['en'],
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )
        return States.CAMPUS.value

    async def campus(self, update, context):
        user_id = update.message.from_user.id
        campus = update.message.text
        logger.info(f"Received campus from user {user_id}: {campus}")
        campuses = [c['name'] for c in self.locations['campuses']]
        if campus in campuses:
            context.user_data['campus'] = campus
            departments = [d['name'] for d in next(c['departments'] for c in self.locations['campuses'] if c['name'] == campus)]
            keyboard = [[d] for d in departments]
            await update.message.reply_text(
                self.locations['prompts']['department']['en'],
                reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            )
            return States.DEPARTMENT.value
        await update.message.reply_text(
            f"Invalid campus. {self.locations['prompts']['campus']['en']}",
            reply_markup=ReplyKeyboardMarkup([[c] for c in campuses], one_time_keyboard=True)
        )
        return States.CAMPUS.value

    async def department(self, update, context):
        user_id = update.message.from_user.id
        department = update.message.text
        logger.info(f"Received department from user {user_id}: {department}")
        campus = context.user_data['campus']
        departments = next(c['departments'] for c in self.locations['campuses'] if c['name'] == campus)
        department_names = [d['name'] for d in departments]
        if department in department_names:
            context.user_data['department'] = department
            dept_data = next(d for d in departments if d['name'] == department)
            context.user_data['building'] = dept_data['building']
            context.user_data['floor'] = dept_data['floor']
            await update.message.reply_text(
                self.locations['prompts']['room']['en'],
                reply_markup=ReplyKeyboardRemove()
            )
            return States.ROOM.value
        await update.message.reply_text(
            f"Invalid department. {self.locations['prompts']['department']['en']}",
            reply_markup=ReplyKeyboardMarkup([[d] for d in department_names], one_time_keyboard=True)
        )
        return States.DEPARTMENT.value

    async def room(self, update, context):
        user_id = update.message.from_user.id
        room = update.message.text.strip()
        logger.info(f"Received room from user {user_id}: {room}")
        if re.match(self.locations['validation']['room'], room):
            context.user_data['room'] = room
            await update.message.reply_text(
                "Enter your name:",
                reply_markup=ReplyKeyboardRemove()
            )
            return States.NAME.value
        await update.message.reply_text(
            "Invalid room number. Please enter a valid room or office number (e.g., Room 204).",
            reply_markup=ReplyKeyboardRemove()
        )
        return States.ROOM.value

    async def name(self, update, context):
        user_id = update.message.from_user.id
        context.user_data['name'] = update.message.text
        logger.info(f"Received name from user {user_id}: {context.user_data['name']}")
        await update.message.reply_text(
            "Share your phone number (or use the Telegram contact sharing option):",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Share Contact", request_contact=True)]], one_time_keyboard=True)
        )
        return States.PHONE.value

    async def phone(self, update, context):
        user_id = update.message.from_user.id
        if update.message.contact:
            context.user_data['phone'] = update.message.contact.phone_number
        else:
            context.user_data['phone'] = update.message.text
        logger.info(f"Received phone from user {user_id}: {context.user_data['phone']}")
        await update.message.reply_text(
            "Enter your email (required):",
            reply_markup=ReplyKeyboardRemove()
        )
        return States.EMAIL.value

    async def email(self, update, context):
        user_id = update.message.from_user.id
        email = update.message.text
        logger.info(f"Received email from user {user_id}: {email}")
        if not email or not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            await update.message.reply_text(
                "Please enter a valid email address (required):"
            )
            return States.EMAIL.value
        context.user_data['email'] = email
        await update.message.reply_text(
            "Provide additional details (optional, press 'Skip' to submit):",
            reply_markup=ReplyKeyboardMarkup([["Skip"]], one_time_keyboard=True)
        )
        return States.DESCRIPTION.value

    async def description(self, update, context):
        user_id = update.message.from_user.id
        description = update.message.text
        logger.info(f"Received description from user {user_id}: {description}")
        try:
            if description == "Skip" or not description:
                context.user_data['description'] = context.user_data.get('description', 'No additional details provided')
            else:
                context.user_data['description'] = description
            self.form_data.store(user_id, 'category', context.user_data['category'])
            self.form_data.store(user_id, 'component', context.user_data['component'])
            self.form_data.store(user_id, 'issue_id', context.user_data['issue_id'])
            self.form_data.store(user_id, 'description', context.user_data['description'])
            self.form_data.store(user_id, 'team', context.user_data['team'])
            self.form_data.store(user_id, 'campus', context.user_data['campus'])
            self.form_data.store(user_id, 'department', context.user_data['department'])
            self.form_data.store(user_id, 'building', context.user_data['building'])
            self.form_data.store(user_id, 'floor', context.user_data['floor'])
            self.form_data.store(user_id, 'room', context.user_data['room'])
            self.form_data.store(user_id, 'name', context.user_data['name'])
            self.form_data.store(user_id, 'phone', context.user_data['phone'])
            self.form_data.store(user_id, 'email', context.user_data['email'])
            self.form_data.store(user_id, 'date', datetime.now().isoformat())
            form_data = self.form_data.get_form_data(user_id)
            try:
                if self.email_service.send_email(
                    form_data=form_data,
                    user_id=user_id,
                    from_email=context.user_data['email'],
                    to_email=self.email_recipient,
                    user_name=context.user_data['name']
                ):
                    await update.message.reply_text(
                        "Your ticket has been submitted and will be reviewed by IT staff. Thank you!",
                        reply_markup=ReplyKeyboardRemove()
                    )
                else:
                    await update.message.reply_text(
                        "Failed to submit ticket. Please try again or contact IT directly.",
                        reply_markup=ReplyKeyboardRemove()
                    )
            except Exception as e:
                logger.error(f"Email sending failed for user {user_id}: {str(e)}")
                await update.message.reply_text(
                    "Failed to submit ticket due to an error. Please try again or contact IT directly.",
                    reply_markup=ReplyKeyboardRemove()
                )
            self.form_data.clear(user_id)
            return ConversationHandler.END
        except Exception as e:
            logger.error(f"Error in description handler for user {user_id}: {str(e)}")
            await update.message.reply_text(
                "An error occurred. Please try again or select 'PANIC' to contact IT.",
                reply_markup=ReplyKeyboardMarkup([[self.panic_option]], one_time_keyboard=True)
            )
            return States.DESCRIPTION.value

    async def cancel(self, update, context):
        user_id = update.message.from_user.id
        logger.info(f"Received /cancel from user {user_id}")
        self.form_data.clear(user_id)
        await update.message.reply_text(
            "Ticket submission cancelled.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
