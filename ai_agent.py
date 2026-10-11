"""
ai_agent.py - AI Agent Integration with Hugging Face Inference API.

Interprets natural language queries, selects approved attendance tools via
structured JSON action requests, validates parameters, and coordinates
execution without executing arbitrary code.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple, Union

from dotenv import load_dotenv

import attendance_tools

# Load environment variables from .env file
load_dotenv()

DEFAULT_HF_MODEL = os.getenv("HF_MODEL_ID", "Qwen/Qwen2.5-72B-Instruct")

SYSTEM_PROMPT = """You are an intelligent, precise AI Assistant for an Attendance Management System.
Your job is to interpret the user's natural language request and select the single appropriate attendance tool.

You DO NOT calculate numbers yourself, and you NEVER directly modify data files.
You MUST respond ONLY with a strict JSON object specifying the action and arguments.

Available Tools:
1. "get_student_attendance":
   Description: Retrieve complete attendance records for a specific student.
   Arguments: {"student_identifier": "<name or roll number>"}

2. "calculate_attendance_percentage":
   Description: Calculate the attendance percentage for a specific student.
   Arguments: {"student_identifier": "<name or roll number>"}

3. "mark_attendance":
   Description: Mark or update a student's attendance as Present or Absent for a specific day.
   Arguments: {
     "student_identifier": "<name or roll number>",
     "day": "<e.g. 'Day 1', 'Day 2', 'Day 3'>",
     "status": "<'Present' or 'Absent'>"
   }

4. "remove_attendance":
   Description: Remove an attendance record for a student on a specific day.
   Arguments: {
     "student_identifier": "<name or roll number>",
     "day": "<e.g. 'Day 1', 'Day 2'>"
   }

5. "get_all_students":
   Description: Get attendance records and percentages for all students in the class.
   Arguments: {}

6. "calculate_class_average_attendance":
   Description: Calculate the class average attendance percentage and overall attendance rate.
   Arguments: {}

7. "get_low_attendance_students":
   Description: List students whose attendance percentage is below a certain threshold (default 75).
   Arguments: {"threshold": <numeric threshold, e.g. 75>}

JSON Schema:
{
  "action": "<action_name>",
  "arguments": { ... }
}

