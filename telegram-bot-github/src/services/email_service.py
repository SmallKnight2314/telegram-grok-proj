# email_service.py
import logging  # Annotation: Imports logging module for debug, info, and error logging of email operations.
import smtplib  # Annotation: Imports smtplib for sending emails via SMTP protocol.
import ssl  # Annotation: Imports ssl for establishing secure TLS connections to the SMTP server.
from email.mime.text import MIMEText  # Annotation: Imports MIMEText for adding plain text parts to emails.
from email.mime.multipart import MIMEMultipart  # Annotation: Imports MIMEMultipart for creating emails with multiple parts (text + attachments).
from email.mime.image import MIMEImage  # Annotation: Imports MIMEImage for attaching image files (e.g., .jpg, .png).
from email.mime.base import MIMEBase  # Annotation: Imports MIMEBase for attaching non-text files (e.g., videos).
from email import encoders  # Annotation: Imports encoders for base64 encoding of binary attachments.
from email.utils import formataddr  # Annotation: Imports formataddr to format email headers with names and addresses.
import os  # Annotation: Imports os for file path operations and checking file existence.

# Configure logging for debugging and monitoring
logger = logging.getLogger(__name__)  # Annotation: Creates a logger instance for this module to log email-related events.

# Class to handle email sending for ticket submissions
class EmailService:
    def __init__(self, smtp_server: str, smtp_port: int, email_sender: str, email_password: str):
        # Initialize SMTP settings
        self.smtp_server = smtp_server  # Annotation: Stores SMTP server address (passed from ITTicketBot in it_ticket_bot.py).
        self.smtp_port = smtp_port  # Annotation: Stores SMTP port number (e.g., 587 for TLS).
        self.email_sender = email_sender  # Annotation: Stores the sender email address for SMTP authentication.
        self.email_password = email_password  # Annotation: Stores the sender email password for SMTP authentication.
        logger.debug("EmailService initialized")  # Annotation: Logs successful initialization of EmailService.

    def send_email(self, form_data: str, user_id: int, from_email: str, to_email: str, user_name: str, media_path: str = None) -> bool:
        # Send ticket email with optional media attachment
        try:
            # Create a multipart email message
            msg = MIMEMultipart()  # Annotation: Creates a multipart MIME message to hold text and optional attachments.
            msg['From'] = formataddr((user_name, from_email))  # Annotation: Sets the From header with user's name and email (from BotDialog.submit_ticket in bot_dialog.py).
            msg['To'] = to_email  # Annotation: Sets the To header with recipient email (self.email_recipient from ITTicketBot).
            msg['Subject'] = f"IT Support Ticket - {user_id}"  # Annotation: Sets email subject with user ID for identification.
            msg['Reply-To'] = from_email  # Annotation: Sets Reply-To header to user's email for direct replies.

            # Attach the ticket data as plain text
            msg.attach(MIMEText(form_data, 'plain'))  # Annotation: Attaches ticket data (from FormData.get_form_data in form_data.py) as plain text body.

            # Attach media file if provided
            if media_path and os.path.exists(media_path):  # Annotation: Checks if media_path (from BotDialog.media) exists.
                # Determine MIME type based on extension
                ext = os.path.splitext(media_path)[1].lower()  # Annotation: Extracts file extension (e.g., .jpg, .mp4) to determine MIME type.
                if ext in ['.jpg', '.jpeg', '.png']:  # Annotation: Handles image files (.jpg, .jpeg, .png) with MIMEImage.
                    with open(media_path, 'rb') as f:
                        mime_part = MIMEImage(f.read(), name=os.path.basename(media_path))  # Annotation: Reads image file and creates MIMEImage part.
                else:  # Assume video (e.g., .mp4)
                    with open(media_path, 'rb') as f:
                        mime_part = MIMEBase('application', 'octet-stream')  # Annotation: Handles non-image files (e.g., videos) with MIMEBase.
                        mime_part.set_payload(f.read())  # Annotation: Sets file content as payload.
                    encoders.encode_base64(mime_part)  # Annotation: Encodes binary data in base64 for email compatibility.
                    mime_part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(media_path)}')  # Annotation: Adds header to specify attachment filename.
                msg.attach(mime_part)  # Annotation: Attaches the MIME part (image or video) to the email.
                logger.info(f"Attached media file to email for user {user_id}: {media_path}")  # Annotation: Logs successful attachment.

            # Connect to SMTP server and send email
            context = ssl.create_default_context()  # Annotation: Creates a default SSL context for secure SMTP connection.
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:  # Annotation: Opens SMTP connection to the specified server and port.
                server.starttls(context=context)  # Annotation: Upgrades connection to TLS for security.
                server.login(self.email_sender, self.email_password)  # Annotation: Authenticates with SMTP server using sender credentials.
                server.send_message(msg)  # Annotation: Sends the multipart email.
            logger.info(f"Email sent successfully for user {user_id} to {to_email}")  # Annotation: Logs successful email delivery.
            return True  # Annotation: Returns True to indicate success (checked in BotDialog.submit_ticket).
        except Exception as e:
            logger.error(f"Failed to send email for user {user_id}: {str(e)}")  # Annotation: Logs any errors during email sending.
            return False  # Annotation: Returns False to indicate failure (checked in BotDialog.submit_ticket).
