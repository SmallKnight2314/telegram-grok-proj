import logging
from datetime import datetime
from typing import Any, Dict

logger = logging.getLogger(__name__)

class FormData:
    def __init__(self):
        self._data = {}  # Initialize private dictionary to store ticket data per user_id

    def store(self, user_id: int, key: str, value: Any) -> None:
        if user_id not in self._data:
            self._data[user_id] = {}  # Create new dictionary for user_id if it doesn't exist
        self._data[user_id][key] = value  # Store key-value pair for the user
        logger.debug(f"Stored data for user {user_id}: {key} = {value}")

    def get_form_data(self, user_id: int) -> Dict[str, Any]:
        logger.debug(f"Retrieving form data for user {user_id}")
        return self._data.get(user_id, {})  # Return user data dictionary or empty dict if not found

    def clear(self, user_id: int) -> None:
        if user_id in self._data:
            del self._data[user_id]  # Delete all data for the user_id
            logger.debug(f"Cleared data for user {user_id}")
