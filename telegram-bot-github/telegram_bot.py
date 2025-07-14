# telegram_bot.py
from src.bot.it_ticket_bot import ITTicketBot
import os

def main():
    bot = ITTicketBot(
        token=os.getenv('TELEGRAM_TOKEN'),
        smtp_server=os.getenv('SMTP_SERVER'),
        smtp_port=int(os.getenv('SMTP_PORT')),
        email_sender=os.getenv('EMAIL_SENDER'),
        email_password=os.getenv('EMAIL_PASSWORD'),
        email_recipient=os.getenv('EMAIL_RECIPIENT')
    )
    bot.run()

if __name__ == '__main__':
    main()