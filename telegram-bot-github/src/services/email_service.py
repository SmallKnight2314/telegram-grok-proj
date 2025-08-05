# email_service.py
import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formataddr
import os

# Configure logging for debugging and monitoring
logger = logging.getLogger(__name__)

# Class to handle email sending for ticket submissions
class EmailService:
    def __init__(self, smtp_server: str, smtp_port: int, email_sender: str, email_password: str):
        # Initialize SMTP settings
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.email_sender = email_sender
        self.email_password = email_password
        logger.debug("EmailService initialized")

    def send_email(self, form_data: str, user_id: int, from_email: str, to_email: str, user_name: str, media_path: str = None) -> bool:
        # Send ticket email with optional media attachment
        try:
            # Create a multipart email message
            msg = MIMEMultipart()
            msg['From'] = formataddr((user_name, from_email))
            msg['To'] = to_email
            msg['Subject'] = f"IT Support Ticket - {user_id}"
            msg['Reply-To'] = from_email

            # Attach the ticket data as plain text
            msg.attach(MIMEText(form_data, 'plain'))

            # Attach media file if provided
            if media_path and os.path.exists(media_path):
                # Determine MIME type based on extension
                ext = os.path.splitext(media_path)[1].lower()
                if ext in ['.jpg', '.jpeg', '.png']:
                    with open(media_path, 'rb') as f:
                        mime_part = MIMEImage(f.read(), name=os.path.basename(media_path))
                else:  # Assume video (e.g., .mp4)
                    with open(media_path, 'rb') as f:
                        mime_part = MIMEBase('application', 'octet-stream')
                        mime_part.set_payload(f.read())
                    encoders.encode_base64(mime_part)
                    mime_part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(media_path)}')
                msg.attach(mime_part)
                logger.info(f"Attached media file to email for user {user_id}: {media_path}")

            # Connect to SMTP server and send email
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.email_sender, self.email_password)
                server.send_message(msg)
            logger.info(f"Email sent successfully for user {user_id} to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email for user {user_id}: {str(e)}")
            return False
