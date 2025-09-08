import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.header import Header
from email.utils import formataddr
import os
from datetime import datetime
import ssl
import re
import time

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self, smtp_server: str, smtp_port: int, smtp_user: str, smtp_password: str):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        logger.debug(f"EmailService initialized with SMTP server: {smtp_server}, port: {smtp_port}, user: {smtp_user}")

    def validate_email(self, email: str) -> bool:
        """Validate email address format."""
        pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        is_valid = bool(re.match(pattern, email))
        if not is_valid:
            logger.error(f"Invalid email format: {email}")
        return is_valid

    def send_email(self, form_data: dict, user_id: int, from_email: str, to_email: str, user_name: str, media_path: str = None, retries: int = 2, delay: int = 5) -> bool:
        start_time = datetime.now()
        logger.info(f"Preparing to send email for user {user_id} to {to_email}")
        logger.debug(f"Input parameters: form_data={form_data}, from_email={from_email}, to_email={to_email}, user_name={user_name}, media_path={media_path}")

        # Validate email addresses
        if not self.validate_email(from_email) or not self.validate_email(to_email):
            logger.error(f"Invalid email addresses for user {user_id}: from={from_email}, to={to_email}")
            return False

        try:
            msg = MIMEMultipart()
            msg['From'] = formataddr((str(Header(user_name, 'utf-8')), from_email))
            logger.debug(f"Set From header: {msg['From']}")
            msg['To'] = formataddr((to_email, to_email))
            logger.debug(f"Set To header: {msg['To']}")
            msg['Subject'] = str(Header(f"chatbot: {form_data.get('issue', 'Unknown Issue')}", 'utf-8'))
            logger.debug(f"Set Subject header: {msg['Subject']}")

            if form_data.get('is_other_location', False):
                location_info = f"Address: {form_data.get('address', 'N/A')}"
            else:
                location_info = (
                    f"Campus: {form_data.get('campus', 'N/A')}\n"
                    f"Department: {form_data.get('department', 'N/A')}\n"
                    f"Building: {form_data.get('building', 'N/A')}\n"
                    f"Floor: {form_data.get('floor', 'N/A')}\n"
                    f"Room: {form_data.get('room', 'N/A')}"
                )

            body = (
                f"User ID: {user_id}\n"
                f"Name: {form_data.get('name', 'N/A')}\n"
                f"Phone: {form_data.get('phone', 'N/A')}\n"
                f"Email: {form_data.get('email', 'N/A')}\n"
                f"Category: {form_data.get('category', 'N/A')}\n"
                f"Component: {form_data.get('component', 'N/A')}\n"
                f"Issue ID: {form_data.get('issue_id', 'N/A')}\n"
                f"Issue: {form_data.get('issue', 'N/A')}\n"
                f"Description: {form_data.get('description', 'N/A')}\n"
                f"Team: {form_data.get('team', 'N/A')}\n"
                f"{location_info}\n"
                f"Latitude: {form_data.get('latitude', 'N/A')}\n"
                f"Longitude: {form_data.get('longitude', 'N/A')}\n"
                f"Date: {form_data.get('date', 'N/A')}"
            )
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            logger.debug(f"Email body: {body}")

            if media_path and os.path.exists(media_path):
                try:
                    with open(media_path, 'rb') as attachment:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(attachment.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f"attachment; filename= {os.path.basename(media_path)}"
                    )
                    msg.attach(part)
                    logger.debug(f"Attached media file: {media_path}")
                except Exception as e:
                    logger.error(f"Failed to attach media file {media_path}: {str(e)}", exc_info=True)

            # Try SSL first (port 465 or specified port)
            for attempt in range(retries + 1):
                try:
                    logger.debug(f"Attempt {attempt + 1}: Connecting to SMTP server: {self.smtp_server}:{self.smtp_port} (SSL)")
                    with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, context=ssl.create_default_context()) as server:
                        logger.debug(f"Logging in with user: {self.smtp_user}")
                        server.login(self.smtp_user, self.smtp_password)
                        logger.debug("Sending email")
                        server.send_message(msg)
                        logger.info(f"Email sent successfully for user {user_id} to {to_email} via SSL")
                        logger.debug(f"send_email method (SSL) took {(datetime.now() - start_time).total_seconds()} seconds")
                        return True
                except smtplib.SMTPConnectError as e:
                    logger.warning(f"Attempt {attempt + 1}: SSL connection failed: {str(e)}")
                    if attempt == retries:
                        logger.warning("Retrying with TLS")
                        break
                    time.sleep(delay)

            # Fallback to TLS (port 587 or specified port)
            for attempt in range(retries + 1):
                try:
                    logger.debug(f"Attempt {attempt + 1}: Connecting to SMTP server: {self.smtp_server}:{self.smtp_port} (TLS)")
                    with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                        logger.debug("Initiating TLS")
                        server.starttls(context=ssl.create_default_context())
                        logger.debug(f"Logging in with user: {self.smtp_user}")
                        server.login(self.smtp_user, self.smtp_password)
                        logger.debug("Sending email")
                        server.send_message(msg)
                        logger.info(f"Email sent successfully for user {user_id} to {to_email} via TLS")
                        logger.debug(f"send_email method (TLS) took {(datetime.now() - start_time).total_seconds()} seconds")
                        return True
                except smtplib.SMTPConnectError as e:
                    logger.warning(f"Attempt {attempt + 1}: TLS connection failed: {str(e)}")
                    if attempt == retries:
                        logger.error(f"All TLS attempts failed for user {user_id}")
                        return False
                    time.sleep(delay)

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed for user {user_id}: {str(e)}", exc_info=True)
            return False
        except smtplib.SMTPRecipientsRefused as e:
            logger.error(f"SMTP recipients refused for user {user_id}: {str(e)}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Failed to send email for user {user_id}: {str(e)}", exc_info=True)
            return False
