# form_data.py
class FormData:
    def __init__(self):
        self._data = {}

    def store(self, user_id, key, value):
        if user_id not in self._data:
            self._data[user_id] = {}
        self._data[user_id][key] = value

    def get_form_data(self, user_id):
        if user_id not in self._data:
            return None
        data = self._data[user_id]
        return (
            f"IT Support Ticket Submission\n"
            f"Subject: {data.get('subject', 'N/A')}\n"
            f"Date: {data.get('date', 'N/A')}\n"
            f"Name: {data.get('name', 'N/A')}\n"
            f"Department: {data.get('department', 'N/A')}\n"
            f"Campus: {data.get('campus', 'N/A')}\n"
            f"Building: {data.get('building', 'N/A')}\n"
            f"Floor: {data.get('floor', 'N/A')}\n"
            f"Room Number/Reception Desk: {data.get('room', 'N/A')}\n"
            f"Phone Number: {data.get('phone', 'N/A')}\n"
            f"Email: {data.get('email', 'N/A')}\n"
            f"Description: {data.get('description', 'N/A')}\n"
            f"Callback Requested: {data.get('callback', 'N/A')}"
        )

    def clear(self, user_id):
        self._data.pop(user_id, None)