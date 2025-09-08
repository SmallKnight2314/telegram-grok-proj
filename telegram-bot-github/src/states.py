from enum import Enum  # Annotation: Imports Enum from the enum module to define a set of named constants for conversation states.

class States(Enum):  # Annotation: Defines States as an Enum class to represent conversation states, used in BotDialog (bot_dialog.py) and ITTicketBot (it_ticket_bot.py) for state transitions.
    AUTH = 0  # Annotation: Represents the state for email authentication, handled by BotDialog.auth in bot_dialog.py.
    CATEGORY = 1  # Annotation: Represents the state for selecting a ticket category (e.g., szoftver), handled by BotDialog.category.
    COMPONENT = 2  # Annotation: Represents the state for selecting a component (e.g., Ecostat), handled by BotDialog.component.
    ISSUE = 3  # Annotation: Represents the state for selecting a specific issue (e.g., login error), handled by BotDialog.issue.
    CAMPUS = 4  # Annotation: Represents the state for selecting a campus (from locations.json), handled by BotDialog.campus.
    DEPARTMENT = 5  # Annotation: Represents the state for selecting a department (from locations.json), handled by BotDialog.department.
    ROOM = 6  # Annotation: Represents the state for entering a room number, handled by BotDialog.room.
    GEOLOCATION = 7  # Annotation: Represents the state for optional geolocation sharing, handled by BotDialog.geolocation.
    NAME = 8  # Annotation: Represents the state for entering the user's name, handled by BotDialog.name.
    PHONE = 9  # Annotation: Represents the state for entering or sharing a phone number, handled by BotDialog.phone.
    EMAIL = 10  # Annotation: Represents an unused state (email input moved to AUTH in current bot_dialog.py version).
    DESCRIPTION = 11  # Annotation: Represents the state for entering additional ticket description, handled by BotDialog.description.
    MEDIA = 12  # Annotation: Represents the state for uploading optional media (photo/video), handled by BotDialog.media.
    ADDRESS = 13  # New state for address input
