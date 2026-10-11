"""
tests/test_attendance_tools.py - Comprehensive Unit and Integration Tests.

Validates:
- Correct attendance percentage calculations
- Marking a student Present and Absent
- Updating totals and persistence
- Removing attendance records (unmarked day handling)
- Handling unknown students, invalid days, and invalid statuses
- Class average attendance and overall attendance rate calculations
- Handling invalid AI-generated action requests
- Ensuring failed operations do not corrupt JSON files
- All tests use temporary files to never modify real data
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import attendance_tools
from ai_agent import AIAgent


class TestAttendanceTools(unittest.TestCase):
    def setUp(self):
        """Create an isolated temporary environment for each test."""
        self.test_dir = tempfile.mkdtemp()
        self.test_file = Path(self.test_dir) / "test_students.json"

        # Known fixture data with 5 students
        self.fixture_data = {
            "students": [
                {
                    "name": "Rahul",
                    "roll_no": "101",
                    "attendance": {
                        "Day 1": "Present",
                        "Day 2": "Absent",
                        "Day 3": "Present",
                        "Day 4": "Present",
                        "Day 5": "Absent",
                    },
                    "total_days": 5,
                    "days_present": 3,
                },
                {
                    "name": "Priya",
                    "roll_no": "102",
                    "attendance": {
                        "Day 1": "Present",
                        "Day 2": "Present",
                        "Day 3": "Present",
                        "Day 4": "Present",
                        "Day 5": "Present",
                    },
                    "total_days": 5,
                    "days_present": 5,
                },
                {
                    "name": "Amit",
                    "roll_no": "103",
                    "attendance": {
                        "Day 1": "Present",
                        "Day 2": "Absent",
                        "Day 3": "Absent",
                        "Day 4": "Present",
                        "Day 5": "Absent",
                    },
                    "total_days": 5,
                    "days_present": 2,
                },
                {
                    "name": "Sneha",
                    "roll_no": "104",
                    "attendance": {
                        "Day 1": "Present",
                        "Day 2": "Present",
                        "Day 3": "Present",
                        "Day 4": "Present",
                        "Day 5": "Absent",
                    },
                    "total_days": 5,
                    "days_present": 4,
                },
                {
                    "name": "Rohan",
                    "roll_no": "105",
                    "attendance": {
                        "Day 1": "Absent",
                        "Day 2": "Present",
                        "Day 3": "Present",
                        "Day 4": "Absent",
                        "Day 5": "Present",
                    },
                    "total_days": 5,
                    "days_present": 3,
                },
            ]
        }
        with open(self.test_file, "w", encoding="utf-8") as f:
            json.dump(self.fixture_data, f, indent=2)

        self.agent = AIAgent(data_path=self.test_file)

    def tearDown(self):
        """Clean up temporary test directory."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_calculate_attendance_percentage(self):
        """Test calculation of student attendance percentage."""
        # Rahul: 3 / 5 = 60.0%
        result = attendance_tools.calculate_attendance_percentage("Rahul", data_path=self.test_file)
        self.assertTrue(result["success"])
        self.assertEqual(result["attendance_percentage"], 60.0)
        self.assertEqual(result["days_present"], 3)
        self.assertEqual(result["total_days"], 5)

        # Priya: 5 / 5 = 100.0%
        result_priya = attendance_tools.calculate_attendance_percentage("102", data_path=self.test_file)
        self.assertTrue(result_priya["success"])
        self.assertEqual(result_priya["attendance_percentage"], 100.0)

    def test_zero_working_days(self):
        """Test handling of student with 0 recorded working days."""
        # Add a student with empty attendance
        with open(self.test_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["students"].append({
            "name": "NewStudent",
            "roll_no": "106",
            "attendance": {},
            "total_days": 0,
            "days_present": 0
        })
        with open(self.test_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

        res = attendance_tools.calculate_attendance_percentage("NewStudent", data_path=self.test_file)
        self.assertTrue(res["success"])
        self.assertEqual(res["total_days"], 0)
        self.assertEqual(res["attendance_percentage"], 0.0)

    def test_mark_attendance_present(self):
        """Test marking a student as Present and updating totals."""
        # Amit was Absent on Day 2 (originally 2/5 -> 40%)
        # Mark Day 2 as Present
        res = attendance_tools.mark_attendance("Amit", "Day 2", "Present", data_path=self.test_file)
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "Present")
        self.assertEqual(res["days_present"], 3)
        self.assertEqual(res["total_days"], 5)
        self.assertEqual(res["attendance_percentage"], 60.0)

        # Verify persistence in JSON
        with open(self.test_file, "r", encoding="utf-8") as f:
            saved = json.load(f)
        amit = next(s for s in saved["students"] if s["name"] == "Amit")
        self.assertEqual(amit["attendance"]["Day 2"], "Present")
        self.assertEqual(amit["days_present"], 3)

    def test_mark_attendance_absent(self):
        """Test marking a student as Absent."""
        # Priya was Present on Day 1. Mark Absent.
        res = attendance_tools.mark_attendance("Priya", "Day 1", "Absent", data_path=self.test_file)
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "Absent")
        self.assertEqual(res["days_present"], 4)
        self.assertEqual(res["total_days"], 5)
        self.assertEqual(res["attendance_percentage"], 80.0)

    def test_mark_attendance_new_day(self):
        """Test adding attendance for a new day (e.g. Day 6)."""
        res = attendance_tools.mark_attendance("Rahul", "Day 6", "Present", data_path=self.test_file)
        self.assertTrue(res["success"])
        self.assertEqual(res["total_days"], 6)
        self.assertEqual(res["days_present"], 4)
        self.assertAlmostEqual(res["attendance_percentage"], 66.67, places=2)

    def test_remove_attendance(self):
        """Test removing an attendance entry and unmarking the day."""
        # Rahul originally has 5 days (Day 4 was Present).
        res = attendance_tools.remove_attendance("Rahul", "Day 4", data_path=self.test_file)
        self.assertTrue(res["success"])
        self.assertEqual(res["removed_day"], "Day 4")
        self.assertEqual(res["removed_status"], "Present")
        self.assertEqual(res["total_days"], 4)
        self.assertEqual(res["days_present"], 2)
        self.assertEqual(res["attendance_percentage"], 50.0)

        # Check persistence
        with open(self.test_file, "r", encoding="utf-8") as f:
            saved = json.load(f)
        rahul = next(s for s in saved["students"] if s["name"] == "Rahul")
        self.assertNotIn("Day 4", rahul["attendance"])
        self.assertEqual(rahul["total_days"], 4)

    def test_remove_nonexistent_day(self):
        """Test removing a day that is not recorded."""
        res = attendance_tools.remove_attendance("Rahul", "Day 99", data_path=self.test_file)
        self.assertFalse(res["success"])
        self.assertEqual(res["error"], "DAY_NOT_FOUND")

    def test_unknown_student(self):
        """Test querying or updating a non-existent student."""
        res = attendance_tools.get_student_attendance("UnknownStudent", data_path=self.test_file)
        self.assertFalse(res["success"])
        self.assertEqual(res["error"], "STUDENT_NOT_FOUND")

        res_mark = attendance_tools.mark_attendance("999", "Day 1", "Present", data_path=self.test_file)
        self.assertFalse(res_mark["success"])
        self.assertEqual(res_mark["error"], "STUDENT_NOT_FOUND")

    def test_invalid_day_and_status(self):
        """Test validation on invalid day or status inputs."""
        res_day = attendance_tools.mark_attendance("Rahul", "InvalidDay!", "Present", data_path=self.test_file)
        self.assertFalse(res_day["success"])
        self.assertEqual(res_day["error"], "INVALID_DAY")

        res_status = attendance_tools.mark_attendance("Rahul", "Day 1", "Maybe", data_path=self.test_file)
        self.assertFalse(res_status["success"])
        self.assertEqual(res_status["error"], "INVALID_STATUS")

    def test_get_all_students(self):
        """Test retrieving all student records and percentages."""
        res = attendance_tools.get_all_students(data_path=self.test_file)
        self.assertTrue(res["success"])
        self.assertEqual(res["count"], 5)
        self.assertEqual(len(res["students"]), 5)
        # Check first student has percentage
        self.assertIn("attendance_percentage", res["students"][0])

    def test_calculate_class_average_and_overall_rate(self):
        """Test arithmetic mean and overall attendance rate."""
        # Rahul: 60%, Priya: 100%, Amit: 40%, Sneha: 80%, Rohan: 60%
        # Sum = 340%, Mean = 340 / 5 = 68.0%
        # Total present = 3+5+2+4+3 = 17. Total days = 25.
        # Overall rate = 17 / 25 * 100 = 68.0%
        res = attendance_tools.calculate_class_average_attendance(data_path=self.test_file)
        self.assertTrue(res["success"])
        self.assertEqual(res["class_average"], 68.0)
        self.assertEqual(res["overall_attendance_rate"], 68.0)
        self.assertEqual(res["students_included"], 5)
        self.assertEqual(res["total_days_present"], 17)
        self.assertEqual(res["total_recorded_days"], 25)

    def test_get_low_attendance_students(self):
        """Test finding students below a threshold."""
        # Default 75% -> Rahul (60%), Amit (40%), Rohan (60%)
        res = attendance_tools.get_low_attendance_students(threshold=75, data_path=self.test_file)
        self.assertTrue(res["success"])
        self.assertEqual(res["count"], 3)
        low_names = [s["name"] for s in res["students"]]
        self.assertIn("Rahul", low_names)
        self.assertIn("Amit", low_names)
        self.assertIn("Rohan", low_names)
        self.assertNotIn("Priya", low_names)
        self.assertNotIn("Sneha", low_names)

        # Custom threshold 50% -> Only Amit (40%)
        res_50 = attendance_tools.get_low_attendance_students(threshold=50, data_path=self.test_file)
        self.assertTrue(res_50["success"])
        self.assertEqual(res_50["count"], 1)
        self.assertEqual(res_50["students"][0]["name"], "Amit")

    def test_ai_agent_invalid_action(self):
        """Test AI agent handling unapproved actions."""
        payload = {"action": "delete_all_database", "arguments": {}}
        res = self.agent.validate_and_execute_action(payload)
        self.assertFalse(res["success"])
        self.assertEqual(res["error"], "UNAPPROVED_ACTION")

    def test_ai_agent_malformed_arguments(self):
        """Test AI agent handling missing required action arguments."""
        payload = {"action": "mark_attendance", "arguments": {"student_identifier": "Rahul"}}
        res = self.agent.validate_and_execute_action(payload)
        self.assertFalse(res["success"])
        self.assertEqual(res["error"], "MISSING_ARGUMENT")

    def test_failed_operation_does_not_corrupt_file(self):
        """Confirm that a failed operation does not alter or corrupt the JSON file."""
        with open(self.test_file, "r", encoding="utf-8") as f:
            original_content = f.read()

        # Attempt invalid mark
        res = attendance_tools.mark_attendance("NonExistent", "Day 1", "Present", data_path=self.test_file)
        self.assertFalse(res["success"])

        with open(self.test_file, "r", encoding="utf-8") as f:
            current_content = f.read()

        self.assertEqual(original_content, current_content)

    def test_ai_agent_end_to_end_queries(self):
        """Test AI agent processing the key natural language queries."""
        # 1. Percentage
        q1 = self.agent.process_query("Calculate the attendance percentage of Rahul.")
        self.assertTrue(q1["success"])
        self.assertEqual(q1["action_requested"], "calculate_attendance_percentage")

        # 2. Mark present
        q2 = self.agent.process_query("Mark Rahul present on Day 3.")
        self.assertTrue(q2["success"])
        self.assertEqual(q2["action_requested"], "mark_attendance")

        # 3. Mark by roll number
        q3 = self.agent.process_query("Mark roll number 102 absent on Day 2.")
        self.assertTrue(q3["success"])
        self.assertEqual(q3["action_requested"], "mark_attendance")

        # 4. Remove
        q4 = self.agent.process_query("Remove Rahul's attendance for Day 4.")
        self.assertTrue(q4["success"])
        self.assertEqual(q4["action_requested"], "remove_attendance")

        # 5. All students
        q5 = self.agent.process_query("Show the attendance percentage of all students.")
        self.assertTrue(q5["success"])
        self.assertEqual(q5["action_requested"], "get_all_students")

        # 6. Class average
        q6 = self.agent.process_query("Calculate the class average attendance.")
        self.assertTrue(q6["success"])
        self.assertEqual(q6["action_requested"], "calculate_class_average_attendance")

        # 7. Low attendance
        q7 = self.agent.process_query("Show students whose attendance is below 75%.")
        self.assertTrue(q7["success"])
        self.assertEqual(q7["action_requested"], "get_low_attendance_students")


if __name__ == "__main__":
    unittest.main()
