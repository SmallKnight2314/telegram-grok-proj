# form_data.py
import logging  # Annotation: Imports logging module for logging data storage and clearing operations.

# Configure logging for debugging and monitoring
logger = logging.getLogger(__name__)  # Annotation: Creates a logger instance for this module to log form data events.

# Class to manage ticket data storage for each user
class FormData:
    def __init__(self):
        # Initialize dictionary to store user data
        self._data = {}  # Annotation: Initializes an empty dictionary to store form data, with user IDs as keys.

    def store(self, user_id: int, key: str, value):
        # Store a key-value pair for a specific user
        if user_id not in self._data:  # Annotation: Checks if the user_id has no existing data dictionary.
            self._data[user_id] = {}  # Annotation: Creates an empty dictionary for the user if none exists.
        self._data[user_id][key] = value  # Annotation: Stores the key-value pair (e.g., 'category': 'szoftver') in the user's dictionary.
        logger.info(f"Stored {key} for user {user_id}: {value}")  # Annotation: Logs the storage operation for auditing (called in BotDialog.submit_ticket).

    def get_form_data(self, user_id: int) -> str:
        # Format ticket data as a string for email body
        if user_id not in self._data:  # Annotation: Checks if no data exists for the user_id.
            return None  # Annotation: Returns None if no data is found (not typically reached due to prior checks).
        data = self._data[user_id]  # Annotation: Retrieves the user's data dictionary.
        # Format geolocation as coordinates or "Not provided"
        geolocation = (
            f"({data['latitude']}, {data['longitude']})"
            if data.get('latitude') and data.get('longitude')
            else "Not provided"  # Annotation: Formats geolocation as coordinates if both latitude and longitude exist, else "Not provided".
        )
        # Format media as file path or "Not provided"
        media = data.get('media', 'Not provided')  # Annotation: Retrieves media file path or defaults to "Not provided" if missing.
        return (
            f"Hospital IT Support Ticket Submission\n"
            f"Category: {data.get('category', 'N/A')}\n"
            f"Component: {data.get('component', 'N/A')}\n"
            f"Issue: {data.get('description', 'N/A')}\n"
            f"Team: {data.get('team', 'N/A')}\n"
            f"Date: {data.get('date', 'N/A')}\n"
            f"Campus: {data.get('campus', 'N/A')}\n"
            f"Department: {data.get('department', 'N/A')}\n"
            f"Building: {data.get('building', 'N/A')}\n"
            f"Floor: {data.get('floor', 'N/A')}\n"
            f"Room: {data.get('room', 'N/A')}\n"
            f"Geolocation: {geolocation}\n"
            f"Media: {media}\n"
            f"Name: {data.get('name', 'N/A')}\n"
            f"Phone: {data.get('phone', 'N/A')}\n"
            f"Email: {data.get('email', 'N/A')}"  # Annotation: Formats all stored data into a plain text string for email body (passed to EmailService.send_email in email_service.py).
        )

    def clear(self, user_id: int):
        # Clear stored data for a user after submission or cancellation
        self._data.pop(user_id, None)  # Annotation: Removes the user's data dictionary if it exists (called in BotDialog.submit_ticket and BotDialog.cancel).
        logger.info(f"Cleared data for user {user_id}")  # Annotation: Logs the data clearing operation for auditing.
