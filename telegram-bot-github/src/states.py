from enum import Enum

# Defines conversation states for the Telegram bot's ticket submission flow
class States(Enum):
    CATEGORY = 1        # Select issue category (e.g., hardware, software)
    COMPONENT = 2       # Select component (e.g., printer, computer)
    ISSUE = 3           # Select specific issue or 'other'
    OTHER_ISSUE = 4     # Enter custom issue description if 'other' selected
    CAMPUS = 5          # Select campus (e.g., Main Campus)
    DEPARTMENT = 6      # Select department (e.g., Radiology)
    ROOM = 7            # Enter room number
    GEOLOCATION = 8     # Share optional geolocation (latitude, longitude)
    NAME = 9            # Enter user name
    PHONE = 10          # Enter or share phone number
    EMAIL = 11          # Enter email address
    DESCRIPTION = 12    # Enter additional issue details
    MEDIA = 13          # Upload optional single media file (image/video, <75MB)
