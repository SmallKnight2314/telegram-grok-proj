import os  # Annotation: Imports the os module for accessing environment variables and handling file paths.
from dotenv import load_dotenv  # Annotation: Imports load_dotenv from python-dotenv to load environment variables from a .env file.
import logging  # Annotation: Imports logging module for debug, info, and error logging throughout the application.
from src.bot.it_ticket_bot import ITTicketBot  # Annotation: Imports ITTicketBot class from it_ticket_bot.py, responsible for initializing and running the Telegram bot.

logger = logging.getLogger(__name__)  # Annotation: Creates a logger instance for this module to log events specific to telegram_bot.py.

def main():  # Annotation: Defines the main function, serving as the entry point when the script is run directly.
    logger.debug("Starting telegram_bot.py")  # Annotation: Logs a debug message indicating the script has started.
    load_dotenv()  # Annotation: Loads environment variables from .env file into os.environ (expects TELEGRAM_TOKEN, SMTP_SERVER, etc.).
    token = os.getenv('TELEGRAM_TOKEN')  # Annotation: Retrieves the Telegram bot token from environment variables for bot authentication.
    smtp_server = os.getenv('SMTP_SERVER')  # Annotation: Retrieves SMTP server address for sending ticket emails.
    smtp_port = os.getenv('SMTP_PORT', '587')  # Annotation: Retrieves SMTP port, defaults to 587 (standard for TLS) if not specified.
    smtp_username = os.getenv('SMTP_USERNAME')  # Annotation: Retrieves SMTP username (email sender) for email authentication.
    smtp_password = os.getenv('SMTP_PASSWORD')  # Annotation: Retrieves SMTP password for email authentication.
    email_recipient = os.getenv('EMAIL_RECIPIENT')  # Annotation: Retrieves recipient email address for ticket submissions.

    if not all([token, smtp_server, smtp_username, smtp_password, email_recipient]):  # Annotation: Checks if all required environment variables are set.
        missing = [var for var, val in [  # Annotation: Creates a list of missing variable names if any are None or empty.
            ('TELEGRAM_TOKEN', token),
            ('SMTP_SERVER', smtp_server),
            ('SMTP_USERNAME', smtp_username),
            ('SMTP_PASSWORD', smtp_password),
            ('EMAIL_RECIPIENT', email_recipient)
        ] if not val]
        logger.error(f"Missing required environment variables: {', '.join(missing)}")  # Annotation: Logs an error listing missing variables for debugging.
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")  # Annotation: Raises ValueError to halt execution if variables are missing.

    try:  # Annotation: Attempts to convert smtp_port to an integer, handling potential errors.
        smtp_port = int(smtp_port)  # Annotation: Converts smtp_port (from .env) to an integer for use in EmailService (email_service.py).
    except (ValueError, TypeError):  # Annotation: Catches ValueError or TypeError if smtp_port is non-numeric or invalid.
        logger.error(f"Invalid SMTP_PORT value: {smtp_port}. Must be a valid integer.")  # Annotation: Logs an error for invalid SMTP port.
        raise ValueError(f"Invalid SMTP_PORT value: {smtp_port}. Must be a valid integer.")  # Annotation: Raises ValueError to halt execution.

    try:  # Annotation: Attempts to initialize and run ITTicketBot, catching any initialization or runtime errors.
        logger.debug("Initializing ITTicketBot")  # Annotation: Logs the start of ITTicketBot initialization for debugging.
        bot = ITTicketBot(  # Annotation: Instantiates ITTicketBot (from it_ticket_bot.py) with token and SMTP settings.
            token=token,
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            email_sender=smtp_username,
            email_password=smtp_password,
            email_recipient=email_recipient
        )
        logger.info("ITTicketBot initialized successfully")  # Annotation: Logs successful initialization of the bot.
        bot.run()  # Annotation: Calls ITTicketBot.run (in it_ticket_bot.py) to set up handlers and start polling for Telegram messages.
        logger.info("Bot running")  # Annotation: Logs that the bot is actively running and polling.
    except Exception as e:  # Annotation: Catches any exceptions during bot initialization or execution.
        logger.error(f"Failed to run ITTicketBot: {str(e)}")  # Annotation: Logs the error with details for debugging.
        raise  # Annotation: Re-raises the exception to stop the script and signal failure.

if __name__ == '__main__':  # Annotation: Checks if the script is run directly (not imported as a module).
    main()  # Annotation: Calls the main function to start the bot application.
