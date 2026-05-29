#!/usr/bin/env python3
import os
import csv
import json
import argparse
import collections
import sys
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

from core import (
    SHEET_NAME,
    SCRIPT_DIR,
    STATEMENTS_DIR,
    ACCOUNTS_CONFIG,
    resolve_credentials,
    get_latest_file,
    parse_nfcu_csv,
    parse_amx_csv,
    parse_chase_csv,
    match_transaction_type,
    match_account_name,
    parse_date_flexible
)

def initialize_local_files(dry_run):
    """
    Ensures local storage JSON files exist.
    If dry_run is True, both files must exist, otherwise we exit.
    If dry_run is False, we initialize empty placeholders if they don't exist.
    """
    transaction_rules_path = os.path.join(SCRIPT_DIR, "transaction_rules.json")
    all_accounts_path = os.path.join(SCRIPT_DIR, "all_accounts.json")

    # 1. Handle transaction_rules.json
    if not os.path.exists(transaction_rules_path):
        if dry_run:
            print(f"Error: Required local transaction rules file does not exist: {transaction_rules_path}")
            print("Please run without --dry-run first to synchronize/initialize configuration from Google Sheets.")
            sys.exit(1)
        else:
            try:
                with open(transaction_rules_path, 'w', encoding='utf-8') as rules_file:
                    json.dump({}, rules_file, indent=2)
                print(f"Initialized empty transaction rules file: {transaction_rules_path}")
            except Exception as error:
                print(f"Error creating transaction rules file: {error}")

    # 2. Handle all_accounts.json
    if not os.path.exists(all_accounts_path):
        if dry_run:
            print(f"Error: Required local accounts file does not exist: {all_accounts_path}")
            print("Please run without --dry-run first to synchronize/initialize configuration from Google Sheets.")
            sys.exit(1)
        else:
            try:
                with open(all_accounts_path, 'w', encoding='utf-8') as accounts_file:
                    json.dump([], accounts_file, indent=2)
                print(f"Initialized empty accounts file: {all_accounts_path}")
            except Exception as error:
                print(f"Error creating accounts file: {error}")

