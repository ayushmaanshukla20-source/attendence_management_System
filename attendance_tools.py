"""
attendance_tools.py - Core Attendance Management Tools.

Provides validated operations for querying, marking, removing, and calculating
student attendance from persistent JSON storage.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Default path to students JSON data file
DEFAULT_DATA_PATH = Path(__file__).parent / "data" / "students.json"

VALID_STATUSES = {"Present", "Absent"}


# ============================================================================
# Helper Functions: Data Loading, Saving, Normalization, & Recalculation
# ============================================================================

def get_data_path(custom_path: Optional[Union[str, Path]] = None) -> Path:
    """Return the resolved Path object for the student records file."""
    if custom_path is not None:
        return Path(custom_path)
    return DEFAULT_DATA_PATH


def load_students_data(data_path: Optional[Union[str, Path]] = None) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """
    Safely load student data from the JSON file.

    Returns:
        (data_dict, error_dict)
        If loading succeeds, error_dict is None.
        If loading fails, data_dict is empty and error_dict has details.
    """
    target_path = get_data_path(data_path)
    if not target_path.exists():
        return {}, {
            "success": False,
            "error": "FILE_NOT_FOUND",
            "message": f"Data file does not exist at {target_path}."
        }

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        return {}, {
            "success": False,
            "error": "CORRUPT_DATA_FILE",
            "message": f"Failed to parse JSON file {target_path}: {exc}"
        }
    except Exception as exc:
        return {}, {
            "success": False,
            "error": "FILE_READ_ERROR",
            "message": f"Error reading data file: {exc}"
        }

    if "students" not in data or not isinstance(data["students"], list):
        return {}, {
            "success": False,
            "error": "INVALID_DATA_SCHEMA",
            "message": "Data file missing 'students' list."
        }

    return data, None


def save_students_data(data: Dict[str, Any], data_path: Optional[Union[str, Path]] = None) -> Optional[Dict[str, Any]]:
    """
    Safely write student data to the JSON file using atomic file replacement.

    Returns:
        None on success, or an error dictionary on failure.
    """
    target_path = get_data_path(data_path)
    target_dir = target_path.parent
    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Atomic write via temporary file in the same directory
        with tempfile.NamedTemporaryFile("w", dir=target_dir, delete=False, encoding="utf-8") as tf:
            json.dump(data, tf, indent=2)
            temp_name = tf.name
        os.replace(temp_name, target_path)
        return None
    except Exception as exc:
        if 'temp_name' in locals() and os.path.exists(temp_name):
            try:
                os.remove(temp_name)
            except OSError:
                pass
        return {
            "success": False,
            "error": "FILE_WRITE_ERROR",
            "message": f"Failed to save student data: {exc}"
        }


def recalculate_student_totals(student: Dict[str, Any]) -> None:
    """
    Recalculate total_days and days_present from the raw attendance dict.
    The attendance dictionary is the single source of truth.
    """
    attendance = student.get("attendance", {})
    if not isinstance(attendance, dict):
        student["attendance"] = {}
        attendance = student["attendance"]

    total_days = len(attendance)
    days_present = sum(1 for status in attendance.values() if str(status).strip().capitalize() == "Present")

    student["total_days"] = total_days
    student["days_present"] = days_present


def normalize_day(day_input: Union[str, int]) -> Optional[str]:
    """
    Normalize various representations of day:
    e.g. 'Day 3', 'day 3', 'Day3', 'day3', 3, '3' -> 'Day 3'.
    """
    if day_input is None:
        return None

    day_str = str(day_input).strip()
    # Match patterns like "Day 3", "day 3", "Day3", "day3"
    match = re.match(r"^(?:day\s*)?(\d+)$", day_str, re.IGNORECASE)
    if match:
        return f"Day {match.group(1)}"

    # If it's already "Day <something>" with non-numeric, preserve title case
    if day_str.lower().startswith("day"):
        parts = day_str.split(maxsplit=1)
        if len(parts) == 2:
            return f"Day {parts[1]}"
    return None


def normalize_status(status_input: str) -> Optional[str]:
    """
    Validate and normalize attendance status.
    Accepts only 'Present' or 'Absent' (case-insensitive, or shorthand 'P'/'A').
    """
    if not status_input:
        return None

    cleaned = str(status_input).strip().capitalize()
    if cleaned in VALID_STATUSES:
        return cleaned
    if cleaned == "P":
        return "Present"
    if cleaned == "A":
        return "Absent"
    return None


def find_student(students: List[Dict[str, Any]], student_identifier: Union[str, int]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Locate a student by either name or roll number (case-insensitive string or int).

    Returns:
        (student_dict, error_dict)
    """
    if student_identifier is None:
        return None, {
            "success": False,
            "error": "MISSING_IDENTIFIER",
            "message": "Student identifier cannot be empty."
        }

    ident_str = str(student_identifier).strip().lower()
    if not ident_str:
        return None, {
            "success": False,
            "error": "MISSING_IDENTIFIER",
            "message": "Student identifier cannot be empty."
        }

    matches: List[Dict[str, Any]] = []

    for s in students:
        s_name = str(s.get("name", "")).strip().lower()
        s_roll = str(s.get("roll_no", "")).strip().lower()

        # Exact roll match or exact name match
        if ident_str == s_roll or ident_str == s_name:
            matches.append(s)

    # If no exact match, allow matching first name if unambiguous
    if not matches:
        for s in students:
            s_name = str(s.get("name", "")).strip().lower()
            if s_name.startswith(ident_str) or ident_str in s_name.split():
                matches.append(s)

    if not matches:
        return None, {
            "success": False,
            "error": "STUDENT_NOT_FOUND",
            "message": f"No student found with the identifier '{student_identifier}'."
        }

    if len(matches) > 1:
        match_names = [f"{s.get('name')} (Roll {s.get('roll_no')})" for s in matches]
        return None, {
            "success": False,
            "error": "AMBIGUOUS_IDENTIFIER",
            "message": f"Multiple students matched '{student_identifier}': {', '.join(match_names)}. Please specify roll number."
        }

    return matches[0], None


