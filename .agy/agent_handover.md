# Agent Handover Context: Google Sheets Budgeting Automation

This document provides context, design patterns, and constraints for the next agent working on the Budgeting Automation tool.

---

## 1. Project Overview
The project is a Python-based utility that automatically parses financial statement exports (CSV format) from various institutions, normalizes their transactions, matches categories, handles account transfers, processes payroll adjustments, and syncs them to a Google Sheet.

* **Repository Root:** `/Users/angel/Documents/Dev/Budgeting`
* **Google Sheet ID:** `1V9jTJgLd5Y2V9Fn7JTwOS8IisdmXe82Vy5Lh7rBQgeY`

---

## 2. Directory & File Structure
* **`app.py`**: The high-level runner and orchestrator script. Sets up argument parsing and coordinates the execution loop.
* **`core/`**: The main package containing modular application libraries:
  * **`core/__init__.py`**: Exposes the package API for simple imports.
  * **`core/config.py`**: Global constants (`SHEET_NAME`, contribution levels, and bank `ACCOUNTS_CONFIG` patterns).
  * **`core/auth.py`**: Handles credential retrieval and authentication flow.
  * **`core/parser.py`**: Contains CSV parsers for bank and credit statements.
  * **`core/categorizer.py`**: Transaction classification rules and transfer cross-referencing logic.
* **`test/test_app.py`**: The unit test suite, updated to test functions imported directly from `core`.
* **`Statements/`**: Local folder where raw statement CSV files are placed.
* **`transaction_rules.json`**: Local category rules mapping categories to regex patterns.
* **`all_accounts.json`**: Local JSON cache of valid account names.
* **`setup_guide.md`**: Guide for setting up service accounts, credentials storage, and APIs.

---

## 3. Core Features & Business Logic

### A. Sign Normalization
Different banks export outflows and inflows with conflicting signs. The script normalizes all values such that:
* **Outflows** are negative (`< 0`).
* **Inflows / Payments** are positive (`> 0`).
* *Note:* NFCU Checking imports are adjusted to negative unless description keywords contain `"Transfer From"`, `"Deposit"`, `"Dividend"`, `"Reward Redemption"`, or `"Paid Family"`.

### B. Account Transfers & Cross-Referencing
* Transfers between credit cards and checking accounts are classified as `"Account Transfer"`.
* When processing NFCU Checking outflows, the script performs a look-ahead cross-reference search over parsed AMX Gold/Platinum payments matching the transfer amount within a 5-day window to dynamically update checking descriptions (e.g. `"Transfer to AMX Gold"`).

### C. Lyra Health Payroll & Deductions
* Checking transactions containing `"lyra"` (case-insensitive) are treated as payroll deposits.
* **Exclusion Rule:** If the description also contains `"coupa"` (case-insensitive), it is treated as a standard inflow (no adjustment, no dynamic deductions).
* **Standard Payroll Adjustments:**
  1. The net deposit amount is increased by gross deductions: `CONTRIBUTION_401K_AMOUNT` (`1020.83`) and `CONTRIBUTION_HSA_AMOUNT` (`130.00`).
  2. Two corresponding outflow transactions are dynamically generated sharing the same transaction date (type/category: `"401k"` and `"HSA"`, amount: negative contributions, account: `"NFCU Checking"`).
  3. The main payroll deposit is categorized as `"Balance Adjustment"`.

### D. Schema & Sync Markers
* The sheet columns are `[DATE, AMOUNT, TYPE, ACCOUNT, DESCRIPTION, LAST UPDATED]`.
* Every successful sync appends a marker row at the end of the batch: `[current_run_date, "", "", "", "", "*"]`.
* The deduplication check ignores this marker row and verifies unique keys constructed as `(date, description.lower(), round(amount, 2))`.

### E. Secure Credentials Resolution
* Credentials for Google Sheets API are resolved dynamically from:
  1. System Keychain (using the `keyring` library to look up service `"BudgetingAutomation"`, account `"google_service_account"`).
  2. Environment variable `GOOGLE_APPLICATION_CREDENTIALS_JSON` containing the JSON contents (fallback).
  3. Local `service_account.json` plain-text file in the project folder (backward-compatible fallback).

---

## 4. Key Developer Constraints
1. **Fully Verbose Variable Names:** Always use descriptive, fully verbose variable names everywhere (including loop indexes, dictionary comprehensions, etc.). Never use short or abbreviated variables like `t`, `n`, or `acc`.
2. **Dry Run Mode:** `python3 app.py --dry-run` performs parsing and local-only logic using local backups (`all_accounts.json` and `transaction_rules.json`), writing output to `test/dry_run_results.csv` without hitting the Google Sheets API.
3. **Execution Commands:**
   * Test Suite: `python3 test/test_app.py`
   * Dry Run: `python3 app.py --dry-run`
   * Live Sync: `python3 -u app.py` (requires credentials stored in macOS Keychain, set in `GOOGLE_APPLICATION_CREDENTIALS_JSON`, or locally at `service_account.json`)

