# email_service.py
import smtplib
from email.mime.text import MIMEText
import logging

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self, smtp_server, smtp_port, sender, password, recipient):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender = sender
        self.password = password
        self.recipient = recipient

    def send_email(self, form_data):
        try:
            msg = MIMEText(form_data)
            msg['Subject'] = 'New IT Problem Ticket'
            msg['From'] = self.sender
            msg['To'] = self.recipient

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender, self.password)
                server.sendmail(self.sender, self.recipient, msg.as_string())
            return True
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return False