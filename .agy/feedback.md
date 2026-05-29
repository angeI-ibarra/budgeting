# Feedback & Code Review Updates: Configuration Initialization

Please update the script initialization and Google Sheets connection logic according to the following technical specifications.

### 1. Configuration & Rules Renaming
* The file `rules.json` is being replaced by `transaction_rules.json`.
* The categorization rules (keys) inside `transaction_rules.json` must be dynamically named after the transaction types found in the **"Backend Data"** tab under the **"Transaction Type"** column.
* **Pre-Run Initialization:** Implement a dedicated initialization method to set up or verify these local JSON storage files before the main parsing pipeline executes.

### 2. Updated Connection & Authentication Logic
Modify the "Authenticate and connect to Google Sheet" lifecycle step to split behaviors based on the `dry_run` flag:

#### Case A: If `dry_run` is True (Local Only)
1. **Accounts:** Fetch the allowed accounts locally from the `all_accounts.json` file.
2. **Transaction Types:** Fetch the transaction types locally from the `transaction_rules.json` file (where the keys represent the valid types). Do not attempt to hit the Google Sheets API.

#### Case B: If `dry_run` is False (Production/Live Sync)
1. **Accounts Sync:**
   * Fetch the live list of accounts from the Google Sheet.
   * Create or update the local `all_accounts.json` file with this latest list.
2. **Transaction Rules Sync:**
   * Fetch the live transaction types from the Google Sheet.
   * Create or update the local `transaction_rules.json` file.
   * **Crucial:** Append any *new* transaction types as keys to the JSON object. Do **not** overwrite or erase any existing rules or mappings already configured in the file.


### 3. Naming Convention
1. Do not abbreviate variable names. Be descriptive and clear. This includes variables in for loops
