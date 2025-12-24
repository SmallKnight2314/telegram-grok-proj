# form_data.py
import logging

logger = logging.getLogger(__name__)

class FormData:
    def __init__(self):
        self._data = {}

    def store(self, user_id, key, value):
        if user_id not in self._data:
            self._data[user_id] = {}
        self._data[user_id][key] = value
        logger.info(f"Stored {key} for user {user_id}: {value}")

    def get_form_data(self, user_id):
        if user_id not in self._data:
            return None
        data = self._data[user_id]
        return (
            f"Hospital IT Support Ticket Submission\n"
            f"Category: {data.get('category', 'N/A')}\n"
            f"Component: {data.get('component', 'N/A')}\n"
            f"Issue: {data.get('description', 'N/A')}\n"
            f"Team: {data.get('team', 'N/A')}\n"
            f"Date: {data.get('date', 'N/A')}\n"
            f"Campus: {data.get('campus', 'N/A')}\n"
            f"Ward: {data.get('ward', 'N/A')}\n"
            f"Department: {data.get('department', 'N/A')}\n"
            f"Name: {data.get('name', 'N/A')}\n"
            f"Phone: {data.get('phone', 'N/A')}\n"
            f"Email: {data.get('email', 'N/A')}"
        )

    def clear(self, user_id):
        self._data.pop(user_id, None)
        logger.info(f"Cleared data for user {user_id}")
