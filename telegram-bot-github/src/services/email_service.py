# email_service.py
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
import logging

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self, smtp_server, smtp_port, sender, password):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender = sender  # Authorized email for SMTP (e.g., ticket@hospital.com)
        self.password = password

    def send_email(self, form_data, user_id=None, from_email=None, to_email=None, user_name=None):
        logger.debug(f"Sending email to {to_email} appearing from {from_email} with form_data: {form_data}")
        msg = MIMEText(form_data)
        msg['Subject'] = f'IT Support Ticket - {user_id or "Unknown"}'
        if from_email and user_name:
            # Encode the user_name for non-ASCII characters and format the From header
            msg['From'] = formataddr((str(Header(user_name, 'utf-8')), from_email))
            msg['Reply-To'] = from_email  # Set Reply-To to user's email
        else:
            msg['From'] = self.sender
            msg['Reply-To'] = self.sender
        msg['To'] = to_email

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30) as server:
                server.starttls()
                logger.debug(f"Logging in with {self.sender}")
                server.login(self.sender, self.password)
                server.sendmail(self.sender, to_email, msg.as_string())  # Use sender for SMTP transaction
            logger.info(f"Email sent successfully to {to_email} for user {user_id}")
            return True
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed for user {user_id}: {str(e)}", exc_info=True)
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error for user {user_id}: {str(e)}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending email for user {user_id}: {str(e)}", exc_info=True)
            return False