# ============================================================================
# Core Tools
# ============================================================================

def get_student_attendance(student_identifier: Union[str, int], data_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """
    Tool 1: Get Student Attendance.
    Find a student by name or roll number and return their complete attendance record,
    total days, days present, and attendance percentage.
    """
    data, err = load_students_data(data_path)
    if err:
        return err

    student, err = find_student(data["students"], student_identifier)
    if err:
        return err

    recalculate_student_totals(student)
    total = student["total_days"]
    present = student["days_present"]
    pct = round((present / total * 100), 2) if total > 0 else 0.0

    return {
        "success": True,
        "action": "get_student_attendance",
        "student": student.get("name"),
        "roll_no": str(student.get("roll_no")),
        "attendance": student.get("attendance", {}),
        "total_days": total,
        "days_present": present,
        "attendance_percentage": pct,
        "message": f"Retrieved attendance for {student.get('name')} (Roll: {student.get('roll_no')})."
    }


def calculate_attendance_percentage(student_identifier: Union[str, int], data_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """
    Tool 2: Calculate Attendance Percentage.
    Calculate attendance percentage using: (days_present / total_days) * 100.
    Handles zero working days safely.
    """
    data, err = load_students_data(data_path)
    if err:
        return err

    student, err = find_student(data["students"], student_identifier)
    if err:
        return err

    recalculate_student_totals(student)
    total = student["total_days"]
    present = student["days_present"]

    if total == 0:
        return {
            "success": True,
            "action": "calculate_attendance_percentage",
            "student": student.get("name"),
            "roll_no": str(student.get("roll_no")),
            "total_days": 0,
            "days_present": 0,
            "attendance_percentage": 0.0,
            "message": f"No working days recorded for {student.get('name')}. Attendance percentage is 0.0%."
        }

    pct = round((present / total * 100), 2)
    return {
        "success": True,
        "action": "calculate_attendance_percentage",
        "student": student.get("name"),
        "roll_no": str(student.get("roll_no")),
        "total_days": total,
        "days_present": present,
        "attendance_percentage": pct,
        "message": f"{student.get('name')}'s attendance is {present}/{total} days ({pct}%)."
    }


def mark_attendance(student_identifier: Union[str, int], day: Union[str, int], status: str, data_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """
    Tool 3: Mark Attendance.
    Mark a student as Present or Absent on a specified day.
    Recalculates totals, updates JSON persistence, and validates inputs.
    """
    normalized_day = normalize_day(day)
    if not normalized_day:
        return {
            "success": False,
            "error": "INVALID_DAY",
            "message": f"Invalid day format '{day}'. Please use formats like 'Day 1', 'Day 2', etc."
        }

    normalized_status = normalize_status(status)
    if not normalized_status:
        return {
            "success": False,
            "error": "INVALID_STATUS",
            "message": f"Invalid attendance status '{status}'. Only 'Present' or 'Absent' are accepted."
        }

    data, err = load_students_data(data_path)
    if err:
        return err

    student, err = find_student(data["students"], student_identifier)
    if err:
        return err

    attendance = student.setdefault("attendance", {})
    existing_status = attendance.get(normalized_day)
    was_updated = existing_status is not None

    attendance[normalized_day] = normalized_status
    recalculate_student_totals(student)

    # Save to file
    save_err = save_students_data(data, data_path)
    if save_err:
        return save_err

    pct = round((student["days_present"] / student["total_days"] * 100), 2) if student["total_days"] > 0 else 0.0

    if was_updated:
        msg = f"Attendance for {student.get('name')} on {normalized_day} updated from '{existing_status}' to '{normalized_status}'."
    else:
        msg = f"Attendance for {student.get('name')} on {normalized_day} marked as '{normalized_status}'."

    return {
        "success": True,
        "action": "mark_attendance",
        "student": student.get("name"),
        "roll_no": str(student.get("roll_no")),
        "day": normalized_day,
        "status": normalized_status,
        "was_updated": was_updated,
        "previous_status": existing_status,
        "days_present": student["days_present"],
        "total_days": student["total_days"],
        "attendance_percentage": pct,
        "message": msg
    }


def remove_attendance(student_identifier: Union[str, int], day: Union[str, int], data_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """
    Tool 4: Remove Attendance.
    Remove the attendance entry for the specified student and day.
    Unmarks the day without counting it as absent. Recalculates totals and saves.
    """
    normalized_day = normalize_day(day)
    if not normalized_day:
        return {
            "success": False,
            "error": "INVALID_DAY",
            "message": f"Invalid day format '{day}'. Please use format like 'Day 1'."
        }

    data, err = load_students_data(data_path)
    if err:
        return err

    student, err = find_student(data["students"], student_identifier)
    if err:
        return err

    attendance = student.get("attendance", {})
    if normalized_day not in attendance:
        return {
            "success": False,
            "error": "DAY_NOT_FOUND",
            "message": f"No attendance record found for {student.get('name')} on {normalized_day}."
        }

    previous_status = attendance.pop(normalized_day)
    recalculate_student_totals(student)

    save_err = save_students_data(data, data_path)
    if save_err:
        return save_err

    pct = round((student["days_present"] / student["total_days"] * 100), 2) if student["total_days"] > 0 else 0.0

    return {
        "success": True,
        "action": "remove_attendance",
        "student": student.get("name"),
        "roll_no": str(student.get("roll_no")),
        "removed_day": normalized_day,
        "removed_status": previous_status,
        "days_present": student["days_present"],
        "total_days": student["total_days"],
        "attendance_percentage": pct,
        "message": f"Removed attendance record for {student.get('name')} on {normalized_day} (was {previous_status})."
    }


def get_all_students(data_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """
    Tool 5: Get All Students.
    Return all student records, including calculated attendance percentages.
    """
    data, err = load_students_data(data_path)
    if err:
        return err

    results: List[Dict[str, Any]] = []
    for s in data["students"]:
        recalculate_student_totals(s)
        total = s["total_days"]
        present = s["days_present"]
        pct = round((present / total * 100), 2) if total > 0 else 0.0
        results.append({
            "name": s.get("name"),
            "roll_no": str(s.get("roll_no")),
            "attendance": s.get("attendance", {}),
            "total_days": total,
            "days_present": present,
            "attendance_percentage": pct
        })

    return {
        "success": True,
        "action": "get_all_students",
        "count": len(results),
        "students": results,
        "message": f"Retrieved records for all {len(results)} students."
    }


def calculate_class_average_attendance(data_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """
    Tool 6: Calculate Class Average Attendance.
    Primary calculation: Arithmetic mean of individual student attendance percentages:
        class_average = sum(student_attendance_percentages) / number_of_students
    Also calculates the overall attendance rate across all recorded student-days:
        overall_attendance_rate = total_days_present_across_students / total_recorded_student_days * 100
    Clearly distinguishes both metrics.
    """
    data, err = load_students_data(data_path)
    if err:
        return err

    percentages: List[float] = []
    total_days_all = 0
    total_present_all = 0

    for s in data["students"]:
        recalculate_student_totals(s)
        total = s["total_days"]
        present = s["days_present"]

        total_days_all += total
        total_present_all += present

        if total > 0:
            pct = (present / total) * 100
            percentages.append(pct)

    if not percentages:
        return {
            "success": True,
            "action": "calculate_class_average_attendance",
            "class_average": 0.0,
            "students_included": 0,
            "total_students": len(data["students"]),
            "overall_attendance_rate": 0.0,
            "total_days_present": 0,
            "total_recorded_days": 0,
            "message": "No attendance records available to calculate class average."
        }

    class_avg = round(sum(percentages) / len(percentages), 2)
    overall_rate = round((total_present_all / total_days_all * 100), 2) if total_days_all > 0 else 0.0

    return {
        "success": True,
        "action": "calculate_class_average_attendance",
        "class_average": class_avg,
        "students_included": len(percentages),
        "total_students": len(data["students"]),
        "overall_attendance_rate": overall_rate,
        "total_days_present": total_present_all,
        "total_recorded_days": total_days_all,
        "message": (
            f"Class average attendance is {class_avg}% (mean across {len(percentages)} students). "
            f"Overall attendance rate across all student-days is {overall_rate}% "
            f"({total_present_all}/{total_days_all} days present)."
        )
    }


def get_low_attendance_students(threshold: Union[float, int] = 75.0, data_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """
    Tool 7: Get Low Attendance Students.
    Return students whose calculated attendance percentage is strictly below the threshold.
    """
    try:
        threshold_val = float(threshold)
    except (ValueError, TypeError):
        return {
            "success": False,
            "error": "INVALID_THRESHOLD",
            "message": f"Threshold '{threshold}' must be a numeric value."
        }

    data, err = load_students_data(data_path)
    if err:
        return err

    low_students: List[Dict[str, Any]] = []

    for s in data["students"]:
        recalculate_student_totals(s)
        total = s["total_days"]
        present = s["days_present"]
        pct = round((present / total * 100), 2) if total > 0 else 0.0

        if pct < threshold_val:
            low_students.append({
                "name": s.get("name"),
                "roll_no": str(s.get("roll_no")),
                "total_days": total,
                "days_present": present,
                "attendance_percentage": pct
            })

    return {
        "success": True,
        "action": "get_low_attendance_students",
        "threshold": threshold_val,
        "count": len(low_students),
        "total_students": len(data["students"]),
        "students": low_students,
        "message": f"Found {len(low_students)} student(s) with attendance below {threshold_val}%."
    }
