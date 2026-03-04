# app/optimizer.py
from ortools.sat.python import cp_model
from app.models import Staff, Shift, Country, RosterAssignment
from collections import Counter, defaultdict
from datetime import date, timedelta
import time

class RosterOptimizer:
    def __init__(self, staff_list: list[Staff], shifts: list[Shift], rules: dict = None, demand_signal: dict = None):
        # Filter out inactive staff
        self.staff_list = [s for s in staff_list if s.status == "Active"] if staff_list else []

        # If demand_signal is provided, generate shifts from it
        if demand_signal:
            self.shifts = self._generate_shifts_from_demand(demand_signal)
        else:
            self.shifts = shifts

        # Default rules if none provided
        self.rules = rules if rules else {'min_rest_hours': 10, 'max_consecutive_days': 6, 'max_weekly_hours': 44}

        # Auto-generate staff if none provided
        if not self.staff_list:
            self.staff_list = self._generate_synthetic_staff()

        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        self.assignments = {} 

    def _generate_synthetic_staff(self):
        """
        Estimates staff needed based on peak concurrency + buffer.
        """
        events = []
        for s in self.shifts:
            d = s.date
            start_min = (d.toordinal() * 1440) + (s.start_time // 100 * 60) + (s.start_time % 100)
            end_min = start_min + int(s.duration_hours * 60)

            events.append((start_min, 1))
            events.append((end_min, -1))

        events.sort()

        max_overlap = 0
        current_overlap = 0
        for _, change in events:
            current_overlap += change
            max_overlap = max(max_overlap, current_overlap)

        # --- VOLUME CHECK ---
        # Calculate total hours required
        total_shift_hours = sum(s.duration_hours * s.required_staff_count for s in self.shifts)

        # Calculate capacity per person
        max_weekly_hours = self.rules.get('max_weekly_hours', 44)
        if self.shifts:
            dates = [s.date for s in self.shifts]
            period_days = (max(dates) - min(dates)).days + 1
        else:
            period_days = 7

        period_weeks = max(period_days / 7.0, 1.0)
        capacity_per_person = period_weeks * max_weekly_hours

        # Minimum staff by volume (hours)
        min_staff_volume = total_shift_hours / capacity_per_person

        # Add buffer (20% for volume, 50% for concurrency flexibility)
        needed_volume = int(min_staff_volume * 1.2) + 1
        needed_concurrency = int(max_overlap * 1.5) + 2

        needed = max(needed_volume, needed_concurrency)

        print(f"Auto-generating {needed} staff (Peak Demand: {max_overlap}, Volume Need: {min_staff_volume:.1f})")

        generated = []
        for i in range(needed):
            generated.append(Staff(
                id=f"Open_Pos_{i+1}",
                name=f"Open Position {i+1}",
                role="Driver",
                status="Active",
                contract_type="Full Time",
                country="SG"
            ))
        return generated

    def _generate_shifts_from_demand(self, demand_signal):
        """
        Converts demand signal {"08:00": 5, "08:30": 6} into Shift objects.
        Strategy: Create shifts for each demand slot.
        This effectively creates a 'task' based roster.
        """
        generated_shifts = []
        today_date = date.today() # Use today as default date for generated shifts

        for time_str, count in demand_signal.items():
            if count <= 0: continue

            # Parse start time
            try:
                h, m = map(int, time_str.split(':'))
                start_t = h * 100 + m

                # Assume 30 min duration for each slot from demand planner
                start_min = h * 60 + m
                end_min = start_min + 30

                end_h = (end_min // 60) % 24
                end_m = end_min % 60
                end_t = end_h * 100 + end_m

                # Create 'count' number of shifts for this slot
                # Each shift needs 1 person
                for i in range(count):
                    shift = Shift(
                        id=f"GEN_{time_str}_{i}",
                        date=today_date,
                        type="Generated",
                        start_time=start_t,
                        end_time=end_t,
                        duration_hours=0.5, # 30 mins
                        required_staff_count=1
                    )
                    generated_shifts.append(shift)
            except Exception as e:
                raise ValueError(f"Error generating shift for {time_str}: {e}") from e

        return generated_shifts

    def solve(self):
        start_time = time.time()

        # 1. CREATE VARIABLES
        for staff in self.staff_list:
            for shift in self.shifts:
                self.assignments[(staff.id, shift.id)] = self.model.NewBoolVar(f'assign_{staff.id}_{shift.id}')

        # 2. HARD CONSTRAINTS
        self._apply_shift_coverage()
        self._apply_conflict_constraints() 
        self._apply_min_rest_period() 
        self._apply_max_consecutive_days()
        self._apply_max_weekly_hours()

        # 3. SOFT CONSTRAINTS (Fairness)
        self._minimize_variance()

        # 4. SOLVE
        self.solver.parameters.max_time_in_seconds = 10.0
        status = self.solver.Solve(self.model)
        
        duration = time.time() - start_time

        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            result_list = self._extract_solution()
            
            # --- METRICS CALCULATION ---
            metrics = self.calculate_metrics_only(result_list)
            metrics["runtime_seconds"] = round(duration, 4)
            metrics["status"] = self.solver.StatusName(status)
            
            return {
                "assignments": result_list,
                "metrics": metrics
            }
        return None

    def calculate_metrics_only(self, assignments):
        """Helper to recalculate stats on manual edits"""
        active = [x for x in assignments if x.shift_type not in ['Off', 'Leave', 'MC']]
        counts = Counter([x.staff_id for x in active])
        gap = (max(counts.values()) - min(counts.values())) if counts else 0
        return {
            "fairness_gap": gap,
            "shift_count": len(active),
            "runtime_seconds": 0.0,
            "status": "Manual Update"
        }

    # --- CONSTRAINT IMPLEMENTATIONS ---
    def _apply_shift_coverage(self):
        for shift in self.shifts:
            staff_assigned = [self.assignments[(staff.id, shift.id)] for staff in self.staff_list]
            self.model.Add(sum(staff_assigned) == shift.required_staff_count)

    def _apply_conflict_constraints(self):
        shifts_by_date = {}
        for shift in self.shifts:
            if shift.date not in shifts_by_date: shifts_by_date[shift.date] = []
            shifts_by_date[shift.date].append(shift)
        for staff in self.staff_list:
            for date, daily_shifts in shifts_by_date.items():
                self.model.Add(sum(self.assignments[(staff.id, s.id)] for s in daily_shifts) <= 1)

    def _apply_min_rest_period(self):
        min_rest_minutes = int(self.rules.get('min_rest_hours', 10) * 60)

        if not self.shifts:
            return

        min_date = min(s.date for s in self.shifts)

        def shift_start_minutes(s):
            day_diff = (s.date - min_date).days
            start_min = (s.start_time // 100) * 60 + (s.start_time % 100)
            return day_diff * 24 * 60 + start_min

        def shift_end_minutes(s):
            return shift_start_minutes(s) + int(s.duration_hours * 60)

        # Sort all shifts by start time
        sorted_shifts = sorted(self.shifts, key=shift_start_minutes)

        # Since shifts are not pre-assigned to staff in the optimizer, we must
        # create constraints for all staff for pairs of shifts that are too close in time.
        # However, by sorting the shifts by start time, we only need to compare each shift
        # with subsequent shifts until the start time of the subsequent shift is safely
        # beyond the end time of the current shift plus the min_rest_minutes.
        # This reduces the number of comparisons drastically compared to O(N^2).
        # We apply this for all staff to prevent any staff member from taking both shifts.

        for staff in self.staff_list:
            # We iterate through the sorted shifts
            for i in range(len(sorted_shifts)):
                shift_a = sorted_shifts[i]
                a_end = shift_end_minutes(shift_a)

                # Only look ahead to adjacent shifts in time
                for j in range(i + 1, len(sorted_shifts)):
                    shift_b = sorted_shifts[j]
                    b_start = shift_start_minutes(shift_b)

                    # If shift_b starts after shift_a ends + min_rest, all subsequent shifts will too
                    if b_start >= a_end + min_rest_minutes:
                        break

                    # Otherwise, shift_b is too close to shift_a. They cannot both be assigned to this staff.
                    self.model.Add(self.assignments[(staff.id, shift_a.id)] + self.assignments[(staff.id, shift_b.id)] <= 1)


    def _apply_max_consecutive_days(self):
        max_d = self.rules.get('max_consecutive_days', 6)
        shifts_by_date = defaultdict(list)
        for s in self.shifts:
            shifts_by_date[s.date].append(s)
        all_dates = sorted(shifts_by_date.keys())
        
        for staff in self.staff_list:
            # Sliding window of size max_d + 1
            for i in range(len(all_dates) - max_d):
                window = all_dates[i : i + max_d + 1]
                worked_flags = []
                for d in window:
                    worked_flags.append(sum(self.assignments[(staff.id, s.id)] for s in shifts_by_date[d]))
                # Sum of "worked days" in window must be <= max_d
                self.model.Add(sum(worked_flags) <= max_d)

    def _apply_max_weekly_hours(self):
        max_h = self.rules.get('max_weekly_hours', 44)
        all_dates = sorted(list(set(s.date for s in self.shifts)))
        
        # Check every 7-day window
        # Convert hours to minutes for integer constraint
        max_minutes = int(max_h * 60)

        for i in range(len(all_dates) - 6):
            window_dates = all_dates[i : i+7]
            for staff in self.staff_list:
                minutes_in_window = []
                for shift in self.shifts:
                    if shift.date in window_dates:
                        # shift.duration_hours is float, so we multiply by 60 and cast to int
                        shift_duration_min = int(shift.duration_hours * 60)
                        minutes_in_window.append(self.assignments[(staff.id, shift.id)] * shift_duration_min)
                self.model.Add(sum(minutes_in_window) <= max_minutes)

    def _minimize_variance(self):
        # Calculate total shifts per staff
        num_shifts = []
        for staff in self.staff_list:
            num_shifts.append(sum(self.assignments[(staff.id, s.id)] for s in self.shifts))
        
        if num_shifts:
            min_s = self.model.NewIntVar(0, 100, 'min_shifts')
            max_s = self.model.NewIntVar(0, 100, 'max_shifts')
            self.model.AddMinEquality(min_s, num_shifts)
            self.model.AddMaxEquality(max_s, num_shifts)
            self.model.Minimize(max_s - min_s)

    def _extract_solution(self):
        results = []
        for staff in self.staff_list:
            for shift in self.shifts:
                if self.solver.Value(self.assignments[(staff.id, shift.id)]) == 1:
                    results.append(RosterAssignment(
                        staff_id=staff.id, 
                        shift_id=shift.id, 
                        date=shift.date,
                        shift_type=shift.type
                    ))
        return results

    # --- VALIDATION & RECOMMENDATION LOGIC ---
    
    def validate_roster(self, fixed_assignments: list[dict], shift_definitions: list[dict]):
        """Checks for Understaffing and Rest Violations based on manual edits."""
        return validate_roster_logic(fixed_assignments, shift_definitions, self.rules)

    def recommend_replacement(self, date_target, shift_name, fixed_assignments, shift_definitions):
        """
        Smart Remediation:
        Phase 1: Find OFF Staff
        Phase 2: Find SWAP Candidates (Domino)
        """
        # Convert Data
        if isinstance(date_target, str): date_target = date.fromisoformat(date_target)
        for x in fixed_assignments:
            if isinstance(x['date'], str): x['date'] = date.fromisoformat(x['date'])

        # 1. Analyze Day
        workload = Counter()
        day_assignments = {} 
        shift_counts = Counter()

        for x in fixed_assignments:
            if x['shift'] not in ["Off", "Leave", "MC"]: 
                workload[x['staff_id']] += 1
            if x['date'] == date_target:
                day_assignments[x['staff_id']] = x['shift']
                if x['shift'] not in ["Off", "Leave", "MC"]:
                    shift_counts[x['shift']] += 1

        target_def = next((s for s in shift_definitions if s['Name'] == shift_name), None)
        if not target_def: return {"candidate": None, "message": "Unknown Shift"}

        # 2. Identify Candidates
        # All staff in the roster
        if self.staff_list:
            all_staff_ids = [s.id for s in self.staff_list]
        else:
            all_staff_ids = list(set(x['staff_id'] for x in fixed_assignments))

        # Candidates are those explicitly marked "Off" OR those with no assignment record for the day (None)
        candidates_off = [sid for sid in all_staff_ids if day_assignments.get(sid) in ["Off", None]]
        
        # --- PHASE 1: DIRECT FILL ---
        valid_off = self._filter_candidates(candidates_off, date_target, target_def, fixed_assignments, shift_definitions)
        if valid_off:
            valid_off.sort(key=lambda x: workload[x]) # Pick least worked (Fairness)
            best = valid_off[0]
            return {
                "candidate": best, 
                "message": f"🌟 Recommended: {best} (Least Worked: {workload[best]} shifts). Fairness check passed."
            }

        # --- PHASE 2: SWAP FROM SURPLUS ---
        surplus_shifts = []
        for s_def in shift_definitions:
            name = s_def['Name']
            req = s_def['Staff Needed']
            if shift_counts[name] > req:
                surplus_shifts.append(name)
        
        if surplus_shifts:
            candidates_swap = [sid for sid, shift in day_assignments.items() if shift in surplus_shifts]
            valid_swap = self._filter_candidates(candidates_swap, date_target, target_def, fixed_assignments, shift_definitions)
            
            if valid_swap:
                valid_swap.sort(key=lambda x: workload[x])
                best = valid_swap[0]
                current_shift = day_assignments[best]
                return {
                    "candidate": best, 
                    "message": f"🔄 Swap Suggestion: Move {best} from '{current_shift}' (Surplus) to '{shift_name}'."
                }

        return {"candidate": None, "message": "No solution found. All staff are busy or restricted."}

    def _filter_candidates(self, candidates, date_target, target_def, fixed_assignments, shift_definitions):
        """Helper to check Rest Constraints for a list of candidate staff"""
        valid = []
        t_start_val = int(target_def['Start Time'])
        t_dur_hours = float(target_def['Duration'])

        t_start_min = (t_start_val // 100) * 60 + (t_start_val % 100)
        t_end_min = t_start_min + int(t_dur_hours * 60)
        
        min_rest_min = int(self.rules.get('min_rest_hours', 10) * 60)

        for sid in candidates:
            is_legal = True
            
            # PREV DAY CHECK
            prev_day = date_target - timedelta(days=1)
            prev_assign = next((x for x in fixed_assignments if x['staff_id'] == sid and x['date'] == prev_day), None)
            if prev_assign and prev_assign['shift'] not in ["Off", "Leave", "MC"]:
                p_def = next((s for s in shift_definitions if s['Name'] == prev_assign['shift']), None)
                if p_def:
                    p_start_val = int(p_def['Start Time'])
                    p_dur_hours = float(p_def['Duration'])
                    p_start_min = (p_start_val // 100) * 60 + (p_start_val % 100)
                    p_end_min = p_start_min + int(p_dur_hours * 60)

                    gap = (t_start_min + 24 * 60) - p_end_min
                    if gap < min_rest_min: is_legal = False

            # NEXT DAY CHECK
            if is_legal:
                next_day = date_target + timedelta(days=1)
                next_assign = next((x for x in fixed_assignments if x['staff_id'] == sid and x['date'] == next_day), None)
                if next_assign and next_assign['shift'] not in ["Off", "Leave", "MC"]:
                    n_def = next((s for s in shift_definitions if s['Name'] == next_assign['shift']), None)
                    if n_def:
                        n_start_val = int(n_def['Start Time'])
                        n_start_min = (n_start_val // 100) * 60 + (n_start_val % 100)

                        gap = (n_start_min + 24 * 60) - t_end_min
                        if gap < min_rest_min: is_legal = False
            
            if is_legal: valid.append(sid)
        return valid

def validate_roster_logic(fixed_assignments: list[dict], shift_definitions: list[dict], rules: dict):
    # Helper: Convert dates (Work on copy to avoid mutating input)
    working_assignments = []
    for x in fixed_assignments:
        item = x.copy()
        if isinstance(item['date'], str):
            item['date'] = date.fromisoformat(item['date'])
        working_assignments.append(item)

    errors = []
    # Build Shift Map
    shift_map = {}
    for s in shift_definitions:
        start_val = int(s['Start Time'])
        dur_hours = float(s['Duration'])
        start_min = (start_val // 100) * 60 + (start_val % 100)
        end_min = start_min + int(dur_hours * 60)
        shift_map[s['Name']] = {'start_min': start_min, 'end_min': end_min, 'req': s['Staff Needed'], 'dur_hours': dur_hours}

    # 1. Check Understaffing
    coverage_counter = Counter()
    for x in working_assignments:
        if x['shift'] in shift_map:
            coverage_counter[(x['date'], x['shift'])] += 1

    all_dates = sorted(list(set(x['date'] for x in working_assignments)))
    for d in all_dates:
        for s_def in shift_definitions:
            s_name = s_def['Name']
            req = s_def['Staff Needed']
            actual = coverage_counter[(d, s_name)]
            if actual < req:
                missing = req - actual
                errors.append({
                    "type": "Understaffing",
                    "msg": f"📉 Understaffed: {d} '{s_name}' needs {req} staff, has {actual}.",
                    "search_query": "",
                    "meta": {"date": d.isoformat(), "shift": s_name}
                })

    # 2. Check Rest Violations
    min_rest_min = int(rules.get('min_rest_hours', 10) * 60)
    # Sort by Staff -> Date
    sorted_data = sorted(working_assignments, key=lambda x: (x['staff_id'], x['date']))

    for i in range(len(sorted_data) - 1):
        curr = sorted_data[i]
        next_s = sorted_data[i+1]

        if curr['staff_id'] != next_s['staff_id']: continue
        if curr['shift'] not in shift_map or next_s['shift'] not in shift_map: continue

        day_diff = (next_s['date'] - curr['date']).days

        # Adjacent Days Check
        if day_diff == 1:
            prev_def = shift_map[curr['shift']]
            curr_def = shift_map[next_s['shift']]

            prev_end_min = prev_def['end_min']
            curr_start_min = curr_def['start_min'] + 24 * 60 # Next day adds 24h
            gap_min = curr_start_min - prev_end_min

            if gap_min < min_rest_min:
                errors.append({
                    "type": "Rest Violation",
                    "msg": f"⚠️ Rest Violation: {curr['staff_id']} on {next_s['date']}. Gap is {gap_min/60:.1f}h (Min {min_rest_min/60:.1f}h).",
                    "search_query": "minimum rest period",
                    "meta": {"date": next_s['date'].isoformat(), "shift": next_s['shift'], "violator": curr['staff_id']}
                })

    # 3. Check Max Daily Hours
    max_daily_h = rules.get('max_daily_hours', 12)
    staff_day_hours = defaultdict(float)
    for x in working_assignments:
        if x['shift'] in shift_map:
            dur = shift_map[x['shift']]['dur_hours']
            staff_day_hours[(x['staff_id'], x['date'])] += dur

    for (staff_id, d), total_hours in staff_day_hours.items():
        if total_hours > max_daily_h:
            errors.append({
                "type": "Daily Hours Violation",
                "msg": f"⏳ Daily Hours Violation: {staff_id} on {d}. Worked {total_hours}h (Max {max_daily_h}h).",
                "search_query": "maximum daily working hours",
                "meta": {"date": d.isoformat(), "violator": staff_id}
            })

    # 4. Check Max Weekly Hours
    max_weekly_h = rules.get('max_weekly_hours', 44)
    staff_dates = defaultdict(list)
    for x in working_assignments:
        if x['shift'] in shift_map:
            staff_dates[x['staff_id']].append((x['date'], shift_map[x['shift']]['dur_hours']))

    for staff_id, shifts in staff_dates.items():
        shifts.sort(key=lambda y: y[0])
        all_dates_worked = sorted(list(set(y[0] for y in shifts)))

        if not all_dates_worked:
            continue

        day_dict = defaultdict(float)
        for d, hrs in shifts:
            day_dict[d] += hrs

        min_date = all_dates_worked[0]
        max_date = all_dates_worked[-1]

        current_date = min_date
        while current_date <= max_date:
            window_hours = sum(day_dict[current_date + timedelta(days=i)] for i in range(7))
            if window_hours > max_weekly_h:
                errors.append({
                    "type": "Weekly Hours Violation",
                    "msg": f"📅 Weekly Hours Violation: {staff_id} from {current_date} to {current_date + timedelta(days=6)}. Worked {window_hours}h (Max {max_weekly_h}h).",
                    "search_query": "maximum weekly working hours",
                    "meta": {"date": current_date.isoformat(), "violator": staff_id}
                })
            current_date += timedelta(days=1)

    # 5. Check Max Consecutive Days
    max_consecutive_days = rules.get('max_consecutive_days', 6)
    for staff_id, shifts in staff_dates.items():
        worked_days = sorted(list(set(y[0] for y in shifts)))

        streak = 1
        for i in range(1, len(worked_days)):
            if (worked_days[i] - worked_days[i-1]).days == 1:
                streak += 1
                if streak > max_consecutive_days:
                    errors.append({
                        "type": "Consecutive Days Violation",
                        "msg": f"🔥 Consecutive Days Violation: {staff_id} worked {streak} days ending on {worked_days[i]} (Max {max_consecutive_days}).",
                        "search_query": "maximum consecutive working days",
                        "meta": {"date": worked_days[i].isoformat(), "violator": staff_id}
                    })
            else:
                streak = 1

    return errors
