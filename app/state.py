
from pydantic import BaseModel, Field
from typing import List, Optional

class ShiftItem(BaseModel):
    name: str
    start_time: Optional[int] = None  # Changed to int to match existing logic (e.g. 800)
    duration_hours: Optional[int] = None
    staff_needed: int

class RosterState(BaseModel):
    # This acts as the checklist
    shifts: List[ShiftItem] = []
    month_year: Optional[str] = None
    location: str = "Singapore"

    def missing_fields(self) -> List[str]:
        missing = []
        if not self.shifts:
            missing.append("shift details (name, time, duration, staff count)")
        else:
            for i, shift in enumerate(self.shifts):
                if shift.start_time is None:
                    missing.append(f"start time for the '{shift.name}' shift")
                if shift.duration_hours is None:
                    missing.append(f"duration for the '{shift.name}' shift")
        if not self.month_year:
            missing.append("the month and year for the roster")
        return missing
