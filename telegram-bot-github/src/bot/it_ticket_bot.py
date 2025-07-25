# it_ticket_bot.py
# it_ticket_bot.py
import logging
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters
from src.dialog.bot_dialog import BotDialog, States
from src.data.form_data import FormData
from src.services.email_service import EmailService

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ITTicketBot:
    def __init__(self, token, smtp_server, smtp_port, email_sender, email_password, email_recipient):
        logger.debug(f"Initializing ITTicketBot with token: {token[:5]}...")
        if not token:
            logger.error("TELEGRAM_TOKEN is missing or invalid")
            raise ValueError("TELEGRAM_TOKEN is required")
        self.token = token
        self.email_service = EmailService(smtp_server, smtp_port, email_sender, email_password)
        self.form_data = FormData()
        self.email_recipient = email_recipient  # Store IT support email
        self.dialog = BotDialog(self.form_data, self.email_service, self.email_recipient)
        self.application = Application.builder().token(self.token).build()
        logger.debug("ITTicketBot initialized")

    def setup_handlers(self):
        logger.debug("Setting up handlers")
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self.dialog.start)],
            states={
                States.CATEGORY.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.category)],
                States.COMPONENT.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.component)],
                States.ISSUE.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.issue)],
                States.OTHER_ISSUE.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.other_issue)],
                States.CAMPUS.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.campus)],
                States.WARD.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.ward)],
                States.DEPARTMENT.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.department)],
                States.NAME.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.name)],
                States.PHONE.value: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.phone),
                    MessageHandler(filters.CONTACT, self.dialog.phone)
                ],
                States.EMAIL.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.email)],
                States.DESCRIPTION.value: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.description),
                    MessageHandler(filters.Regex('^Skip$'), self.dialog.description)
                ]
            },
            fallbacks=[
                CommandHandler('cancel', self.dialog.cancel),
                MessageHandler(filters.Regex('^PANIC$'), self.dialog.panic)
            ]
        )
        self.application.add_handler(conv_handler)
        logger.info("Bot handlers set up successfully")

    def run(self):
        logger.debug("Starting bot polling")
        self.setup_handlers()
        self.application.run_polling()
        logger.debug("Bot polling ended")
