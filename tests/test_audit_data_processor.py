import pytest
from datetime import date
from app.compliance import AuditDataProcessor

class TestAuditDataProcessor:

    def test_empty_assignments(self):
        assignments = []
        shift_definitions = [{"Name": "Morning", "Duration": 8}]
        result = AuditDataProcessor.process(assignments, shift_definitions)
        assert result == "No assignments provided."

    def test_missing_staff_id(self):
        assignments = [
            {"date": "2023-10-01", "shift": "Morning"}
        ]
        shift_definitions = [{"Name": "Morning", "Duration": 8}]
        result = AuditDataProcessor.process(assignments, shift_definitions)
        assert result == "Invalid assignment data: missing staff_id"

    def test_basic_metrics(self):
        assignments = [
            {"staff_id": "S1", "date": "2023-10-01", "shift": "Morning"},
            {"staff_id": "S1", "date": "2023-10-02", "shift": "Morning"},
            {"staff_id": "S1", "date": "2023-10-03", "shift": "Evening"}
        ]
        shift_definitions = [
            {"Name": "Morning", "Duration": 8},
            {"Name": "Evening", "Duration": 6}
        ]
        result = AuditDataProcessor.process(assignments, shift_definitions)
        expected = (
            "Staff S1:\n"
            "  - Total Hours: 22\n"
            "  - Max Consecutive Days: 3\n"
            "  - Shift Pattern: 2023-10-01: Morning (8h), 2023-10-02: Morning (8h), 2023-10-03: Evening (6h)..."
        )
        assert result == expected

    def test_off_leave_mc_shifts(self):
        assignments = [
            {"staff_id": "S1", "date": "2023-10-01", "shift": "Morning"},
            {"staff_id": "S1", "date": "2023-10-02", "shift": "Leave"},
            {"staff_id": "S1", "date": "2023-10-03", "shift": "Morning"},
            {"staff_id": "S1", "date": "2023-10-04", "shift": "Off"},
            {"staff_id": "S1", "date": "2023-10-05", "shift": "Morning"},
            {"staff_id": "S1", "date": "2023-10-06", "shift": "MC"}
        ]
        shift_definitions = [{"Name": "Morning", "Duration": 8}]
        result = AuditDataProcessor.process(assignments, shift_definitions)
        expected = (
            "Staff S1:\n"
            "  - Total Hours: 24\n"
            "  - Max Consecutive Days: 1\n"
            "  - Shift Pattern: 2023-10-01: Morning (8h), 2023-10-03: Morning (8h), 2023-10-05: Morning (8h)..."
        )
        assert result == expected

    def test_missing_shift_duration_fallback(self):
        assignments = [
            {"staff_id": "S1", "date": "2023-10-01", "shift": "Morning"}
        ]
        shift_definitions = [{"Name": "Morning"}]  # Missing Duration
        result = AuditDataProcessor.process(assignments, shift_definitions)
        expected = (
            "Staff S1:\n"
            "  - Total Hours: 8\n"
            "  - Max Consecutive Days: 1\n"
            "  - Shift Pattern: 2023-10-01: Morning (8h)..."
        )
        assert result == expected

    def test_invalid_date_string(self):
        assignments = [
            {"staff_id": "S1", "date": "2023-10-01", "shift": "Morning"},
            {"staff_id": "S1", "date": "invalid-date", "shift": "Morning"},
            {"staff_id": "S1", "date": "2023-10-03", "shift": "Morning"}
        ]
        shift_definitions = [{"Name": "Morning", "Duration": 8}]
        result = AuditDataProcessor.process(assignments, shift_definitions)

        # invalid-date should be skipped, meaning the sequence is interrupted
        # consecutive days becomes 1 for 10-01 and 1 for 10-03. Max is 1.
        # the duration is added before the date is checked, so it adds to total hours
        # total hours is 24 (for the three shifts)
        expected = (
            "Staff S1:\n"
            "  - Total Hours: 24\n"
            "  - Max Consecutive Days: 1\n"
            "  - Shift Pattern: 2023-10-01: Morning (8h), 2023-10-03: Morning (8h)..."
        )
        assert result == expected

    def test_datetime_date_object(self):
        assignments = [
            {"staff_id": "S1", "date": date(2023, 10, 1), "shift": "Morning"},
            {"staff_id": "S1", "date": date(2023, 10, 2), "shift": "Morning"}
        ]
        shift_definitions = [{"Name": "Morning", "Duration": 8}]
        result = AuditDataProcessor.process(assignments, shift_definitions)
        expected = (
            "Staff S1:\n"
            "  - Total Hours: 16\n"
            "  - Max Consecutive Days: 2\n"
            "  - Shift Pattern: 2023-10-01: Morning (8h), 2023-10-02: Morning (8h)..."
        )
        assert result == expected

    def test_multiple_staff_grouping(self):
        assignments = [
            {"staff_id": "S1", "date": "2023-10-01", "shift": "Morning"},
            {"staff_id": "S2", "date": "2023-10-01", "shift": "Evening"}
        ]
        shift_definitions = [
            {"Name": "Morning", "Duration": 8},
            {"Name": "Evening", "Duration": 6}
        ]
        result = AuditDataProcessor.process(assignments, shift_definitions)
        expected_s1 = (
            "Staff S1:\n"
            "  - Total Hours: 8\n"
            "  - Max Consecutive Days: 1\n"
            "  - Shift Pattern: 2023-10-01: Morning (8h)..."
        )
        expected_s2 = (
            "Staff S2:\n"
            "  - Total Hours: 6\n"
            "  - Max Consecutive Days: 1\n"
            "  - Shift Pattern: 2023-10-01: Evening (6h)..."
        )
        assert result == f"{expected_s1}\n{expected_s2}"

    def test_shift_pattern_truncation(self):
        assignments = [
            {"staff_id": "S1", "date": f"2023-10-0{i}", "shift": "Morning"} for i in range(1, 8)
        ]
        shift_definitions = [{"Name": "Morning", "Duration": 8}]
        result = AuditDataProcessor.process(assignments, shift_definitions)

        # Verify only first 5 are shown
        assert "2023-10-01: Morning (8h)" in result
        assert "2023-10-05: Morning (8h)" in result
        assert "2023-10-06: Morning (8h)" not in result
        assert result.endswith("...")