Important Rules:
- Return ONLY the JSON object. Do not add markdown explanation before or after.
- If the user query is unrelated to attendance, return: {"action": "unsupported", "arguments": {"message": "Request outside attendance domain."}}
- Days must be formatted as "Day X" (e.g., "Day 3").
- Status must be "Present" or "Absent".
"""

# Map of allowed actions to their Python implementation
APPROVED_ACTIONS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "get_student_attendance": attendance_tools.get_student_attendance,
    "calculate_attendance_percentage": attendance_tools.calculate_attendance_percentage,
    "mark_attendance": attendance_tools.mark_attendance,
    "remove_attendance": attendance_tools.remove_attendance,
    "get_all_students": attendance_tools.get_all_students,
    "calculate_class_average_attendance": attendance_tools.calculate_class_average_attendance,
    "get_low_attendance_students": attendance_tools.get_low_attendance_students,
}


class AIAgent:
    """
    Coordinates AI query processing, tool execution, and response synthesis.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        model_id: Optional[str] = None,
        data_path: Optional[Union[str, Path]] = None,
    ) -> None:
        self.token = token or os.getenv("HF_TOKEN")
        self.model_id = model_id or DEFAULT_HF_MODEL
        self.data_path = data_path
        self._hf_client = None

    def _get_hf_client(self):
        """Lazy-initialize the Hugging Face InferenceClient."""
        if not self.token:
            return None

        if self._hf_client is None:
            try:
                from huggingface_hub import InferenceClient
                self._hf_client = InferenceClient(
                    model=self.model_id,
                    token=self.token,
                )
            except Exception as exc:
                print(f"[Warning] Failed to initialize Hugging Face client: {exc}")
                self._hf_client = None
        return self._hf_client

    def has_active_token(self) -> bool:
        """Check if an active Hugging Face token is configured."""
        return bool(self.token and self.token.strip() and not self.token.startswith("your_hf_token_here"))

    def extract_json(self, raw_text: str) -> Optional[Dict[str, Any]]:
        """
        Extract and parse a JSON object from raw LLM text output.
        Handles markdown code blocks and raw JSON text.
        """
        if not raw_text or not raw_text.strip():
            return None

        text = raw_text.strip()

        # Check for ```json ... ``` code blocks
        json_block_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
        if json_block_match:
            try:
                return json.loads(json_block_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Search for first outer { ... }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass

        return None

    def call_huggingface_model(self, user_query: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Call Hugging Face Inference API with system prompt and user query.
        Returns:
            (raw_response_text, error_message)
        """
        client = self._get_hf_client()
        if client is None:
            return None, "HF_TOKEN not configured or client initialization failed."

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_query},
        ]

        try:
            # Using chat_completion API
            response = client.chat_completion(
                messages=messages,
                max_tokens=300,
                temperature=0.1,
            )
            content = response.choices[0].message.content
            return content, None
        except Exception as exc:
            return None, f"Hugging Face API call failed: {exc}"

    def rule_based_intent_parser(self, query: str) -> Optional[Dict[str, Any]]:
        """
        A reliable, deterministic rule-based intent parser used as a seamless
        fallback when HF_TOKEN is not set or network is unavailable.
        """
        q = query.strip()
        q_lower = q.lower()

        # Class average
        if "average" in q_lower:
            return {"action": "calculate_class_average_attendance", "arguments": {}}

        # Low attendance / below threshold
        low_match = re.search(r"(?:below|less than|<)\s*(\d+)", q_lower)
        if "below" in q_lower or "low" in q_lower or "defaulter" in q_lower or low_match:
            threshold = float(low_match.group(1)) if low_match else 75.0
            return {"action": "get_low_attendance_students", "arguments": {"threshold": threshold}}

        # All students
        if "all student" in q_lower or "all the student" in q_lower or "everyone" in q_lower or "whole class" in q_lower:
            return {"action": "get_all_students", "arguments": {}}

        # Extract day: e.g. "Day 3", "day 2"
        day_match = re.search(r"\bday\s*(\d+)\b", q_lower)
        day_arg = f"Day {day_match.group(1)}" if day_match else None

        # Extract student identifier (name or roll number)
        # Check for roll number pattern: "roll no 101", "roll number 102", "roll 103"
        roll_match = re.search(r"\broll(?:\s*(?:no|number))?\s*[:=]?\s*(\d+)\b", q_lower)
        student_id: Optional[str] = None
        if roll_match:
            student_id = roll_match.group(1)

        # Check for status
        status: Optional[str] = None
        if "present" in q_lower:
            status = "Present"
        elif "absent" in q_lower:
            status = "Absent"

        # Action: Remove attendance
        if "remove" in q_lower or "delete" in q_lower or "clear" in q_lower:
            if not student_id:
                # Find name words
                words = [w for w in re.findall(r"\b[A-Za-z]+\b", q) if w.lower() not in {"remove", "attendance", "for", "on", "day", "the", "student", "record"}]
                if words:
                    student_id = words[0]
            if student_id and day_arg:
                return {
                    "action": "remove_attendance",
                    "arguments": {"student_identifier": student_id, "day": day_arg},
                }

        # Action: Mark attendance
        if ("mark" in q_lower or "set" in q_lower or "update" in q_lower) and status:
            if not student_id:
                # Find student name from words
                words = [w for w in re.findall(r"\b[A-Za-z]+\b", q) if w.lower() not in {"mark", "as", "present", "absent", "on", "for", "day", "student", "roll", "number"}]
                if words:
                    student_id = words[0]
            if student_id and day_arg:
                return {
                    "action": "mark_attendance",
                    "arguments": {
                        "student_identifier": student_id,
                        "day": day_arg,
                        "status": status,
                    },
                }

        # Action: Attendance percentage
        if "percentage" in q_lower or "%" in q:
            if not student_id:
                words = [w for w in re.findall(r"\b[A-Za-z]+\b", q) if w.lower() not in {"calculate", "what", "is", "the", "attendance", "percentage", "of", "for", "student", "show"}]
                if words:
                    student_id = words[0]
            if student_id:
                return {
                    "action": "calculate_attendance_percentage",
                    "arguments": {"student_identifier": student_id},
                }

        # Action: Get student attendance record
        if not student_id:
            words = [w for w in re.findall(r"\b[A-Za-z]+\b", q) if w.lower() not in {"get", "show", "view", "attendance", "of", "for", "record", "records", "the", "details"}]
            if words:
                student_id = words[0]
        if student_id:
            return {
                "action": "get_student_attendance",
                "arguments": {"student_identifier": student_id},
            }

        return None

    def validate_and_execute_action(self, action_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Strictly validate action payload and dispatch to the approved Python function.
        Never executes arbitrary code or unapproved tools.
        """
        if not isinstance(action_payload, dict):
            return {
                "success": False,
                "error": "MALFORMED_PAYLOAD",
                "message": "Action payload must be a JSON dictionary.",
            }

        action_name = action_payload.get("action")
        raw_args = action_payload.get("arguments", {})

        if not isinstance(raw_args, dict):
            return {
                "success": False,
                "error": "INVALID_ARGUMENTS",
                "message": "Action 'arguments' must be a JSON dictionary.",
            }

        if action_name not in APPROVED_ACTIONS:
            return {
                "success": False,
                "error": "UNAPPROVED_ACTION",
                "message": f"Action '{action_name}' is not in the list of approved attendance tools.",
            }

        tool_fn = APPROVED_ACTIONS[action_name]

        try:
            # Dispatch based on tool signature
            if action_name in {"get_student_attendance", "calculate_attendance_percentage"}:
                student_id = raw_args.get("student_identifier")
                if not student_id:
                    return {
                        "success": False,
                        "error": "MISSING_ARGUMENT",
                        "message": f"Action '{action_name}' requires 'student_identifier'.",
                    }
                return tool_fn(student_identifier=student_id, data_path=self.data_path)

            elif action_name == "mark_attendance":
                student_id = raw_args.get("student_identifier")
                day = raw_args.get("day")
                status = raw_args.get("status")
                if not student_id or not day or not status:
                    return {
                        "success": False,
                        "error": "MISSING_ARGUMENT",
                        "message": "Action 'mark_attendance' requires 'student_identifier', 'day', and 'status'.",
                    }
                return tool_fn(
                    student_identifier=student_id,
                    day=day,
                    status=status,
                    data_path=self.data_path,
                )

            elif action_name == "remove_attendance":
                student_id = raw_args.get("student_identifier")
                day = raw_args.get("day")
                if not student_id or not day:
                    return {
                        "success": False,
                        "error": "MISSING_ARGUMENT",
                        "message": "Action 'remove_attendance' requires 'student_identifier' and 'day'.",
                    }
                return tool_fn(
                    student_identifier=student_id,
                    day=day,
                    data_path=self.data_path,
                )

            elif action_name == "get_all_students":
                return tool_fn(data_path=self.data_path)

            elif action_name == "calculate_class_average_attendance":
                return tool_fn(data_path=self.data_path)

            elif action_name == "get_low_attendance_students":
                threshold = raw_args.get("threshold", 75.0)
                return tool_fn(threshold=threshold, data_path=self.data_path)

            else:
                return {
                    "success": False,
                    "error": "UNHANDLED_ACTION",
                    "message": f"No handler mapped for action '{action_name}'.",
                }

        except Exception as exc:
            return {
                "success": False,
                "error": "TOOL_EXECUTION_ERROR",
                "message": f"Error during tool execution: {exc}",
            }

    def format_human_response(self, tool_result: Dict[str, Any]) -> str:
        """
        Format tool output into a clean, professional, beginner-friendly human-readable message.
        """
        if not tool_result.get("success", False):
            err_type = tool_result.get("error", "ERROR")
            err_msg = tool_result.get("message", "An unknown error occurred.")
            return f"❌ **Error [{err_type}]**: {err_msg}"

        action = tool_result.get("action")

        if action == "mark_attendance":
            student = tool_result.get("student")
            roll_no = tool_result.get("roll_no")
            day = tool_result.get("day")
            status = tool_result.get("status")
            present = tool_result.get("days_present")
            total = tool_result.get("total_days")
            pct = tool_result.get("attendance_percentage")
            return (
                f"✅ **{student}'s attendance has been updated for {day}.**\n\n"
                f"- **Roll number**: {roll_no}\n"
                f"- **Status**: {status}\n"
                f"- **Days present**: {present}\n"
                f"- **Recorded attendance days**: {total}\n"
                f"- **Attendance percentage**: {pct}%"
            )

        elif action == "remove_attendance":
            student = tool_result.get("student")
            roll_no = tool_result.get("roll_no")
            day = tool_result.get("removed_day")
            was_status = tool_result.get("removed_status")
            present = tool_result.get("days_present")
            total = tool_result.get("total_days")
            pct = tool_result.get("attendance_percentage")
            return (
                f"🗑️ **Attendance for {student} on {day} has been removed.**\n\n"
                f"- **Roll number**: {roll_no}\n"
                f"- **Previous Status**: {was_status}\n"
                f"- **Days present**: {present}\n"
                f"- **Recorded attendance days**: {total}\n"
                f"- **New attendance percentage**: {pct}%\n"
                f"*(Note: The day is now unmarked and does not count as absent.)*"
            )

        elif action == "calculate_attendance_percentage":
            student = tool_result.get("student")
            roll_no = tool_result.get("roll_no")
            present = tool_result.get("days_present")
            total = tool_result.get("total_days")
            pct = tool_result.get("attendance_percentage")
            return (
                f"📊 **Attendance Percentage for {student} (Roll: {roll_no})**:\n\n"
                f"- **Days present**: {present}\n"
                f"- **Total working days recorded**: {total}\n"
                f"- **Attendance percentage**: **{pct}%**"
            )

        elif action == "get_student_attendance":
            student = tool_result.get("student")
            roll_no = tool_result.get("roll_no")
            present = tool_result.get("days_present")
            total = tool_result.get("total_days")
            pct = tool_result.get("attendance_percentage")
            attendance = tool_result.get("attendance", {})
            days_str = "\n".join([f"  • {d}: {s}" for d, s in attendance.items()]) if attendance else "  • No days recorded."
            return (
                f"📋 **Attendance Record: {student} (Roll: {roll_no})**\n\n"
                f"**Daily Breakdown:**\n{days_str}\n\n"
                f"- **Days present**: {present}/{total}\n"
                f"- **Attendance percentage**: **{pct}%**"
            )

        elif action == "get_all_students":
            students = tool_result.get("students", [])
            lines = []
            for s in students:
                lines.append(
                    f"- **{s['name']}** (Roll: {s['roll_no']}): {s['attendance_percentage']}% "
                    f"({s['days_present']}/{s['total_days']} days present)"
                )
            summary = "\n".join(lines)
            return f"👥 **Class Attendance Summary ({len(students)} Students)**:\n\n{summary}"

        elif action == "calculate_class_average_attendance":
            class_avg = tool_result.get("class_average")
            overall_rate = tool_result.get("overall_attendance_rate")
            students_count = tool_result.get("students_included")
            total_students = tool_result.get("total_students")
            present_all = tool_result.get("total_days_present")
            recorded_all = tool_result.get("total_recorded_days")
            return (
                f"📈 **Class Attendance Statistics**:\n\n"
                f"- **Class Average Attendance (Mean of student percentages)**: **{class_avg}%**\n"
                f"  *(Calculated across {students_count} of {total_students} students with recorded attendance)*\n\n"
                f"- **Overall Class Attendance Rate**: **{overall_rate}%**\n"
                f"  *(Total student-days present: {present_all} out of {recorded_all} recorded)*"
            )

        elif action == "get_low_attendance_students":
            threshold = tool_result.get("threshold")
            students = tool_result.get("students", [])
            if not students:
                return f"🌟 **Great news!** No students have attendance below {threshold}%."
            lines = []
            for s in students:
                lines.append(
                    f"- **{s['name']}** (Roll: {s['roll_no']}): **{s['attendance_percentage']}%** "
                    f"({s['days_present']}/{s['total_days']} days present)"
                )
            summary = "\n".join(lines)
            return (
                f"⚠️ **Students with Attendance Below {threshold}% ({len(students)} found)**:\n\n"
                f"{summary}"
            )

        return tool_result.get("message", "Operation completed.")

    def process_query(self, user_query: str) -> Dict[str, Any]:
        """
        End-to-end processing pipeline:
        1. Receive natural language query.
        2. Attempt Hugging Face Inference API call if token configured.
        3. If no token or HF call fails, fall back to rule-based parser.
        4. Validate parsed action and arguments.
        5. Execute approved Python attendance tool.
        6. Generate both structured JSON and human-readable explanation.
        """
        source = "huggingface"
        action_payload: Optional[Dict[str, Any]] = None
        hf_error: Optional[str] = None

        # Step 1: Hugging Face attempt
        if self.has_active_token():
            raw_hf_output, hf_error = self.call_huggingface_model(user_query)
            if raw_hf_output:
                action_payload = self.extract_json(raw_hf_output)

        # Step 2: Fallback if HF was unavailable or failed
        if not action_payload:
            source = "rule_based_fallback"
            action_payload = self.rule_based_intent_parser(user_query)

        # If still unable to understand
        if not action_payload:
            return {
                "success": False,
                "source": source,
                "hf_error": hf_error,
                "error": "UNRECOGNIZED_INTENT",
                "message": (
                    "Could not determine the intended attendance action from your query. "
                    "Please try queries like: 'Calculate attendance of Rahul', "
                    "'Mark Priya present on Day 3', 'Show class average', or 'Show students below 75%'."
                ),
                "human_response": (
                    "❓ I couldn't understand that attendance request.\n\n"
                    "Examples of requests I understand:\n"
                    "- *'Calculate the attendance percentage of Rahul.'*\n"
                    "- *'Mark Rahul present on Day 3.'*\n"
                    "- *'Mark roll number 102 absent on Day 2.'*\n"
                    "- *'Remove Rahul's attendance for Day 4.'*\n"
                    "- *'Show the attendance percentage of all students.'*\n"
                    "- *'Calculate the class average attendance.'*\n"
                    "- *'Show students whose attendance is below 75%.'*"
                ),
            }

        # Step 3: Validate and execute the selected action
        tool_result = self.validate_and_execute_action(action_payload)

        # Step 4: Format human response
        human_msg = self.format_human_response(tool_result)

        return {
            "success": tool_result.get("success", False),
            "source": source,
            "action_requested": action_payload.get("action"),
            "action_arguments": action_payload.get("arguments"),
            "tool_result": tool_result,
            "human_response": human_msg,
        }
