import math
import random
from datetime import date, timedelta
from app.models import Staff, Shift, Role, Country
from app.optimizer import RosterOptimizer
from app.rules import get_rules_for_country

class StaffingForecaster:
    def calculate_needs_simulation(self, shift_inputs: list, days=7, country="SG", absence_buffer=0.15):
        logs = []
        try:
            # 1. Fetch Rules
            country_code = country.value if hasattr(country, 'value') else str(country)
            rules = get_rules_for_country(country_code)

            # 2. Generate Shifts
            shifts = self._generate_dummy_shifts(shift_inputs, days)
            
            if not shifts:
                 return {
                     "min_staff": 0, "rec_staff": 0, "buffer_size": 0, 
                     "logs": ["⚠️ No valid shifts found. Check 'Staff Needed' in configuration."], 
                     "status": "SKIPPED"
                 }

            # 3. CALCULATE THEORETICAL MINIMUM (Using Optimization)
            daily_max_staff = 0
            for item in shift_inputs:
                daily_max_staff += self._safe_int(item.get("Staff Needed"))
            
            # Start search at daily max (absolute floor)
            current_staff_count = max(1, daily_max_staff)
            min_feasible_found = False
            
            logs.append(f"🕵️‍♂️ Phase 1: Finding Absolute Minimum (starting at {current_staff_count})...")

            # Search loop for Minimum Feasible
            # Safety break at 200 to prevent infinite loops
            while not min_feasible_found and current_staff_count < 200:
                staff_pool = self._generate_dummy_staff(current_staff_count, country_code)
                
                # Run Optimizer in "Check Mode" (Fast, 1.0s limit)
                optimizer = RosterOptimizer(staff_pool, shifts, rules)
                optimizer.solver.parameters.max_time_in_seconds = 1.0 
                
                result = optimizer.solve()
                
                if result:
                    min_feasible_found = True
                    logs.append(f"✅ Feasible Solution Found: {current_staff_count} Staff")
                else:
                    current_staff_count += 1
            
            min_required = current_staff_count

            # 4. CALCULATE RECOMMENDED (With Buffer)
            try:
                raw_rec = min_required / (1.0 - float(absence_buffer))
                rec_required = math.ceil(raw_rec)
            except ZeroDivisionError:
                rec_required = min_required
            
            buffer_added = rec_required - min_required
            logs.append(f"🛡️ Phase 2: Applying {int(float(absence_buffer)*100)}% Resilience Buffer...")
            logs.append(f"💡 Recommendation: Add {buffer_added} extra staff to cover MC/Leave.")

            return {
                "min_staff": min_required,
                "rec_staff": rec_required,
                "buffer_size": buffer_added,
                "logs": logs,
                "status": "OPTIMAL"
            }

        except Exception as e:
            import traceback
            print(traceback.format_exc()) # Print to Docker logs
            return {
                "min_staff": 0, "rec_staff": 0, "buffer_size": 0,
                "logs": [f"Crash in Forecaster: {str(e)}"],
                "status": "ERROR"
            }

    def _generate_dummy_shifts(self, shift_inputs, days):
        shifts = []
        # Use TODAY, not hardcoded 2023
        start_date = date.today()
        
        for d in range(days):
            curr = start_date + timedelta(days=d)
            # --- FIX IS HERE: Convert Date Object to String ---
            curr_str = curr.isoformat()
            
            for item in shift_inputs:
                count = self._safe_int(item.get("Staff Needed"))
                start_t = self._safe_int(item.get("Start Time"))
                dur = self._safe_int(item.get("Duration"))
                name = str(item.get("Name", "Unnamed"))

                if count <= 0 or dur <= 0: continue

                start_min = (start_t // 100) * 60 + (start_t % 100)
                end_min = start_min + int(dur * 60)

                end_h = (end_min // 60) % 24
                end_m = end_min % 60
                end_t = end_h * 100 + end_m
                
                for i in range(count):
                    shifts.append(Shift(
                        id=f"{name}_{d}_{i}", 
                        date=curr_str, # <--- Passing String now, not Object
                        type=name, 
                        start_time=start_t, 
                        end_time=end_t, 
                        duration_hours=dur,
                        required_staff_count=1
                    ))
        return shifts

    def _generate_dummy_staff(self, count, country):
        staff = []
        roles = [Role.DRIVER, Role.LOADER, Role.SUPERVISOR]
        for i in range(count):
            s_role = random.choice(roles)
            # Staff model expects string for country/role
            staff.append(Staff(
                id=f"S{i}", 
                name=f"Simulated Staff {i}", 
                country=str(country), 
                role=str(s_role.value)
            ))
        return staff

    def _safe_int(self, val):
        """Prevents crashes from floats/strings in UI inputs"""
        try:
            if val is None: return 0
            if isinstance(val, (float, int)): return int(val)
            return int(float(val)) 
        except (ValueError, TypeError): return 0
