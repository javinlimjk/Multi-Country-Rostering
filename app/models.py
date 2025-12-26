from pydantic import BaseModel
from typing import List, Optional
from datetime import date
from enum import Enum

class Country(str, Enum):
    SINGAPORE = "SG"
    MALAYSIA = "MY"
    SAUDI_ARABIA = "SA"

class Role(str, Enum):
    DRIVER = "Driver"
    LOADER = "Loader"
    SUPERVISOR = "Supervisor"

class Staff(BaseModel):
    id: str
    name: Optional[str] = "Unknown"
    role: Optional[str] = "Driver"
    country: Optional[str] = "SG"

class Shift(BaseModel):
    id: str
    date: str  # ISO Format YYYY-MM-DD
    type: str  # "Morning", "Night"
    start_time: int
    end_time: int
    duration_hours: int
    required_staff_count: int = 1

class RosterAssignment(BaseModel):
    staff_id: str
    shift_id: str
    date: date
    shift_type: str