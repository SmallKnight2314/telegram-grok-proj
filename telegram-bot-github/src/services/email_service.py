import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.header import Header
from email.utils import formataddr
import os
import time  # Added for timing
import re  # Added for email validation

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self, smtp_server: str, smtp_port: int, smtp_username: str, smtp_password: str):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        logger.debug(f"EmailService initialized with SMTP server: {smtp_server}:{smtp_port}")

    def send_email(self, form_data: dict, user_id: int, from_email: str, to_email: str, user_name: str, media_path: str = None) -> bool:
        start_time = time.time()
        logger.info(f"Attempting to send email for user {user_id} from {from_email} to {to_email}")

        try:
            # Validate from_email format
            if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', from_email):
                logger.error(f"Invalid from_email format for user {user_id}: {from_email}")
                return False

            # Create email message
            msg = MIMEMultipart()
            msg['From'] = formataddr((str(Header(user_name, 'utf-8')), from_email))
            logger.debug(f"Set From header: {msg['From']}")
            msg['To'] = to_email
            msg['Subject'] = str(Header(f"chatbot: {form_data['issue']}", 'utf-8'))  # e.g., "chatbot: Ekon - Login Issue"

            # Format email body
            body = (
                "IT Ticket Submission\n"
                "-------------------\n"
                f"User ID: {user_id}\n"
                f"Name: {user_name}\n"
                f"Email: {form_data.get('email', 'N/A')}\n"
                f"Category: {form_data.get('category', 'N/A')}\n"
                f"Component: {form_data.get('component', 'N/A')}\n"
                f"Issue: {form_data.get('issue', 'N/A')}\n"
                f"Description: {form_data.get('description', 'N/A')}\n"
                f"Team: {form_data.get('team', 'N/A')}\n"
                f"Campus: {form_data.get('campus', 'N/A')}\n"
                f"Department: {form_data.get('department', 'N/A')}\n"
                f"Building: {form_data.get('building', 'N/A')}\n"
                f"Floor: {form_data.get('floor', 'N/A')}\n"
                f"Room: {form_data.get('room', 'N/A')}\n"
                f"Latitude: {form_data.get('latitude', 'N/A')}\n"
                f"Longitude: {form_data.get('longitude', 'N/A')}\n"
                f"Phone: {form_data.get('phone', 'N/A')}\n"
                f"Date: {form_data.get('date', 'N/A')}\n"
            )
            logger.debug(f"Email body: {body}")
            msg.attach(MIMEText(body, 'plain', 'utf-8'))

            # Attach media file if provided
            if media_path and os.path.exists(media_path):
                try:
                    with open(media_path, 'rb') as f:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(f.read())
                    encoders.encode_base64(part)
                    filename = os.path.basename(media_path)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename={filename}'
                    )
                    msg.attach(part)
                    file_size = os.path.getsize(media_path) / 1_000_000  # Size in MB
                    logger.info(f"Attached media file to email: {media_path} ({file_size:.2f} MB)")
                except Exception as e:
                    logger.error(f"Failed to attach media file {media_path} for user {user_id}: {str(e)}")
                    return False

            # Send email via SMTP
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=60) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.sendmail(from_email, to_email, msg.as_string())
                logger.info(f"Email successfully sent for user {user_id} to {to_email}")
                logger.debug(f"send_email method took {time.time() - start_time:.2f} seconds")
                return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed for user {user_id}: {str(e)}")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error occurred for user {user_id}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in sending email for user {user_id}: {str(e)}")
            return False
