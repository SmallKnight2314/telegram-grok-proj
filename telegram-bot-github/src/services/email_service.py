# email_service.py
import smtplib
from email.mime.text import MIMEText
import logging
import re

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self, smtp_server, smtp_port, sender, password, recipient):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender = sender
        self.password = password
        self.recipient = recipient

    def send_email(self, form_data, user_id):
        try:
            # Extract user email from form_data string
            email_match = re.search(r'Email: (.+?)(?:\n|$)', form_data)
            user_email = email_match.group(1) if email_match else self.sender
            # Extract subject for email header
            subject_match = re.search(r'Subject: (.+?)(?:\n|$)', form_data)
            subject = subject_match.group(1) if subject_match else 'N/A'
            
            msg = MIMEText(form_data)
            msg['Subject'] = f'IT Support Ticket - {subject}'
            msg['From'] = user_email  # Display user's email
            msg['To'] = self.recipient

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender, self.password)  # Authenticate with bot's credentials
                server.sendmail(self.sender, self.recipient, msg.as_string())  # Send from bot's email
            logger.info(f"Email sent successfully to {self.recipient} appearing from {user_email}")
            return True
        except Exception as e:
            logger.error(f"Error sending email for user {user_id}: {e}")
            return False
