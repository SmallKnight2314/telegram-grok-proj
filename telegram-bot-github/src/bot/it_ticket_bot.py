import logging
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, filters
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
        self.email_recipient = email_recipient
        self.dialog = BotDialog(self.form_data, self.email_service, self.email_recipient)
        self.application = Application.builder().token(self.token).build()
        logger.debug(f"ITTicketBot initialized, dialog methods: {dir(self.dialog)}")

    def setup_handlers(self):
        logger.debug("Setting up handlers")
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self.dialog.start)],
            states={
                States.CATEGORY.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.category)],
                States.COMPONENT.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.component)],
                States.ISSUE.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.issue)],
                States.CAMPUS.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.campus)],
                States.DEPARTMENT.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.department)],
                States.ROOM.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.room)],
                States.GEOLOCATION.value: [
                    MessageHandler(filters.LOCATION, self.dialog.geolocation),
                    MessageHandler(filters.Regex(r'(?i)^Kihagy$'), self.dialog.geolocation)
                ],
                States.NAME.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.name)],
                States.PHONE.value: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.phone),
                    MessageHandler(filters.CONTACT, self.dialog.phone)
                ],
                States.DESCRIPTION.value: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.description),
                    MessageHandler(filters.Regex(r'(?i)^Kihagy$'), self.dialog.description)
                ],
                States.MEDIA.value: [
                    MessageHandler(filters.PHOTO | filters.VIDEO, self.dialog.media),
                    MessageHandler(filters.Regex(r'(?i)^Kihagy$'), self.dialog.media)
                ],
                States.AUTH.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.auth)]
            },
            fallbacks=[
                CommandHandler('cancel', self.dialog.cancel),
                MessageHandler(filters.Regex(r'(?i)^PANIC$'), self.dialog.panic)
            ],
            allow_reentry=True
        )
        self.application.add_handler(conv_handler)
        logger.info("Bot handlers set up successfully")

    def run(self):
        logger.debug("Starting bot polling")
        self.setup_handlers()
        self.application.run_polling()
        logger.debug("Bot polling ended")
