# Import Telegram API classes for handling updates and bot functionality
from telegram import Update
# Import Telegram bot framework components for application setup and handlers
from telegram.ext import (
    Application,  # Main class for running the Telegram bot
    CommandHandler,  # Handles bot commands (e.g., /start, /cancel)
    MessageHandler,  # Handles incoming messages based on filters
    ConversationHandler,  # Manages multi-step conversation flows
    filters,  # Filters for processing specific types of messages (e.g., text, location)
)
# Import custom modules for dialog management, email sending, data storage, and states
from src.dialog.bot_dialog import BotDialog  # Handles conversation logic
from src.services.email_service import EmailService  # Manages email sending
from src.data.form_data import FormData  # Stores ticket data in memory
from src.states import States  # Defines conversation states (e.g., CATEGORY, ISSUE)
import os  # For accessing environment variables
import logging  # For logging bot activity and errors

# Configure logging to write to a file with timestamp, logger name, level, and message
logging.basicConfig(
    filename='/app/logs/bot_logs.txt',  # Log file path
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # Log format
    level=logging.DEBUG  # Capture all debug-level and higher messages
)
logger = logging.getLogger(__name__)  # Initialize logger for this module

class ITTicketBot:
    """Main class for the Telegram IT ticket bot, responsible for initialization and handler setup."""
    def __init__(self, token, smtp_server, smtp_port, email_sender, email_password, email_recipient):
        """
        Initialize the bot with Telegram and SMTP configurations.

        Args:
            token (str): Telegram bot token for API access.
            smtp_server (str): SMTP server address for email sending.
            smtp_port (int): SMTP server port (e.g., 587 for TLS).
            email_sender (str): Email address for sending tickets.
            email_password (str): Password for the sender email account.
            email_recipient (str): Email address to receive tickets.
        """
        logger.debug(f"Initializing ITTicketBot with token: {token[:5]}...")
        print(f"Initializing ITTicketBot with token: {token[:5]}...")
        # Validate that all required environment variables are provided
        if not all([token, smtp_server, smtp_port, email_sender, email_password, email_recipient]):
            logger.error("Missing required environment variables for SMTP or Telegram configuration")
            print("ERROR: Missing required environment variables for SMTP or Telegram configuration")
            raise ValueError("Missing required environment variables")
        # Store configuration parameters
        self.token = token
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.email_sender = email_sender
        self.email_password = email_password
        self.email_recipient = email_recipient
        # Initialize EmailService for sending ticket emails
        self.email_service = EmailService(smtp_server, smtp_port, email_sender, email_password)
        print("EmailService instantiated")
        # Initialize FormData for storing ticket data in memory
        self.form_data = FormData()
        print("FormData instantiated")
        # Initialize BotDialog with configuration files and services
        self.bot_dialog = BotDialog(
            '/app/config/topics.json',  # Path to ticket categories and issues
            '/app/config/locations.json',  # Path to location data (campuses, buildings, etc.)
            self.form_data,  # Data storage instance
            self.email_service,  # Email sending instance
            self.email_recipient  # Recipient email for tickets
        )
        print("BotDialog instantiated")
        # Create Telegram bot application with the provided token
        self.application = Application.builder().token(self.token).build()
        logger.debug(f"ITTicketBot initialized, dialog methods: {dir(self.bot_dialog)}")
        print(f"ITTicketBot initialized, dialog methods: {dir(self.bot_dialog)}")

    def setup_handlers(self):
        """Set up the conversation handler with states and fallbacks for the bot."""
        logger.debug("Setting up handlers")
        print("Setting up bot handlers")
        # Define the conversation handler with entry points, states, and fallbacks
        conv_handler = ConversationHandler(
            entry_points=[
                # Start the conversation with the /start command, triggering BotDialog.start
                CommandHandler('start', self.bot_dialog.start)
            ],
            states={
                # Map each conversation state to a BotDialog method, handling text inputs (excluding commands)
                States.CATEGORY.value: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.bot_dialog.category)
                ],
                States.COMPONENT.value: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.bot_dialog.component)
                ],
                States.ISSUE.value: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.bot_dialog.issue)
                ],
                States.CAMPUS.value: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.bot_dialog.campus)
                ],
                States.BUILDING.value: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.bot_dialog.building)
                ],
                States.FLOOR.value: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.bot_dialog.floor)
                ],
                States.DEPARTMENT.value: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.bot_dialog.department)
                ],
                States.ROOM.value: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.bot_dialog.room)
                ],
                States.ADDRESS.value: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.bot_dialog.address)
                ],
                # Handle both text (e.g., "Kihagy") and location inputs for geolocation
                States.GEOLOCATION.value: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.bot_dialog.geolocation),
                    MessageHandler(filters.LOCATION, self.bot_dialog.geolocation)
                ],
                States.NAME.value: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.bot_dialog.name)
                ],
                # Handle both text and contact inputs for phone number
                States.PHONE.value: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.bot_dialog.phone),
                    MessageHandler(filters.CONTACT, self.bot_dialog.phone)
                ],
                # Handle text and "Kihagy" regex for description
                States.DESCRIPTION.value: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.bot_dialog.description),
                    MessageHandler(filters.Regex(r'(?i)^Kihagy$'), self.bot_dialog.description)
                ],
                # Handle photo, video, and "Kihagy" regex for media upload
                States.MEDIA.value: [
                    MessageHandler(filters.PHOTO | filters.VIDEO, self.bot_dialog.media),
                    MessageHandler(filters.Regex(r'(?i)^Kihagy$'), self.bot_dialog.media)
                ],
                States.AUTH.value: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.bot_dialog.auth)
                ]
            },
            fallbacks=[
                # Allow /cancel and /panic commands, and PANIC button to interrupt the conversation
                CommandHandler('cancel', self.bot_dialog.cancel),
                CommandHandler('panic', self.bot_dialog.panic),
                MessageHandler(filters.Regex(r'(?i)^PANIC$'), self.bot_dialog.panic)
            ],
            allow_reentry=True  # Allow restarting the conversation with /start
        )
        # Add the conversation handler to the bot application
        self.application.add_handler(conv_handler)
        logger.info("Bot handlers set up successfully")
        print("Bot handlers set up successfully")

    def run(self):
        """Start the bot by setting up handlers and initiating polling."""
        logger.debug("Starting bot polling")
        print("Starting bot polling")
        self.setup_handlers()  # Configure the conversation handler
        # Start polling to listen for Telegram updates (messages, commands, etc.)
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)
        logger.debug("Bot polling ended")
        print("Bot polling ended")

def main():
    """Entry point for running the bot, loading environment variables and starting the application."""
    # Load environment variables for Telegram and SMTP configuration
    token = os.getenv('TELEGRAM_TOKEN')
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = int(os.getenv('SMTP_PORT', 587))  # Default to 587 for TLS
    email_sender = os.getenv('SMTP_USERNAME')
    email_password = os.getenv('SMTP_PASSWORD')
    email_recipient = os.getenv('EMAIL_RECIPIENT')
    print(f"Loading environment variables: TELEGRAM_TOKEN={token[:5]}..., SMTP_SERVER={smtp_server}, SMTP_PORT={smtp_port}")
    # Create ITTicketBot instance with configuration
    bot = ITTicketBot(token, smtp_server, smtp_port, email_sender, email_password, email_recipient)
    print("ITTicketBot instance created")
    bot.run()  # Start the bot

if __name__ == '__main__':
    main()  # Run the main function when the script is executed
