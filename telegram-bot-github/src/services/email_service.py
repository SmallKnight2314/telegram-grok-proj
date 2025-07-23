# email_service.py
import smtplib
from email.mime.text import MIMEText
import logging

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self, smtp_server, smtp_port, smtp_username, smtp_password, from_email, to_email):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.from_email = from_email
        self.to_email = to_email

    def send_email(self, form_data, user_id=None):
        msg = MIMEText(form_data)
        msg['Subject'] = f'IT Support Ticket - {user_id}'
        msg['From'] = self.from_email
        msg['To'] = self.to_email
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            logger.info(f"Email sent successfully for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email for user {user_id}: {str(e)}")
            return False
