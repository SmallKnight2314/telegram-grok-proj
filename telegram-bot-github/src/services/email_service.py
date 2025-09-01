import logging  # Annotation: Imports the logging module for debug, info, warning, and error logging to monitor email sending.
import smtplib  # Annotation: Imports smtplib for sending emails via SMTP.
from email.mime.text import MIMEText  # Annotation: Imports MIMEText for creating the email body.
from email.mime.multipart import MIMEMultipart  # Annotation: Imports MIMEMultipart for emails with attachments.
from email.mime.base import MIMEBase  # Annotation: Imports MIMEBase for handling binary attachments (e.g., images/videos).
from email import encoders  # Annotation: Imports encoders to encode binary attachments.
from email.header import Header  # Annotation: Imports Header for proper encoding of non-ASCII email headers (e.g., From, Subject).
from email.utils import formataddr  # Annotation: Imports formataddr to correctly format the From header with name and email.
import os  # Annotation: Imports os module for file operations, such as checking media file existence.

# Configure logging for debugging and monitoring
logger = logging.getLogger(__name__)  # Annotation: Creates a logger instance for this module to log email-specific events.

class EmailService:
    def __init__(self, smtp_server: str, smtp_port: int, smtp_username: str, smtp_password: str):
        # Initialize EmailService with SMTP configuration
        self.smtp_server = smtp_server  # Annotation: Stores SMTP server address (e.g., 'smtp.example.com').
        self.smtp_port = smtp_port  # Annotation: Stores SMTP port (e.g., 587 for TLS).
        self.smtp_username = smtp_username  # Annotation: Stores SMTP username for authentication.
        self.smtp_password = smtp_password  # Annotation: Stores SMTP password for authentication.
        logger.debug(f"EmailService initialized with SMTP server: {smtp_server}:{smtp_port}")  # Annotation: Logs initialization details for debugging.

    def send_email(self, form_data: str, user_id: int, from_email: str, to_email: str, user_name: str, media_path: str = None) -> bool:
        # Annotation: Sends an email with the ticket data and optional media attachment; returns True on success, False on failure.
        start_time = logging.time.time()  # Annotation: Records start time to measure method execution duration.
        logger.info(f"Attempting to send email for user {user_id} from {from_email} to {to_email}")  # Annotation: Logs email attempt details.

        try:
            # Create email message
            msg = MIMEMultipart()  # Annotation: Initializes a multipart email to support text and attachments.
            # Extract 'issue' from form_data by searching for "Issue: " prefix
            issue = 'N/A'  # Annotation: Default value if 'issue' cannot be found.
            for line in form_data.split('\n'):
                if line.startswith('Issue: '):
                    issue = line[len('Issue: '):]  # Annotation: Extracts the value after "Issue: ".
                    break
            logger.debug(f"Extracted issue from form_data: {issue}")  # Annotation: Logs the extracted issue.

            # Set From header with proper encoding
            msg['From'] = formataddr((str(Header(user_name, 'utf-8')), from_email))  # Annotation: Encodes user_name with UTF-8 and formats as "Name <email>".
            logger.debug(f"Set From header: {msg['From']}")  # Annotation: Logs the raw From header for debugging.
            msg['To'] = to_email  # Annotation: Sets recipient email address.
            msg['Subject'] = str(Header(f"IT Support Ticket - {issue}", 'utf-8'))  # Annotation: Sets subject with UTF-8 encoded issue (e.g., "IT Support Ticket - Alpha System - Login Issue (1)").

            # Attach ticket data as email body
            msg.attach(MIMEText(form_data, 'plain', 'utf-8'))  # Annotation: Attaches the formatted ticket data as plain text with UTF-8 encoding.

            # Attach media file if provided
            if media_path and os.path.exists(media_path):  # Annotation: Checks if media_path is provided and file exists.
                try:
                    with open(media_path, 'rb') as f:  # Annotation: Opens the media file in binary read mode.
                        part = MIMEBase('application', 'octet-stream')  # Annotation: Creates a MIMEBase object for the attachment.
                        part.set_payload(f.read())  # Annotation: Reads and sets the file content as the payload.
                    encoders.encode_base64(part)  # Annotation: Encodes the attachment in base64 for email compatibility.
                    filename = os.path.basename(media_path)  # Annotation: Extracts the filename for the attachment header.
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename={filename}'
                    )  # Annotation: Sets the Content-Disposition header to mark as an attachment.
                    msg.attach(part)  # Annotation: Attaches the media file to the email.
                    logger.info(f"Attached media file to email: {media_path}")  # Annotation: Logs successful attachment.
                except Exception as e:
                    logger.error(f"Failed to attach media file {media_path} for user {user_id}: {str(e)}")  # Annotation: Logs media attachment failure.
                    return False  # Annotation: Returns False if attachment fails.

            # Send email via SMTP
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30) as server:  # Annotation: Opens an SMTP connection with a 30-second timeout.
                server.starttls()  # Annotation: Enables TLS for secure connection.
                server.login(self.smtp_username, self.smtp_password)  # Annotation: Authenticates with SMTP server.
                server.sendmail(from_email, to_email, msg.as_string())  # Annotation: Sends the email.
                logger.info(f"Email successfully sent for user {user_id} to {to_email}")  # Annotation: Logs successful email send.
                logger.debug(f"send_email method took {logging.time.time() - start_time} seconds")  # Annotation: Logs execution time.
                return True  # Annotation: Returns True on success.

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed for user {user_id}: {str(e)}")  # Annotation: Logs authentication failure.
            return False  # Annotation: Returns False for authentication errors.
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error occurred for user {user_id}: {str(e)}")  # Annotation: Logs general SMTP errors (e.g., server down, recipient invalid).
            return False  # Annotation: Returns False for SMTP errors.
        except Exception as e:
            logger.error(f"Unexpected error in sending email for user {user_id}: {str(e)}")  # Annotation: Logs unexpected errors (e.g., network issues).
            return False  # Annotation: Returns False for other errors.
