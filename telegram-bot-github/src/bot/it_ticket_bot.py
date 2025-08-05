# it_ticket_bot.py
import logging
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters
from src.dialog.bot_dialog import BotDialog, States
from src.data.form_data import FormData
from src.services.email_service import EmailService

# Configure logging for debugging and monitoring
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Main bot class to initialize and run the Telegram bot
class ITTicketBot:
    def __init__(self, token, smtp_server, smtp_port, email_sender, email_password, email_recipient):
        # Initialize bot with Telegram token and SMTP settings
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
        logger.debug("ITTicketBot initialized")

    def setup_handlers(self):
        # Set up conversation handlers for the ticket submission flow
        logger.debug("Setting up handlers")
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self.dialog.start)],
            states={
                # Handle category selection
                States.CATEGORY.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.category)],
                # Handle component selection
                States.COMPONENT.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.component)],
                # Handle issue selection
                States.ISSUE.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.issue)],
                # Handle custom issue description
                States.OTHER_ISSUE.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.other_issue)],
                # Handle campus selection
                States.CAMPUS.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.campus)],
                # Handle department selection
                States.DEPARTMENT.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.department)],
                # Handle room number input
                States.ROOM.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.room)],
                # Handle optional geolocation sharing
                States.GEOLOCATION.value: [
                    MessageHandler(filters.LOCATION, self.dialog.geolocation),
                    MessageHandler(filters.Regex('^Skip$'), self.dialog.geolocation)
                ],
                # Handle name input
                States.NAME.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.name)],
                # Handle phone number input or contact sharing
                States.PHONE.value: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.phone),
                    MessageHandler(filters.CONTACT, self.dialog.phone)
                ],
                # Handle email input
                States.EMAIL.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.email)],
                # Handle additional description input
                States.DESCRIPTION.value: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.description),
                    MessageHandler(filters.Regex('^Skip$'), self.dialog.description)
                ],
                # Handle optional media upload (image or video)
                States.MEDIA.value: [
                    MessageHandler(filters.PHOTO | filters.VIDEO, self.dialog.media),
                    MessageHandler(filters.Regex('^Skip$'), self.dialog.media)
                ]
            },
            fallbacks=[
                CommandHandler('cancel', self.dialog.cancel),  # Cancel the conversation
                MessageHandler(filters.Regex('^PANIC$'), self.dialog.panic)  # Handle panic button
            ]
        )
        self.application.add_handler(conv_handler)
        logger.info("Bot handlers set up successfully")

    def run(self):
        # Start the bot's polling loop
        logger.debug("Starting bot polling")
        self.setup_handlers()
        self.application.run_polling()
        logger.debug("Bot polling ended")
