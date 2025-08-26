import logging  # Annotation: Imports logging module for debug, info, and error logging of bot operations.
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters  # Annotation: Imports Telegram API classes: Application for bot instance, CommandHandler for commands, ConversationHandler for multi-step flows, MessageHandler for messages, and filters for message filtering.
from src.dialog.bot_dialog import BotDialog, States  # Annotation: Imports BotDialog class and States enum from bot_dialog.py and states.py for dialog management and state transitions.
from src.data.form_data import FormData  # Annotation: Imports FormData class from form_data.py for managing ticket data.
from src.services.email_service import EmailService  # Annotation: Imports EmailService class from email_service.py for sending ticket emails.

# Configure logging for debugging and monitoring
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')  # Annotation: Configures global logging with DEBUG level and a timestamped format for all modules.
logger = logging.getLogger(__name__)  # Annotation: Creates a logger instance for this module.

# Main bot class to initialize and run the Telegram bot
class ITTicketBot:
    def __init__(self, token, smtp_server, smtp_port, email_sender, email_password, email_recipient):
        # Initialize bot with Telegram token and SMTP settings
        logger.debug(f"Initializing ITTicketBot with token: {token[:5]}...")  # Annotation: Logs initialization, showing first 5 characters of token for security.
        if not token:  # Annotation: Checks if the Telegram token is provided.
            logger.error("TELEGRAM_TOKEN is missing or invalid")  # Annotation: Logs an error if token is missing or empty.
            raise ValueError("TELEGRAM_TOKEN is required")  # Annotation: Raises ValueError to halt execution if token is missing.
        self.token = token  # Annotation: Stores the Telegram bot token (passed from telegram_bot.py).
        self.email_service = EmailService(smtp_server, smtp_port, email_sender, email_password)  # Annotation: Instantiates EmailService with SMTP settings (used in BotDialog.submit_ticket).
        self.form_data = FormData()  # Annotation: Instantiates FormData for storing ticket data per user (used in BotDialog methods).
        self.email_recipient = email_recipient  # Annotation: Stores the recipient email for ticket submissions (passed to BotDialog).
        self.dialog = BotDialog(self.form_data, self.email_service, self.email_recipient)  # Annotation: Instantiates BotDialog with form_data, email_service, and email_recipient for dialog handling.
        self.application = Application.builder().token(self.token).build()  # Annotation: Builds a Telegram Application instance with the bot token for message handling.
        logger.debug(f"ITTicketBot initialized, dialog methods: {dir(self.dialog)}")  # Annotation: Logs successful initialization and lists BotDialog methods for debugging.

    def setup_handlers(self):
        # Set up conversation handlers for the ticket submission flow
        logger.debug("Setting up handlers")  # Annotation: Logs the start of handler setup.
        conv_handler = ConversationHandler(  # Annotation: Creates a ConversationHandler to manage multi-step ticket submission flow.
            entry_points=[CommandHandler('start', self.dialog.start)],  # Annotation: Defines /start command as the entry point, calling BotDialog.start.
            states={
                # Handle category selection
                States.CATEGORY.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.category)],  # Annotation: Handles non-command text in CATEGORY state, calling BotDialog.category.
                # Handle component selection
                States.COMPONENT.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.component)],  # Annotation: Handles non-command text in COMPONENT state, calling BotDialog.component.
                # Handle issue selection
                States.ISSUE.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.issue)],  # Annotation: Handles non-command text in ISSUE state, calling BotDialog.issue.
                # Handle custom issue description
                States.OTHER_ISSUE.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.other_issue)],  # Annotation: Handles non-command text in OTHER_ISSUE state, calling BotDialog.other_issue.
                # Handle campus selection
                States.CAMPUS.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.campus)],  # Annotation: Handles non-command text in CAMPUS state, calling BotDialog.campus.
                # Handle department selection
                States.DEPARTMENT.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.department)],  # Annotation: Handles non-command text in DEPARTMENT state, calling BotDialog.department.
                # Handle room number input
                States.ROOM.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.room)],  # Annotation: Handles non-command text in ROOM state, calling BotDialog.room.
                # Handle optional geolocation sharing
                States.GEOLOCATION.value: [
                    MessageHandler(filters.LOCATION, self.dialog.geolocation),  # Annotation: Handles location messages in GEOLOCATION state, calling BotDialog.geolocation.
                    MessageHandler(filters.Regex(r'(?i)^Kihagy$'), self.dialog.geolocation)  # Annotation: Handles case-insensitive "Kihagy" (skip) in GEOLOCATION state, calling BotDialog.geolocation.
                ],
                # Handle name input
                States.NAME.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.name)],  # Annotation: Handles non-command text in NAME state, calling BotDialog.name.
                # Handle phone number input or contact sharing
                States.PHONE.value: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.phone),  # Annotation: Handles non-command text in PHONE state, calling BotDialog.phone.
                    MessageHandler(filters.CONTACT, self.dialog.phone)  # Annotation: Handles contact sharing in PHONE state, calling BotDialog.phone.
                ],
                # Handle description input
                States.DESCRIPTION.value: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.description),  # Annotation: Handles non-command text in DESCRIPTION state, calling BotDialog.description.
                    MessageHandler(filters.Regex(r'(?i)^Kihagy$'), self.dialog.description)  # Annotation: Handles case-insensitive "Kihagy" in DESCRIPTION state, calling BotDialog.description.
                ],
                # Handle optional media upload
                States.MEDIA.value: [
                    MessageHandler(filters.PHOTO | filters.VIDEO, self.dialog.media),  # Annotation: Handles photo or video messages in MEDIA state, calling BotDialog.media.
                    MessageHandler(filters.Regex(r'(?i)^Kihagy$'), self.dialog.media)  # Annotation: Handles case-insensitive "Kihagy" in MEDIA state, calling BotDialog.media.
                ],
                # Handle email authentication
                States.AUTH.value: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dialog.auth)]  # Annotation: Handles non-command text in AUTH state, calling BotDialog.auth.
            },
            fallbacks=[
                CommandHandler('cancel', self.dialog.cancel),  # Annotation: Fallback handler for /cancel command, calling BotDialog.cancel.
                MessageHandler(filters.Regex(r'(?i)^PANIC$'), self.dialog.panic)  # Annotation: Fallback handler for case-insensitive "PANIC" messages, calling BotDialog.panic.
            ]
        )
        self.application.add_handler(conv_handler)  # Annotation: Adds the ConversationHandler to the Telegram application for message processing.
        logger.info("Bot handlers set up successfully")  # Annotation: Logs successful handler setup.

    def run(self):
        # Start the bot's polling loop
        logger.debug("Starting bot polling")  # Annotation: Logs the start of the bot’s polling process.
        self.setup_handlers()  # Annotation: Calls setup_handlers to register conversation handlers before polling.
        self.application.run_polling()  # Annotation: Starts the Telegram bot’s polling loop to listen for incoming messages.
        logger.debug("Bot polling ended")  # Annotation: Logs when polling ends (typically only on shutdown).
