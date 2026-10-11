"""
main.py - Entry Point for AI-Powered Attendance Management System.

Provides an interactive CLI interface and command-line execution for
natural language queries, student management, and attendance statistics.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from ai_agent import AIAgent
import attendance_tools

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def print_banner(agent: AIAgent) -> None:
    """Display welcome banner and current AI integration status."""
    print("=" * 68)
    print("      🏫  AI-POWERED ATTENDANCE MANAGEMENT SYSTEM  🏫")
    print("=" * 68)

    if agent.has_active_token():
        print(f"  [AI Status]  Connected to Hugging Face API ({agent.model_id})")
    else:
        print("  [AI Status]  Running in Local Fallback Mode (No HF_TOKEN detected)")
        print("               To enable Hugging Face cloud LLM:")
        print("               1. Copy .env.example to .env")
        print("               2. Add your HF_TOKEN in .env")

    print("-" * 68)
    print("  Type any natural language command, or use built-in shortcuts:")
    print("    • 'list'  - View all student records")
    print("    • 'stats' - View class average & stats")
    print("    • 'help'  - View example questions")
    print("    • 'json'  - Toggle machine-readable JSON output")
    print("    • 'exit'  - Quit the application")
    print("=" * 68 + "\n")


def print_help() -> None:
    """Print helpful example queries."""
    print("\n💡 Example queries you can ask:")
    print("  1. 'Calculate the attendance percentage of Rahul.'")
    print("  2. 'Mark Rahul present on Day 3.'")
    print("  3. 'Mark roll number 102 absent on Day 2.'")
    print("  4. 'Remove Rahul\'s attendance for Day 4.'")
    print("  5. 'Show the attendance percentage of all students.'")
    print("  6. 'Calculate the class average attendance.'")
    print("  7. 'Show students whose attendance is below 75%.'\n")


def display_students_table() -> None:
    """Render a clean ASCII table of all students."""
    result = attendance_tools.get_all_students()
    if not result.get("success"):
        print(f"❌ Failed to load students: {result.get('message')}")
        return

    students = result.get("students", [])
    print("\n" + "=" * 70)
    print(f"{'Roll No':<10} {'Name':<18} {'Present':<10} {'Total':<10} {'Percentage':<12}")
    print("-" * 70)
    for s in students:
        print(f"{s['roll_no']:<10} {s['name']:<18} {s['days_present']:<10} {s['total_days']:<10} {s['attendance_percentage']:<6}%")
    print("=" * 70 + "\n")


def handle_user_query(agent: AIAgent, query: str, show_json: bool = False) -> None:
    """Process a user query, format response, and handle output modes."""
    query = query.strip()
    if not query:
        return

    print("\n⏳ Processing request...")
    result = agent.process_query(query)

    print("\n" + result.get("human_response", ""))

    if show_json:
        print("\n--- Structured JSON Output ---")
        print(json.dumps(result.get("tool_result", {}), indent=2))
        print("------------------------------")
    print()


def interactive_loop(agent: AIAgent) -> None:
    """Main interactive REPL loop."""
    print_banner(agent)
    show_json = False

    while True:
        try:
            prompt_indicator = "[JSON ON] >> " if show_json else ">> "
            user_input = input(prompt_indicator).strip()

            if not user_input:
                continue

            cmd_lower = user_input.lower()

            if cmd_lower in {"exit", "quit", "q"}:
                print("\nGoodbye! Have a great day. 👋\n")
                break

            elif cmd_lower in {"help", "h"}:
                print_help()

            elif cmd_lower in {"list", "students"}:
                display_students_table()

            elif cmd_lower in {"stats", "average"}:
                handle_user_query(agent, "Calculate the class average attendance.", show_json)

            elif cmd_lower == "json":
                show_json = not show_json
                status = "ENABLED" if show_json else "DISABLED"
                print(f"\n[Info] Structured JSON display is now {status}.\n")

            else:
                handle_user_query(agent, user_input, show_json)

        except (KeyboardInterrupt, EOFError):
            print("\n\nSession ended. Goodbye! 👋\n")
            break
        except Exception as exc:
            print(f"\n❌ An unexpected error occurred: {exc}\n")


def main() -> None:
    """Parse command line arguments and launch application."""
    parser = argparse.ArgumentParser(
        description="AI-Powered Attendance Management System using Hugging Face & Python Tools"
    )
    parser.add_argument(
        "--query", "-q",
        type=str,
        help="Run a single natural language query non-interactively and exit."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print pure JSON output (ideal for scripting and API integration)."
    )
    parser.add_argument(
        "--model",
        type=str,
        help="Hugging Face model ID to use (overrides HF_MODEL_ID in .env)."
    )
    parser.add_argument(
        "--token",
        type=str,
        help="Hugging Face API token (overrides HF_TOKEN in .env)."
    )

    args = parser.parse_args()

    agent = AIAgent(token=args.token, model_id=args.model)

    if args.query:
        result = agent.process_query(args.query)
        if args.json:
            # Pure machine-readable JSON
            print(json.dumps(result.get("tool_result", {}), indent=2))
        else:
            print(result.get("human_response", ""))
            print(f"\n[Raw Action]: {result.get('action_requested')} (via {result.get('source')})")
    else:
        interactive_loop(agent)


if __name__ == "__main__":
    main()
