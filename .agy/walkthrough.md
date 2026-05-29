# Budget Automation Tool Walkthrough

This document summarizes the final solution for syncing financial CSVs with your Google Sheet.

## What was Implemented

1. **Robust Configuration & File Discovery**:
   - The script defaults to finding `Statements/` in the same directory as `app.py`.
   - Automatically scans and resolves the latest modified CSV file for each financial institution/account.
2. **Updated Configuration & Rules File**:
   - Replaced legacy `rules.json` with `transaction_rules.json`. The legacy file migration has completed successfully, and references to it have been removed from the script.
3. **Conditioned Connection & Authentication Logic**:
   - **Case A: Local Only (`--dry-run`)**: Fetches allowed accounts locally from `all_accounts.json` and transaction rules from `transaction_rules.json` (using keys as the valid transaction types). It does not call the Google Sheets API. If these files are missing in dry-run mode, the script gracefully exits with an instructions message.
   - **Case B: Live Sync (Default)**: Connects to Google Sheets. Fetches the live list of accounts and transaction types from the **"Backend Data"** tab under the **"All Accounts"** and **"Transaction Type"** columns. Saves/updates `all_accounts.json` and appends any new transaction types as keys to `transaction_rules.json` without overwriting existing rules or patterns.
4. **Corrected Sign Normalization**:
   - **NFCU Checking**: Deposits/transfers-in are parsed as positive (checked via description keywords `"Transfer From"`, `"Deposit"`, `"Dividend"`, or `"Reward Redemption"`), and all other outflows are parsed as negative.
   - **NFCU Credit Cards (AMX/Visa)**: Purchases are negative (matching how credit card balances increase) and payments/transfers-in are positive.
   - **AMX Gold/Platinum**: Negates amounts so outflows are negative and payments/inflows are positive.
   - **Chase Visa**: Amounts are kept as is (charges are negative, payments positive).
5. **Account Transfer Rules & Look-Ahead cross-referencing**:
   - Special rules identify transactions as `"Account Transfer"` and update their description dynamically.
   - For NFCU Checking transfers to American Express, the script look-aheads and cross-references the parsed AMX Gold and Platinum transactions to find the exact matching payment amount (matching descriptions containing `"MOBILE PAYMENT"`) within a 5-day window. It then logs the description as `"Transfer to AMX Gold"` or `"Transfer to AMX Platinum"`.
6. **Payroll Deduction & Contribution Tracking**:
   - Defined global configuration variables for pre-tax deductions: `CONTRIBUTION_401K_AMOUNT` (`1020.83`) and `CONTRIBUTION_HSA_AMOUNT` (`130.00`).
   - When parsing Checking, any transaction containing `"lyra"` (case-insensitive) represents a payroll deposit:
     1. The deposit amount value is adjusted to reflect gross pay by adding the 401k and HSA amounts.
     2. Two separate outflow transactions are dynamically generated sharing the same date: a 401k contribution (`-1020.83`) and an HSA contribution (`-130.00`).
   - Custom type mappers categorise these transactions to their respective Sheet categories (`"401k"`, `"HSA"`, and `"Balance Adjustment"`).
7. **6-Column Schema & LAST UPDATED Marker**:
   - Schema matches `[DATE, AMOUNT, TYPE, ACCOUNT, DESCRIPTION, LAST UPDATED]`.
   - Regular transactions have an empty string `""` in the `LAST UPDATED` column.
   - When new transactions are found to append, the script appends a marker row at the end of the batch: `[current_run_date, "", "", "", "", "*"]` (where `current_run_date` is today's date). This marks the exact time the sheet was updated.
   - The deduplication engine reads the 6 columns but skips the marker row because it has no numeric `AMOUNT` value, avoiding any duplication issues.
8. **Chronological Sorting**:
   - All transactions are sorted by date in ascending chronological order before export or upload.
9. **Clean, Verbose Naming Convention**:
    - Fully refactored variable names in both `app.py` and `test/test_app.py` to remove any abbreviations (e.g. `n` -> `normalized_name`, `t` -> `transaction`, `acc_col_idx` -> `accounts_column_index`, `type_chk_amx` -> `type_checking_american_express`).
10. **Secure Credentials Storage (Keychain Integration)**:
    - Integrated Python's `keyring` library to securely load Google service account JSON from the macOS Keychain (service `"BudgetingAutomation"`, account `"google_service_account"`).
    - Implemented a robust fallback hierarchy: first attempting Keychain retrieval, falling back to a `GOOGLE_APPLICATION_CREDENTIALS_JSON` environment variable, and falling back to a plain-text local `service_account.json` file.
    - Updated [setup_guide.md](file:///Users/angel/Documents/Dev/Budgeting/setup_guide.md) with steps to manually store the JSON credentials inside the system Keychain using a simple python terminal command and safely delete the file from disk.
11. **Codebase Modularization**:
    - Partitioned the codebase into a clean python package subdirectory named `core/`.
    - Moved configuration and global parameters into [core/config.py](file:///Users/angel/Documents/Dev/Budgeting/core/config.py).
    - Moved credential resolution logic into [core/auth.py](file:///Users/angel/Documents/Dev/Budgeting/core/auth.py).
    - Moved CSV parser logic and helper functions into [core/parser.py](file:///Users/angel/Documents/Dev/Budgeting/core/parser.py).
    - Moved categorization rules and matching functions into [core/categorizer.py](file:///Users/angel/Documents/Dev/Budgeting/core/categorizer.py).
    - Refactored [app.py](file:///Users/angel/Documents/Dev/Budgeting/app.py) to act as a lightweight orchestrator importing modules from `core`.
    - Updated [test/test_app.py](file:///Users/angel/Documents/Dev/Budgeting/test/test_app.py) to load imports directly from the `core` package.

---

## Validation & Test Results

### 1. Automated Unit Tests
We executed the automated unit test suite after modularizing the codebase:
`python3 test/test_app.py`
All 10 tests passed successfully, validating parsing accuracy, account transfers, secure credential resolution, and package layout integrity.

```
Ran 10 tests in 0.028s

OK
```

### 2. Dry Run Verification
We executed a local dry run of the script:
`python3 app.py --dry-run`
- Verified that `"Deposit Lyra Health, Inc Coupa Pay"` (on 2026-01-20) remains unadjusted at `238.07` and does not generate separate `401k` or `HSA` transactions.
- Verified that the modular script successfully resolves local accounts and rules configurations.

### 3. Keychain Authentication & Live Sync Verification
We ran a live synchronization run:
`python3 -u app.py 2>&1 | tee debug.log`
- Verified that the modular script successfully imports dependencies and resolves Keychain credentials.
- Verified that it correctly connects to Google Sheets, syncs configurations, checks existing transactions, and validates that the budget is up to date.


