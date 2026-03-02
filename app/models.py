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
    status: Optional[str] = "Active" # Active, Inactive
    contract_type: Optional[str] = "Full Time" # Full Time, Part Time
    country: Optional[str] = "SG"

class Shift(BaseModel):
    id: str
    date: date  # ISO Format YYYY-MM-DD
    type: str  # "Morning", "Night"
    start_time: int
    end_time: int
    duration_hours: float
    required_staff_count: int = 1

class RosterAssignment(BaseModel):
    staff_id: str
    shift_id: str
    date: date
    shift_type: str