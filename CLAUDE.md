# CLAUDE.md — AI Assistant Guide for QUEDIS

## Project Overview

**QUEDIS** (Questions Distributor) is a Python tool for student group heads to manage the fair distribution of presentation topics/questions among students. It tracks how many topics each student has been assigned per subject and always assigns the next topic to the student(s) with the lowest current score.

The project ships two independent interfaces for the same core logic:

| File | Interface | Database |
|------|-----------|----------|
| `GUI_for_quedis.py` | Desktop GUI (Tkinter) | `students_scores.db` (hardcoded, local) |
| `quedis_bot.py` | Telegram Bot (aiogram, async) | `{username}_sc.db` (per-user) |

---

## Repository Structure

```
the_quedis_project/
├── GUI_for_quedis.py   # Desktop application (Tkinter, class-based, sync)
├── quedis_bot.py       # Telegram bot (aiogram, async, global-state FSM)
└── README.md           # Brief project description
```

There are no subdirectories, no build system, no test suite, and no CI/CD configuration.

---

## Technology Stack

- **Language:** Python 3
- **GUI:** `tkinter` (stdlib)
- **Telegram bot:** `aiogram` (async framework)
- **Data manipulation:** `pandas` (reads `.xlsx` student lists)
- **Database:** `sqlite3` (stdlib, embedded, no ORM)
- **Async runtime:** `asyncio` (stdlib)

### Required External Dependencies

```
pandas
openpyxl      # pandas Excel backend
aiogram
```

There is no `requirements.txt`. Install manually:

```bash
pip install pandas openpyxl aiogram
```

---

## Running the Applications

### Desktop GUI

```bash
python GUI_for_quedis.py
```

- Requires `student_excel_table.xlsx` in the same directory (first column must be named `name`).
- Creates/uses `students_scores.db` in the working directory.
- UI language is Russian.

### Telegram Bot

```bash
python quedis_bot.py
```

- **You must set `API_TOKEN`** on line 9 of `quedis_bot.py` before running.
- Requires a `downloads/` directory to exist for Excel file uploads.
- Creates per-user databases named `{telegram_username}_sc.db`.

---

## Core Data Model

Both applications use a single SQLite table named `StudentScores`:

```sql
CREATE TABLE StudentScores (
    name TEXT,          -- "Firstname Lastname" (first two words only)
    <subject_1> INTEGER DEFAULT 0,
    <subject_2> INTEGER DEFAULT 0,
    ...
)
```

- The GUI version pre-creates three fixed columns: `civil_law`, `criminal_law`, `labour_law`.
- The bot version starts with only `name` and allows subjects to be added dynamically via `ALTER TABLE ... ADD COLUMN`.
- **Topic assignment logic:** always selects the `N` students with the lowest score for a given subject (`ORDER BY <subject> ASC LIMIT N`) and increments each by 1.
- **Speaker replacement logic:** decrements the outgoing student's score by 1, increments the incoming (lowest-scoring) student's score by 1.

---

## Excel Input Format

- File must be `.xlsx`.
- First column header must be `name` (GUI) — the bot reads the first column dynamically.
- Each row is one student; only the first two whitespace-separated tokens of the name are kept.

---

## Architecture Notes

### GUI (`GUI_for_quedis.py`)

- Single class `QuedisApp` wraps all functionality; instantiated in `__main__`.
- Subject name aliases are defined as sets in `__main__` (not inside the class):
  - `civil_name_set`, `criminal_name_set`, `labour_name_set`
- Subject resolution is done by checking user input against these sets; unrecognised input calls `exit()`.
- All database calls are synchronous and open/close the connection within each method.
- Window: 500×500 px main window; sub-actions open `Toplevel` dialogs.

### Telegram Bot (`quedis_bot.py`)

- Uses `aiogram` dispatcher with **lambda-based message filters** (not FSM states from the framework).
- State is tracked via **module-level global boolean flags**:
  - `waiting_for_subject_name`
  - `waiting_for_students_file`
  - `waiting_for_distributing`
  - `waiting_for_change`
- `username` is a module-level global string holding the current user's Telegram username.
- **This design is not safe for concurrent users** — a second user's message will interfere with the first user's pending state.
- Subject names are normalised before storage: `message.text.strip().replace(' ', '_').lower()`.
- In the bot, subjects are selected by **index number** (shown in a list), not by name alias as in the GUI.
- Downloaded Excel files are saved to `downloads/{username}.xlsx`.

---

## Known Limitations and Issues

1. **SQL injection surface:** Table and column names are interpolated directly into SQL f-strings (e.g., `f"SELECT name, {subject} FROM StudentScores"`). Column names come from `PRAGMA table_info` or user input, so this is partially trusted — but avoid accepting arbitrary column names from untrusted sources.
2. **Single-user bot only:** Global state variables mean the bot breaks under concurrent usage by multiple Telegram users.
3. **Hardcoded bot token:** `API_TOKEN = ''` on line 9 of `quedis_bot.py` must be set before use. Do not commit a real token to version control.
4. **No `downloads/` directory creation:** The bot assumes `downloads/` exists; it will crash if it doesn't.
5. **GUI exits on unknown subject:** `exit()` is called on unrecognised subject input instead of showing an error dialog.
6. **No tests:** There is no test suite of any kind.

---

## Conventions

### Naming

- Functions and variables: `snake_case`
- Class: `PascalCase` (`QuedisApp`)
- Database table: `PascalCase` (`StudentScores`)
- Database columns: `snake_case` with underscores (e.g., `civil_law`, `labour_law`)
- Subject names normalised to lowercase with underscores when stored

### Language

- All UI text and user-facing messages are in **Russian**.
- Code comments are in Russian and occasionally English.
- Variable and function names are in English.

### Database Access Pattern

Both files follow the same pattern — open connection, execute, commit, close — within each function call. There is no persistent connection or connection pool.

```python
conn = sqlite3.connect('students_scores.db')
cur = conn.cursor()
# ... queries ...
conn.commit()
conn.close()
```

---

## Development Workflows

### Adding a New Feature

1. Decide which interface(s) to update (GUI, bot, or both).
2. For the **bot**: add a new keyboard button to `main_keyboard`, add a handler with `@dp.message(lambda ...)`, and if multi-step input is needed add a new global flag.
3. For the **GUI**: add a new entry to `self.options`, add a branch in `run_option()`, and implement a method on `QuedisApp`.
4. Database schema changes go via `ALTER TABLE` (bot pattern) or a new `CREATE TABLE` column (GUI pattern).

### Manual Testing

There is no automated test runner. Manually test by:

1. Preparing a `student_excel_table.xlsx` with a `name` column and several rows.
2. Running the respective application and exercising each menu option.
3. Inspecting the SQLite database directly with `sqlite3 students_scores.db`.

```bash
sqlite3 students_scores.db "SELECT * FROM StudentScores;"
```

### Git Workflow

The project uses a single `master` branch (origin also has `main`). Feature branches follow the pattern `claude/<description>-<id>`.
