# Proposed Code Modularization Plan

This plan outlines the architecture, file layout, and implications of refactoring the single-file `app.py` script into a modular Python package structure.

## Pros & Cons Analysis

### Pros
* **Separation of Concerns:** Clearly segregates parsing logic, Google Sheets communication, authentication, and transaction classification rules into distinct, single-purpose modules.
* **Maintainability & Scale:** Reduces files from a single 750+ line script into smaller files (under 150 lines each), making edits easier to navigate and review.
* **Extensibility:** Easily add new banks/credit cards by updating a dedicated parsing module, without touching the main execution pipeline or Sheets code.
* **Isolated Testing:** Simplifies writing clean mocks and unit tests specifically targeting parsing or classification rules in isolation.

### Cons
* **Import Path Overhead:** Introducing a multi-file folder structure requires handling Python modules correctly, which can add minor setup hurdles for running tests (e.g. configuring search paths in `sys.path`).
* **Loss of Portability:** A single-file script can be easily copied and run anywhere; a partitioned package requires copying the entire directory structure.
* **Integration Regression Risk:** Refactoring runs the risk of circular imports or scope issues with global constants (like `CONTRIBUTION_401K_AMOUNT` or `SHEET_NAME`).

---

## Proposed Architecture & File Structure

We propose splitting the code into a sub-folder package called `core/`.

```
Budgeting/
│
├── app.py                      # Main entry point (CLI argument parsing and orchestration loop)
│
├── core/
│   ├── __init__.py             # Exposes core package interfaces
│   ├── config.py               # Config constants (ACCOUNTS_CONFIG, contribution values, etc.)
│   ├── auth.py                 # resolve_credentials() helper
│   ├── parser.py               # Statement parser functions (NFCU Checking, AMX, Chase, etc.)
│   └── categorizer.py          # Category and rules matching logic
│
└── test/
    └── test_app.py             # Unit tests (updated to import from core.*)
```

---

## Component Breakdown

### 1. [core/config.py](file:///Users/angel/Documents/Dev/Budgeting/core/config.py) [NEW]
Holds all global constants, bank CSV matching patterns, and contribution values:
* `SHEET_NAME`, `CONTRIBUTION_401K_AMOUNT`, `CONTRIBUTION_HSA_AMOUNT`
* `ACCOUNTS_CONFIG` definitions

### 2. [core/auth.py](file:///Users/angel/Documents/Dev/Budgeting/core/auth.py) [NEW]
Contains secure credentials lookup logic:
* `resolve_credentials()` function

### 3. [core/parser.py](file:///Users/angel/Documents/Dev/Budgeting/core/parser.py) [NEW]
Handles files search and CSV conversions:
* `get_latest_file()`, `parse_date_flexible()`
* `parse_nfcu_csv()`, `parse_amx_csv()`, `parse_chase_csv()`

### 4. [core/categorizer.py](file:///Users/angel/Documents/Dev/Budgeting/core/categorizer.py) [NEW]
Applies mapping rules:
* `match_transaction_type()`, `match_account_name()`

### 5. [app.py](file:///Users/angel/Documents/Dev/Budgeting/app.py) [MODIFY]
Retains only orchestration:
* Sets up CLI parsing and runs `initialize_local_files()`
* Connects to Google Sheets via `core/auth.py`
* Loops through files and parses them via `core/parser.py`
* Runs categorization and deduplication via `core/categorizer.py`
* Performs final spreadsheet update operations

### 6. [test/test_app.py](file:///Users/angel/Documents/Dev/Budgeting/test/test_app.py) [MODIFY]
* Updated to import parsing and rule matchers directly from the `core/` package.

---

## Verification Plan

### Automated Tests
* Run the unit test suite after partition to guarantee zero regressions:
  `python3 test/test_app.py`

### Manual Verification
* Run a dry run sync to ensure parsing and local categorization logic is intact:
  `python3 app.py --dry-run`
* Run a live sync to verify successful credentials resolution and Sheets API synchronization:
  `python3 -u app.py`
