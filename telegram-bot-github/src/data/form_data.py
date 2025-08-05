# form_data.py
import logging

# Configure logging for debugging and monitoring
logger = logging.getLogger(__name__)

# Class to manage ticket data storage for each user
class FormData:
    def __init__(self):
        # Initialize dictionary to store user data
        self._data = {}

    def store(self, user_id: int, key: str, value):
        # Store a key-value pair for a specific user
        if user_id not in self._data:
            self._data[user_id] = {}
        self._data[user_id][key] = value
        logger.info(f"Stored {key} for user {user_id}: {value}")

    def get_form_data(self, user_id: int) -> str:
        # Format ticket data as a string for email body
        if user_id not in self._data:
            return None
        data = self._data[user_id]
        # Format geolocation as coordinates or "Not provided"
        geolocation = (
            f"({data['latitude']}, {data['longitude']})"
            if data.get('latitude') and data.get('longitude')
            else "Not provided"
        )
        # Format media as file path or "Not provided"
        media = data.get('media', 'Not provided')
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
            f"Email: {data.get('email', 'N/A')}"
        )

    def clear(self, user_id: int):
        # Clear stored data for a user after submission or cancellation
        self._data.pop(user_id, None)
        logger.info(f"Cleared data for user {user_id}")