def main():
    parser = argparse.ArgumentParser(description="Budgeting Sheet Transactions Sync Tool")
    parser.add_argument('--credentials', default='service_account.json', help='Path to Google Service Account JSON file')
    parser.add_argument('--dry-run', action='store_true', help='Parse and match transactions without writing to Google Sheets')
    args = parser.parse_args()

    # Pre-run initialization
    initialize_local_files(args.dry_run)

    print(f"Scanning for YTD statements in: {STATEMENTS_DIR}")

    # 1. Discover latest statements for configured accounts
    discovered_files = {}
    for account_key, account_configuration in ACCOUNTS_CONFIG.items():
        folder_path = os.path.join(STATEMENTS_DIR, account_configuration['folder'])
        latest_file = get_latest_file(folder_path, account_configuration['pattern'])
        if latest_file:
            modification_time = datetime.fromtimestamp(os.path.getmtime(latest_file)).strftime('%Y-%m-%d %H:%M:%S')
            print(f"Found latest CSV for {account_key}: {os.path.basename(latest_file)} (modified: {modification_time})")
            discovered_files[account_key] = latest_file
        else:
            print(f"Warning: No matching CSV found for {account_key} in {folder_path}")

    if not discovered_files:
        print("Error: No statement CSV files discovered. Exiting.")
        sys.exit(1)

    # 2. Parse all transactions from discovered files
    parsed_transactions = {}
    for account_key, file_path in discovered_files.items():
        account_configuration = ACCOUNTS_CONFIG[account_key]
        parser_type = account_configuration['parser']
        try:
            if parser_type == 'nfcu':
                transactions_list = parse_nfcu_csv(file_path, account_type=account_configuration['account_type'])
            elif parser_type == 'amx':
                transactions_list = parse_amx_csv(file_path)
            elif parser_type == 'chase':
                transactions_list = parse_chase_csv(file_path)
            else:
                transactions_list = []

            # Filter transactions with valid parsed dates
            transactions_list = [transaction for transaction in transactions_list if transaction['date'] is not None]
            parsed_transactions[account_key] = transactions_list
            print(f"Parsed {len(transactions_list)} transactions from {os.path.basename(file_path)}")
        except Exception as error:
            print(f"Error parsing {file_path}: {error}")

    # 3. Authenticate and connect to Google Sheets / Load local storage files
    all_accounts_path = os.path.join(SCRIPT_DIR, "all_accounts.json")
    transaction_rules_path = os.path.join(SCRIPT_DIR, "transaction_rules.json")

    if args.dry_run:
        print("\n--- DRY RUN: Local Sync only ---")
        # Fetch accounts locally
        try:
            with open(all_accounts_path, 'r', encoding='utf-8') as accounts_file:
                all_accounts = json.load(accounts_file)
        except Exception as error:
            print(f"Error reading local accounts file: {error}.")
            sys.exit(1)

        # Fetch transaction types locally from transaction_rules.json
        try:
            with open(transaction_rules_path, 'r', encoding='utf-8') as rules_file:
                rules = json.load(rules_file)
            valid_types = list(rules.keys())
        except Exception as error:
            print(f"Error reading local rules file: {error}.")
            sys.exit(1)

        existing_transaction_frequencies = collections.Counter()
    else:
        if not gspread or not Credentials:
            print("Error: 'gspread' and 'google-auth' libraries are required. Please run: pip install -r requirements.txt")
            sys.exit(1)

        credentials = resolve_credentials(args.credentials)
        try:
            client = gspread.authorize(credentials)
            spreadsheet = client.open(SHEET_NAME)
            print(f"Connected successfully to sheet: '{SHEET_NAME}' (ID: {spreadsheet.id}, URL: {spreadsheet.url})")
        except Exception as connection_error:
            print(f"Error connecting to Google Sheets: {connection_error}")
            sys.exit(1)

        # Fetch metadata from "Backend Data" worksheet
        try:
            # Dynamically resolve tab case-insensitively, with or without spaces
            backend_worksheet = next(
                (worksheet for worksheet in spreadsheet.worksheets() if worksheet.title.lower() in ["backend data", "backenddata"]),
                None
            )
            if not backend_worksheet:
                # Fallback
                backend_worksheet = spreadsheet.worksheet("BackendData")

            print(f"Fetching valid accounts and transaction types from '{backend_worksheet.title}' tab...")
            backend_data = backend_worksheet.get_all_values()

            all_accounts = []
            valid_types = []

            if backend_data:
                headers = [header.strip() for header in backend_data[0]]
                try:
                    accounts_column_index = headers.index("All Accounts")
                except ValueError:
                    print("Warning: 'All Accounts' column not found in BackendData. Defaulting to column index 0.")
                    accounts_column_index = 0
                try:
                    transaction_types_column_index = headers.index("Transaction Type")
                except ValueError:
                    print("Warning: 'Transaction Type' column not found in BackendData. Defaulting to column index 1.")
                    transaction_types_column_index = 1

                for row_data in backend_data[1:]:
                    if len(row_data) > accounts_column_index:
                        account_value = row_data[accounts_column_index].strip()
                        if account_value:
                            all_accounts.append(account_value)
                    if len(row_data) > transaction_types_column_index:
                        transaction_type_value = row_data[transaction_types_column_index].strip()
                        if transaction_type_value:
                            valid_types.append(transaction_type_value)

            print(f"Fetched live accounts: {all_accounts}")
            print(f"Fetched {len(valid_types)} live transaction types.")
        except Exception as error:
            print(f"Error reading 'Backend Data' tab: {error}")
            sys.exit(1)

        # Write/Update local accounts file
        try:
            with open(all_accounts_path, 'w', encoding='utf-8') as accounts_file:
                json.dump(all_accounts, accounts_file, indent=2)
            print(f"Updated local accounts backup file: {all_accounts_path}")
        except Exception as error:
            print(f"Error backing up accounts to local file: {error}")

        # Fetch, Merge and persist transaction rules
        local_rules = {}
        if os.path.exists(transaction_rules_path):
            try:
                with open(transaction_rules_path, 'r', encoding='utf-8') as rules_file:
                    local_rules = json.load(rules_file)
            except Exception as error:
                print(f"Warning: Failed to load local rules for merging: {error}")

        # Append any new transaction types as keys
        for transaction_type in valid_types:
            if transaction_type not in local_rules:
                local_rules[transaction_type] = []
                print(f"Appended new transaction type key to rules: '{transaction_type}'")

        try:
            with open(transaction_rules_path, 'w', encoding='utf-8') as rules_file:
                json.dump(local_rules, rules_file, indent=2)
            print(f"Merged and updated local rules file: {transaction_rules_path}")
        except Exception as error:
            print(f"Error persisting updated rules file: {error}")

        rules = local_rules

        # Fetch existing transactions for deduplication from "Transactions" worksheet
        try:
            transactions_worksheet = spreadsheet.worksheet("Transactions")
            print("Fetching existing transactions from 'Transactions' tab for deduplication...")
            raw_transaction_data = transactions_worksheet.get_all_values()

            existing_transaction_frequencies = collections.Counter()
            if raw_transaction_data:
                headers = [header.strip().upper() for header in raw_transaction_data[0]]
                try:
                    date_index = headers.index('DATE')
                    amount_index = headers.index('AMOUNT')
                    description_index = headers.index('DESCRIPTION')
                except ValueError:
                    # Default layout: [DATE, AMOUNT, TYPE, ACCOUNT, DESCRIPTION, STATUS]
                    date_index, amount_index, description_index = 0, 1, 4

                for row_data in raw_transaction_data[1:]:
                    if len(row_data) <= max(date_index, amount_index, description_index):
                        continue
                    date_value = parse_date_flexible(row_data[date_index])
                    if not date_value:
                        continue
                    try:
                        amount_value = float(row_data[amount_index].replace('$', '').replace(',', '').strip())
                    except ValueError:
                        continue
                    description_value = row_data[description_index].strip().lower()
                    existing_transaction_frequencies[(date_value, description_value, round(amount_value, 2))] += 1
            print(f"Loaded {sum(existing_transaction_frequencies.values())} existing transactions for deduplication.")
        except Exception as error:
            print(f"Error reading 'Transactions' tab: {error}")
            sys.exit(1)

    # 4. Process and categorize transactions
    to_append = []

    print("\nProcessing and categorizing transactions...")
    for account_key, transactions_list in parsed_transactions.items():
        account_configuration = ACCOUNTS_CONFIG[account_key]

        # Determine the sheet account name by fuzzy matching
        sheet_account = match_account_name(account_configuration['default_name'], all_accounts)
        print(f"\nAccount '{account_key}' maps to Google Sheet account: '{sheet_account}'")

        skipped_duplicates = 0
        added_count = 0

        # Standardize matching helper for deduplication
        for transaction in transactions_list:
            # We match transaction types and update descriptions (if account transfer) BEFORE check deduplication
            transaction_type = match_transaction_type(transaction, account_key, parsed_transactions, valid_types, rules)

            date_object = transaction['date']
            amount_value = transaction['amount']
            description = transaction['description']

            # Key for deduplication matching
            deduplication_key = (date_object, description.lower(), round(amount_value, 2))

            if existing_transaction_frequencies[deduplication_key] > 0:
                existing_transaction_frequencies[deduplication_key] -= 1
                skipped_duplicates += 1
                continue

            # Date, Amount, Type, Account, Description, Last Updated
            to_append.append([
                date_object.strftime('%Y-%m-%d'),
                amount_value,
                transaction_type,
                sheet_account,
                description,
                "" # Last Updated is empty for regular transactions
            ])
            added_count += 1

        print(f"  Processed {len(transactions_list)} total: {added_count} new transactions to append, {skipped_duplicates} duplicates skipped.")

    # Sort transactions by date (ascending)
    to_append.sort(key=lambda transaction_row: transaction_row[0])

    # 5. Upload new transactions
    if not to_append:
        print("\nNo new transactions to append. Budget is up to date!")
        return

    # Add the marker row indicating when the sheet was last updated
    current_date_string = datetime.now().strftime('%Y-%m-%d')
    to_append.append([
        current_date_string,
        "",
        "",
        "",
        "",
        "*"
    ])

    print(f"\nTotal new transactions to append: {len(to_append) - 1} (plus 1 update marker row)")

    if args.dry_run:
        output_file_path = os.path.join(SCRIPT_DIR, "test", "dry_run_results.csv")
        print("\n=== DRY RUN TRANSACTIONS TO APPEND (First 10 shown) ===")
        for index, transaction_row in enumerate(to_append[:10]):
            print(f"Row {index+1}: Date={transaction_row[0]}, Amount={transaction_row[1]}, Type={transaction_row[2]}, Account={transaction_row[3]}, Desc={transaction_row[4]}")
        if len(to_append) > 10:
            print(f"... and {len(to_append) - 10} more transactions.")
        print("=====================================================")

        try:
            with open(output_file_path, mode='w', newline='', encoding='utf-8') as output_file:
                writer = csv.writer(output_file)
                writer.writerow(["DATE", "AMOUNT", "TYPE", "ACCOUNT", "DESCRIPTION", "LAST UPDATED"])
                writer.writerows(to_append)
            print(f"Dry run results successfully written to: {output_file_path}")
        except Exception as error:
            print(f"Error writing dry run results file: {error}")
    else:
        try:
            print(f"Uploading {len(to_append)} rows to the 'Transactions' sheet...")
            transactions_worksheet.append_rows(to_append, value_input_option='USER_ENTERED')
            print("Upload completed successfully!")
        except Exception as error:
            print(f"Error appending rows to Google Sheets: {error}")

if __name__ == '__main__':
    main()
