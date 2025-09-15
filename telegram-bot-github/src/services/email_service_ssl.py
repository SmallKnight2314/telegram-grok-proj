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
        print(f"EmailService initialized with SMTP server: {smtp_server}, port: {smtp_port}, user: {smtp_user}")

    def validate_email(self, email: str) -> bool:
        """Validate email address format."""
        pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        is_valid = bool(re.match(pattern, email))
        if not is_valid:
            logger.error(f"Invalid email format: {email}")
            print(f"ERROR: Invalid email format: {email}")
        else:
            print(f"Validated email: {email}")
        return is_valid

    def send_email(self, form_data: dict, user_id: int, from_email: str, to_email: str, user_name: str, media_path: str = None, retries: int = 2, delay: int = 5) -> bool:
        start_time = datetime.now()
        logger.info(f"Preparing to send email for user {user_id} to {to_email}")
        print(f"Preparing to send email for user {user_id} to {to_email}")
        logger.debug(f"Input parameters: form_data={form_data}, from_email={from_email}, to_email={to_email}, user_name={user_name}, media_path={media_path}")

        # Validate email addresses
        if not self.validate_email(from_email) or not self.validate_email(to_email):
            logger.error(f"Invalid email addresses for user {user_id}: from={from_email}, to={to_email}")
            print(f"ERROR: Invalid email addresses for user {user_id}: from={from_email}, to={to_email}")
            return False

        try:
            msg = MIMEMultipart()
            msg['From'] = formataddr((str(Header(user_name, 'utf-8')), from_email))
            logger.debug(f"Set From header: {msg['From']}")
            print(f"Set From header: {msg['From']}")
            msg['To'] = formataddr((to_email, to_email))
            logger.debug(f"Set To header: {msg['To']}")
            print(f"Set To header: {msg['To']}")
            msg['Subject'] = str(Header(f"chatbot: {form_data.get('issue', 'Unknown Issue')}", 'utf-8'))
            logger.debug(f"Set Subject header: {msg['Subject']}")
            print(f"Set Subject header: {msg['Subject']}")

            if form_data.get('is_other_location', False):
                location_info = f"Cím: {form_data.get('address', 'N/A')}"
            else:
                location_info = (
                    f"Telephely: {form_data.get('campus', 'N/A')}\n"
                    f"Szervezeti egység: {form_data.get('department', 'N/A')}\n"
                    f"Épület: {form_data.get('building', 'N/A')}\n"
                    f"Emelet: {form_data.get('floor', 'N/A')}\n"
                    f"Ajtószám/helység neve: {form_data.get('room', 'N/A')}"
                )

            body = (
                f"Azonosító szám: {user_id}\n"
                f"Név: {form_data.get('name', 'N/A')}\n"
                f"Telefon/Mellék: {form_data.get('phone', 'N/A')}\n"
                f"Email: {form_data.get('email', 'N/A')}\n"
                f"Hiba fajtája: {form_data.get('category', 'N/A')}\n"
                f"Komponens: {form_data.get('component', 'N/A')}\n"
                f"Hiba szám: {form_data.get('issue_id', 'N/A')}\n"
                f"Hiba: {form_data.get('issue', 'N/A')}\n"
                f"Részletek: {form_data.get('description', 'N/A')}\n"
                f"Csapat: {form_data.get('team', 'N/A')}\n"
                f"{location_info}\n"
                f"Szélesség: {form_data.get('latitude', 'N/A')}\n"
                f"Hosszúság: {form_data.get('longitude', 'N/A')}\n"
                f"Dátum: {form_data.get('date', 'N/A')}"
            )
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            logger.debug(f"Email body: {body}")
            print(f"Email body prepared for user {user_id}")

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
                    print(f"Attached media file: {media_path}")
                except Exception as e:
                    logger.error(f"Failed to attach media file {media_path}: {str(e)}", exc_info=True)
                    print(f"ERROR: Failed to attach media file {media_path}: {str(e)}")

            # Try SSL first (port 465 or specified port)
            for attempt in range(retries + 1):
                try:
                    logger.debug(f"Attempt {attempt + 1}: Connecting to SMTP server: {self.smtp_server}:{self.smtp_port} (SSL)")
                    print(f"Attempt {attempt + 1}: Connecting to SMTP server {self.smtp_server}:{self.smtp_port} (SSL)")
                    with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, context=ssl.create_default_context()) as server:
                        logger.debug(f"Logging in with user: {self.smtp_user}")
                        print(f"Logging in with SMTP user: {self.smtp_user}")
                        server.login(self.smtp_user, self.smtp_password)
                        logger.debug("Sending email")
                        print(f"Sending email for user {user_id}")
                        server.send_message(msg)
                        logger.info(f"Email sent successfully for user {user_id} to {to_email} via SSL")
                        print(f"Email sent successfully for user {user_id} to {to_email} via SSL")
                        logger.debug(f"send_email method (SSL) took {(datetime.now() - start_time).total_seconds()} seconds")
                        print(f"send_email method (SSL) took {(datetime.now() - start_time).total_seconds()} seconds")
                        return True
                except smtplib.SMTPConnectError as e:
                    logger.warning(f"Attempt {attempt + 1}: SSL connection failed: {str(e)}")
                    print(f"WARNING: Attempt {attempt + 1}: SSL connection failed: {str(e)}")
                    if attempt == retries:
                        logger.warning("Retrying with TLS")
                        print("Retrying with TLS")
                        break
                    time.sleep(delay)

            # Fallback to TLS (port 587 or specified port)
            for attempt in range(retries + 1):
                try:
                    logger.debug(f"Attempt {attempt + 1}: Connecting to SMTP server: {self.smtp_server}:{self.smtp_port} (TLS)")
                    print(f"Attempt {attempt + 1}: Connecting to SMTP server {self.smtp_server}:{self.smtp_port} (TLS)")
                    with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                        logger.debug("Initiating TLS")
                        print("Initiating TLS")
                        server.starttls(context=ssl.create_default_context())
                        logger.debug(f"Logging in with user: {self.smtp_user}")
                        print(f"Logging in with SMTP user: {self.smtp_user}")
                        server.login(self.smtp_user, self.smtp_password)
                        logger.debug("Sending email")
                        print(f"Sending email for user {user_id}")
                        server.send_message(msg)
                        logger.info(f"Email sent successfully for user {user_id} to {to_email} via TLS")
                        print(f"Email sent successfully for user {user_id} to {to_email} via TLS")
                        logger.debug(f"send_email method (TLS) took {(datetime.now() - start_time).total_seconds()} seconds")
                        print(f"send_email method (TLS) took {(datetime.now() - start_time).total_seconds()} seconds")
                        return True
                except smtplib.SMTPConnectError as e:
                    logger.warning(f"Attempt {attempt + 1}: TLS connection failed: {str(e)}")
                    print(f"WARNING: Attempt {attempt + 1}: TLS connection failed: {str(e)}")
                    if attempt == retries:
                        logger.error(f"All TLS attempts failed for user {user_id}")
                        print(f"ERROR: All TLS attempts failed for user {user_id}")
                        return False
                    time.sleep(delay)

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed for user {user_id}: {str(e)}", exc_info=True)
            print(f"ERROR: SMTP authentication failed for user {user_id}: {str(e)}")
            return False
        except smtplib.SMTPRecipientsRefused as e:
            logger.error(f"SMTP recipients refused for user {user_id}: {str(e)}", exc_info=True)
            print(f"ERROR: SMTP recipients refused for user {user_id}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Failed to send email for user {user_id}: {str(e)}", exc_info=True)
            print(f"ERROR: Failed to send email for user {user_id}: {str(e)}")
            return False
