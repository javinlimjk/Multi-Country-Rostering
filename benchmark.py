import time
from app.models import Staff
from app.optimizer import RosterOptimizer

def run_benchmark():
    # We provide a very simple setup to ensure it solves and we can measure time
    # The optimization we make collapses `count` shifts of `required_staff_count=1`
    # into 1 shift of `required_staff_count=count`.
    # Let's use a demand of 50 people for one time slot and 50 people for another.
    demand_signal = {
        "08:00": 30,
        "08:30": 30,
        "09:00": 30,
    }

    # We provide 100 staff
    staff_list = [
        Staff(id=f"S{i}", name=f"Staff {i}", role="Worker", status="Active", contract_type="Full Time", country="US")
        for i in range(100)
    ]

    optimizer = RosterOptimizer(
        staff_list=staff_list,
        shifts=[],
        demand_signal=demand_signal
    )

    print(f"Number of generated shifts: {len(optimizer.shifts)}")
    print(f"Number of staff: {len(optimizer.staff_list)}")

    t0 = time.time()
    result = optimizer.solve()
    t1 = time.time()

    if result:
        print(f"Solve successful in {t1 - t0:.4f} seconds")
        print(result['metrics'])
    else:
        print(f"Solve failed or infeasible. Time: {t1 - t0:.4f} seconds")

if __name__ == "__main__":
    run_benchmark()
