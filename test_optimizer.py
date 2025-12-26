# test_optimizer.py
from datetime import date
from app.models import Staff, Shift, Country, Role, ShiftType
from app.optimizer import RosterOptimizer

# 1. Create Dummy Data
staff_1 = Staff(id="S001", name="Ali", country=Country.SINGAPORE, role=Role.DRIVER)
staff_2 = Staff(id="S002", name="Bob", country=Country.SINGAPORE, role=Role.DRIVER)
staff_3 = Staff(id="S003", name="Charlie", country=Country.MALAYSIA, role=Role.DRIVER)

# Create 2 shifts for the same day (Morning & Afternoon)
shift_1 = Shift(id="SH01", date=date(2023, 10, 1), type=ShiftType.MORNING, duration_hours=8, required_staff_count=1)
shift_2 = Shift(id="SH02", date=date(2023, 10, 1), type=ShiftType.AFTERNOON, duration_hours=8, required_staff_count=1)

# 2. Run Optimizer
print("--- Starting Test ---")
optimizer = RosterOptimizer(staff_list=[staff_1, staff_2, staff_3], shifts=[shift_1, shift_2])
solution = optimizer.solve()

# 3. Print Results
if solution:
    for assignment in solution:
        print(f"➡️ Staff {assignment.staff_id} assigned to Shift {assignment.shift_id} ({assignment.shift_type})")
else:
    print("Failed to solve.")