<div align="center">

# 🏫 AI-Powered Attendance Management System

**Manage class attendance by simply talking to it.**
A modular Python app where an LLM understands what you ask, and deterministic Python tools do the actual work.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Hugging Face](https://img.shields.io/badge/Hugging%20Face-Inference%20API-FFD21E?logo=huggingface&logoColor=black)
![Storage](https://img.shields.io/badge/Storage-JSON-lightgrey)
![Tests](https://img.shields.io/badge/tests-16%20passing-brightgreen)
![License](https://img.shields.io/badge/license-MIT-blue)

[Overview](#-overview) • [Features](#-features) • [Architecture](#-architecture) • [Quick Start](#-quick-start) • [Usage](#-usage) • [Testing](#-testing) • [Troubleshooting](#-troubleshooting)

</div>

---

## 📖 Table of Contents

1. [Overview](#-overview)
2. [Features](#-features)
3. [Architecture](#-architecture)
4. [Data Storage & Integrity](#-data-storage--integrity)
5. [Project Structure](#-project-structure)
6. [Quick Start](#-quick-start)
7. [Configuring the Hugging Face Token](#-configuring-the-hugging-face-token)
8. [Usage](#-usage)
9. [Example Queries](#-example-queries)
10. [Testing](#-testing)
11. [Troubleshooting](#-troubleshooting)
12. [License](#-license)

---

## 🌟 Overview

This project is a beginner-friendly interface for recording, updating, removing and calculating attendance for a classroom. Teachers and administrators don't need to write code or edit files by hand. They just ask in plain English:

> *"Mark Rahul present on Day 3."*
> *"Show students whose attendance is below 75%."*

The language model **only interprets intent**. Every calculation and every change to the data is done by plain Python functions, so results are exact and repeatable.

---

## ✨ Features

| | Feature | Description |
|---|---|---|
| 🗣️ | **Natural language control** | Ask or command in everyday English. |
| 🧮 | **Exact calculations** | Percentages and totals are computed in Python, never by the LLM. |
| 🛡️ | **Safe by design** | No `eval()` or `exec()`, and a strict whitelist of approved actions. |
| 💾 | **Atomic saves** | Updates to `students.json` use atomic file replacement, so the data file can't be corrupted. |
| 📴 | **Offline fallback** | No API token? A built-in pattern matcher takes over so you can test everything immediately. |
| 🖥️ | **Flexible interface** | Interactive CLI, single-query mode and machine-readable JSON output. |
| 🧪 | **Well tested** | 16 automated tests that run on isolated temp files. |

---

## 🧠 Architecture

### Core principle

> **The AI interprets user intent. Python tools execute calculations and data changes.**

```text
┌───────────────────────┐
│ User Natural Language │  ("Mark Rahul present on Day 3")
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│   Hugging Face LLM    │  (Selects action & extracts arguments)
└───────────┬───────────┘
            │ Strict Action JSON:
            │ {"action": "mark_attendance",
            │  "arguments": {"student_identifier": "Rahul",
            │                "day": "Day 3", "status": "Present"}}
            ▼
┌───────────────────────┐
│   Python AIAgent      │  (Validates action name & input types)
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ attendance_tools.py   │  (Executes: marks day, recalculates
└───────────┬───────────┘   totals, saves JSON)
            │
            ▼
┌───────────────────────┐
│ Response Synthesizer  │  (Human-readable text + structured JSON)
└───────────────────────┘
```

### 🔒 Safety guarantees

1. **No `eval()` or `exec()`**: the model never executes arbitrary Python code.
2. **Strict action whitelist**: only 7 pre-approved Python functions can be invoked.
3. **No LLM math hallucinations**: percentages and totals use standard Python arithmetic only.
4. **Safe persistence**: updates to `students.json` use atomic file replacement to prevent corruption.
5. **Seamless offline fallback**: with no Hugging Face token configured, an internal pattern matcher takes over, so you can test end to end out of the box.

---

## 💾 Data Storage & Integrity

All records live in `data/students.json`.

```json
{
  "students": [
    {
      "name": "Rahul",
      "roll_no": "101",
      "attendance": {
        "Day 1": "Present",
        "Day 2": "Absent",
        "Day 3": "Present",
        "Day 4": "Present",
        "Day 5": "Absent"
      },
      "total_days": 5,
      "days_present": 3
    }
  ]
}
```

### Attendance rules

- **Source of truth**: the `attendance` dictionary.
- **Valid statuses**: only `"Present"` and `"Absent"`.
- **Unmarked days**: a day with no record is *unmarked*, not absent.
- **Automatic recalculation**: whenever attendance is marked or removed, Python recalculates `total_days` and `days_present`, so the file can never become inconsistent.

---

## 📁 Project Structure

```text
attendence_management_System/
├── main.py                      # Interactive REPL & CLI interface
├── ai_agent.py                  # Hugging Face integration, validation & dispatch
├── attendance_tools.py          # 7 core attendance functions & data persistence
├── data/
│   └── students.json            # Student attendance storage
├── tests/
│   └── test_attendance_tools.py # 16 automated tests
├── .env.example                 # Example environment variables
├── .gitignore                   # Protects .env and caches
├── requirements.txt             # Python dependencies
└── README.md                    # You are here
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+** (3.11 or 3.13 recommended)
- **PowerShell** (Windows) or **Bash** (macOS / Linux)
- **VS Code** (optional, recommended)

### 1. Clone the repository

```bash
git clone https://github.com/ayushmaanshukla20-source/attendence_management_System.git
cd attendence_management_System
```

> 💡 **VS Code:** *File → Open Folder…* and select the project folder, then press ``Ctrl + ` `` to open the integrated terminal.

### 2. Create and activate a virtual environment

<details open>
<summary><b>🪟 Windows (PowerShell)</b></summary>

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution, run this once:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
```

</details>

<details>
<summary><b>🐧 macOS / Linux (Bash)</b></summary>

```bash
python3 -m venv .venv
source .venv/bin/activate
```

</details>

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

You can now run the app right away using the offline parser, with no token needed.

---

## 🔑 Configuring the Hugging Face Token

To enable the cloud Large Language Model:

1. Create an account on [Hugging Face](https://huggingface.co/).
2. Go to **Settings → Access Tokens**: <https://huggingface.co/settings/tokens>
3. Click **New token**, choose type **Read**, and copy the token (it starts with `hf_...`).
4. Create your `.env` file from the template:

   ```powershell
   # Windows PowerShell
   Copy-Item .env.example .env
   ```
   ```bash
   # macOS / Linux
   cp .env.example .env
   ```

5. Open `.env` and paste your token:

   ```ini
   HF_TOKEN=hf_YourActualTokenGoesHere
   HF_MODEL_ID=Qwen/Qwen2.5-72B-Instruct
   ```

> ⚠️ **Security tip:** `.env` is listed in `.gitignore`, so your private API key is never committed to GitHub.

---

## 🖥️ Usage

### 1. Interactive CLI (recommended)

```bash
python main.py
```

You'll see the welcome banner:

```text
====================================================================
      🏫  AI-POWERED ATTENDANCE MANAGEMENT SYSTEM  🏫
====================================================================
  [AI Status]  Connected to Hugging Face API (Qwen/Qwen2.5-72B-Instruct)
--------------------------------------------------------------------
  Type any natural language command, or use built-in shortcuts:
    • 'list'  - View all student records
    • 'stats' - View class average & stats
    • 'help'  - View example questions
    • 'json'  - Toggle machine-readable JSON output
    • 'exit'  - Quit the application
====================================================================

>>
```

Type a query and press **Enter**.

### 2. Single-query mode (non-interactive)

```bash
python main.py --query "Calculate the attendance percentage of Rahul."
```

### 3. Machine-readable JSON mode

Ideal for automation and scripting:

```bash
python main.py --query "Show the attendance percentage of all students." --json
```

### ⌨️ Built-in shortcuts

| Command | What it does |
| :--- | :--- |
| `list` | View all student records |
| `stats` | View class average & stats |
| `help` | View example questions |
| `json` | Toggle machine-readable JSON output |
| `exit` | Quit the application |

---

## 💬 Example Queries

| Intent | Example query |
| :--- | :--- |
| **Check percentage** | `Calculate the attendance percentage of Rahul.` |
| **Mark attendance** | `Mark Rahul present on Day 3.` |
| **Mark by roll number** | `Mark roll number 102 absent on Day 2.` |
| **Remove an entry** | `Remove Rahul's attendance for Day 4.` |
| **View all students** | `Show the attendance percentage of all students.` |
| **Class average** | `Calculate the class average attendance.` |
| **Low attendance** | `Show students whose attendance is below 75%.` |

---

## 🧪 Testing

The suite has 16 automated tests covering every functional requirement, edge cases, zero working days, corrupted payloads and data isolation.

```bash
python -m unittest discover tests -v
```

<details>
<summary><b>Expected output</b></summary>

```text
test_ai_agent_end_to_end_queries ... ok
test_ai_agent_invalid_action ... ok
test_ai_agent_malformed_arguments ... ok
test_calculate_attendance_percentage ... ok
test_calculate_class_average_and_overall_rate ... ok
test_failed_operation_does_not_corrupt_file ... ok
test_get_all_students ... ok
test_get_low_attendance_students ... ok
test_invalid_day_and_status ... ok
test_mark_attendance_absent ... ok
test_mark_attendance_new_day ... ok
test_mark_attendance_present ... ok
test_remove_attendance ... ok
test_remove_nonexistent_day ... ok
test_unknown_student ... ok
test_zero_working_days ... ok

----------------------------------------------------------------------
Ran 16 tests in 0.040s

OK
```

</details>

> ✅ **Data safety:** all tests use isolated temporary files (`tempfile.mkdtemp()`), so running them never alters your real `data/students.json`.

---

## 🛠️ Troubleshooting

<details>
<summary><b>❌ <code>Activate.ps1 cannot be loaded because running scripts is disabled</code></b></summary>

PowerShell restricts script execution by default on Windows. Run:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
```

Then run `.\.venv\Scripts\Activate.ps1` again.

</details>

<details>
<summary><b>❌ Hugging Face <code>401 Unauthorized</code> or model loading error</b></summary>

- Check that the token in `.env` is correct and has **Read** permission.
- If a model is busy, change `HF_MODEL_ID` in `.env` to another supported model, such as `mistralai/Mistral-7B-Instruct-v0.3`.
- If the token is empty, the app automatically uses the offline fallback engine.

</details>

<details>
<summary><b>❌ Student not found</b></summary>

Use the student's name (`Rahul`, `Priya`, `Amit`, `Sneha`, `Rohan`) or roll number (`101`, `102`, `103`, `104`, `105`).

</details>

---

## 📄 License

Released under the **MIT License**. Built for educational training and robust AI pair programming.

---

<div align="center">

Made with ❤️ by [@ayushmaanshukla20-source](https://github.com/ayushmaanshukla20-source)

⭐ If you found this useful, consider starring the repo!

</div>
