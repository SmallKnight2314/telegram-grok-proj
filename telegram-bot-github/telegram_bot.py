import os
from dotenv import load_dotenv
import logging
from src.bot.it_ticket_bot import ITTicketBot

# Configure logging (avoid overriding it_ticket_bot.py's logging)
logger = logging.getLogger(__name__)

def main():
    logger.debug("Starting telegram_bot.py")
    
    # Load environment variables from .env file
    load_dotenv()
    
    # Retrieve environment variables with defaults where appropriate
    token = os.getenv('TELEGRAM_TOKEN')
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = os.getenv('SMTP_PORT', '587')
    smtp_username = os.getenv('SMTP_USERNAME')
    smtp_password = os.getenv('SMTP_PASSWORD')
    email_recipient = os.getenv('EMAIL_RECIPIENT')
    
    # Validate required environment variables
    if not all([token, smtp_server, smtp_username, smtp_password, email_recipient]):
        missing = [var for var, val in [
            ('TELEGRAM_TOKEN', token),
            ('SMTP_SERVER', smtp_server),
            ('SMTP_USERNAME', smtp_username),
            ('SMTP_PASSWORD', smtp_password),
            ('EMAIL_RECIPIENT', email_recipient)
        ] if not val]
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    
    # Validate SMTP_PORT is a valid integer
    try:
        smtp_port = int(smtp_port)
    except (ValueError, TypeError):
        logger.error(f"Invalid SMTP_PORT value: {smtp_port}. Must be a valid integer.")
        raise ValueError(f"Invalid SMTP_PORT value: {smtp_port}. Must be a valid integer.")
    
    try:
        # Initialize and run the bot
        logger.debug("Initializing ITTicketBot")
        bot = ITTicketBot(
            token=token,
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            email_sender=smtp_username,
            email_password=smtp_password,
            email_recipient=email_recipient
        )
        logger.info("ITTicketBot initialized successfully")
        bot.run()
        logger.info("Bot running")
    except Exception as e:
        logger.error(f"Failed to run ITTicketBot: {str(e)}")
        raise

if __name__ == '__main__':
    main()
