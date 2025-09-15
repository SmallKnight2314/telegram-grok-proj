# Import the IntEnum class from the enum module to create an enumeration with integer values
from enum import IntEnum

# Print to console to confirm the states.py module is loaded
print("Loading states.py module")

# Define the States class as an IntEnum to assign integer values to conversation states
class States(IntEnum):
    # Authentication state for email validation (first state in flow, but used at the end)
    AUTH = 0
    # Category selection state for choosing the issue type (e.g., Hardware, Software)
    CATEGORY = 1
    # Component selection state for specifying the affected component (e.g., Printer, PC)
    COMPONENT = 2
    # Issue selection state for detailing the specific problem
    ISSUE = 3
    # Campus selection state for choosing the campus location
    CAMPUS = 4
    # Building selection state for choosing the building within the campus
    BUILDING = 5
    # Floor selection state for choosing the floor within the building
    FLOOR = 6
    # Department selection state for choosing the department on the floor
    DEPARTMENT = 7
    # Room input state for entering the room number
    ROOM = 8
    # Geolocation input state for sharing location (optional)
    GEOLOCATION = 9
    # Name input state for entering the user's name
    NAME = 10
    # Phone input state for entering the user's phone number or contact
    PHONE = 11
    # Description input state for providing issue details
    DESCRIPTION = 12
    # Team state (potentially unused in conversation flow, used for internal team assignment)
    TEAM = 13
    # Media upload state for attaching photos or videos (optional)
    MEDIA = 14
    # Address input state for free-text address when "Other" is selected
    ADDRESS = 15
