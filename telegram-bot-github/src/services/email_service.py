import logging
from datetime import datetime

logger = logging.getLogger(__name__)  # Annotation: Creates a logger instance for form_data.py to log data operations.

class FormData:
    def __init__(self):
        self._data = {}  # Annotation: Initializes a private dictionary to store ticket data per user_id.

    def store(self, user_id: int, key: str, value: str) -> None:
        if user_id not in self._data:
            self._data[user_id] = {}  # Annotation: Creates a new dictionary for user_id if it doesn't exist.
        self._data[user_id][key] = value  # Annotation: Stores key-value pair for the user (e.g., 'category': 'szoftver').
        logger.debug(f"Stored data for user {user_id}: {key} = {value}")  # Annotation: Logs the stored data for debugging.

    def get_form_data(self, user_id: int) -> str:
        logger.debug(f"Retrieving form data for user {user_id}")  # Annotation: Logs retrieval attempt.
        data = self._data.get(user_id, {})  # Annotation: Gets user data or empty dict if not found.
        geolocation = f"({data['latitude']}, {data['longitude']})" if data.get('latitude') and data.get('longitude') else "Not provided"  # Annotation: Formats geolocation as coordinates or "Not provided".
        media = data.get('media', 'Not provided')  # Annotation: Uses media file path or "Not provided".
        form_data = (
            f"Hospital IT Support Ticket Submission\n"
            f"Category: {data.get('category', 'N/A')}\n"
            f"Component: {data.get('component', 'N/A')}\n"
            f"Issue: {data.get('issue', 'N/A')}\n"  # Annotation: Uses new 'issue' field (computed in BotDialog).
            f"Description: {data.get('description', 'N/A')}\n"  # Annotation: Uses existing 'description' field (predefined or custom).
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
            f"Email: {data.get('email', 'N/A')}"
        )  # Annotation: Formats ticket data into a multi-line string as per the desired format.
        logger.debug(f"Form data for user {user_id}: {form_data}")  # Annotation: Logs the formatted data.
        return form_data  # Annotation: Returns the formatted string for EmailService.

    def clear(self, user_id: int) -> None:
        if user_id in self._data:
            del self._data[user_id]  # Annotation: Deletes all data for the user_id.
            logger.debug(f"Cleared data for user {user_id}")  # Annotation: Logs data clearance.
