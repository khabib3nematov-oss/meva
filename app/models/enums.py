from enum import StrEnum


class UserRole(StrEnum):
    OWNER = "OWNER"
    MANAGER = "MANAGER"
    EMPLOYEE = "EMPLOYEE"


class AttendanceStatus(StrEnum):
    PRESENT = "PRESENT"
    LATE = "LATE"
    LEFT_EARLY = "LEFT_EARLY"
    ABSENT = "ABSENT"
    ON_LEAVE = "ON_LEAVE"


class LeaveType(StrEnum):
    DAY_OFF = "DAY_OFF"
    VACATION = "VACATION"
    SICK = "SICK"
