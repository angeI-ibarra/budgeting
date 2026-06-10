import os
import re
import csv
import datetime
from typing import List, Dict, Any, Optional

from .config import CONTRIBUTION_401K_AMOUNT, CONTRIBUTION_HSA_AMOUNT

def get_latest_file(folder_path: str, pattern: str) -> Optional[str]:
    """
    Finds the latest file in folder_path matching the regex pattern (case-insensitive).
    Returns the absolute path, or None if no matching file is found.
    """
    if not os.path.exists(folder_path):
        return None
    matching_files: List[str] = []
    for entry in os.listdir(folder_path):
        if re.search(pattern, entry, re.IGNORECASE):
            full_path: str = os.path.join(folder_path, entry)
            if os.path.isfile(full_path):
                matching_files.append(full_path)
    if not matching_files:
        return None
    # Sort by modification time to get the latest
    matching_files.sort(key=lambda path: os.path.getmtime(path), reverse=True)
    return matching_files[0]

def parse_date_flexible(date_string: Any) -> Optional[datetime.date]:
    """Attempts to parse a date string in various common formats."""
    if not date_string:
        return None
    date_string_cleaned: str = str(date_string).strip()
    for date_format in ('%m/%d/%Y', '%Y-%m-%d', '%m/%d/%y', '%Y/%m/%d'):
        try:
            return datetime.datetime.strptime(date_string_cleaned, date_format).date()
        except ValueError:
            continue
    return None

def parse_nfcu_csv_credit(file_path: str) -> List[Dict[str, Any]]:
    """
    Parses NFCU Credit Card (Visa/AMX) CSV files.
    All incoming raw transactions are positive; we apply signs based on Type Group.
    """
    transactions_list: List[Dict[str, Any]] = []
    with open(file_path, mode='r', encoding='utf-8-sig') as csv_file:
        csv_reader: csv.DictReader = csv.DictReader(csv_file)
        for csv_row in csv_reader:
            # NFCU fields: 'Transaction Date' or 'Posting Date', 'Amount', 'Description', 'Type Group'
            date_string: Optional[str] = csv_row.get('Transaction Date') or csv_row.get('Posting Date')
            if not date_string:
                continue
            date_object: Optional[datetime.date] = parse_date_flexible(date_string)

            amount_string: Optional[str] = csv_row.get('Amount')
            if not amount_string:
                continue
            try:
                amount_value: float = float(amount_string.replace('$', '').replace(',', '').strip())
            except ValueError:
                continue

            # Reset amount to positive as raw incoming transactions are positive
            amount_value = abs(amount_value)
            description: str = csv_row.get('Description', '').strip()

            # NFCU Credit Cards (AMX/Visa): Use Type Group
            type_group: str = csv_row.get('Type Group', '').strip().lower()
            if type_group == 'payment':
                pass
            elif type_group == 'purchase':
                amount_value = -amount_value
            transactions_list.append({
                'date': date_object,
                'amount': amount_value,
                'description': description,
                'raw': csv_row
            })
    return transactions_list

def parse_nfcu_csv_checking(file_path: str) -> List[Dict[str, Any]]:
    """
    Parses NFCU Checking CSV files.
    All incoming raw transactions are positive; we apply signs based on Description keywords.
    Also handles Lyra Health special checks, HSA, and 401k deductions.
    """
    transactions_list: List[Dict[str, Any]] = []
    with open(file_path, mode='r', encoding='utf-8-sig') as csv_file:
        csv_reader: csv.DictReader = csv.DictReader(csv_file)
        for csv_row in csv_reader:
            # NFCU fields: 'Transaction Date' or 'Posting Date', 'Amount', 'Description'
            date_string: Optional[str] = csv_row.get('Transaction Date') or csv_row.get('Posting Date')
            if not date_string:
                continue
            date_object: Optional[datetime.date] = parse_date_flexible(date_string)

            amount_string: Optional[str] = csv_row.get('Amount')
            if not amount_string:
                continue
            try:
                amount_value: float = float(amount_string.replace('$', '').replace(',', '').strip())
            except ValueError:
                continue

            # Reset amount to positive as raw incoming transactions are positive
            amount_value = abs(amount_value)
            description: str = csv_row.get('Description', '').strip()

            # NFCU Checking: Inspect Description column.
            # Positive only if description contains: "Transfer From", "Deposit", "Dividend", or
            # "Reward Redemption".
            is_positive: bool = False
            description_uppercase: str = description.upper()
            for keyword in ["TRANSFER FROM", "DEPOSIT", "DIVIDEND", "REWARD REDEMPTION", "PAID FAMILY"]:
                if keyword in description_uppercase:
                    is_positive = True
                    break
            if not is_positive:
                amount_value = -amount_value

            # Lyra Health check: increase amount and add 401k/HSA deduction transactions
            # Exclude entries that contain "coupa"
            if "LYRA" in description_uppercase and "COUPA" not in description_uppercase:
                amount_value += CONTRIBUTION_401K_AMOUNT + CONTRIBUTION_HSA_AMOUNT

                transactions_list.append({
                    'date': date_object,
                    'amount': amount_value,
                    'description': description,
                    'raw': csv_row
                })

                transactions_list.append({
                    'date': date_object,
                    'amount': -CONTRIBUTION_401K_AMOUNT,
                    'description': "401k",
                    'raw': csv_row
                })

                transactions_list.append({
                    'date': date_object,
                    'amount': -CONTRIBUTION_HSA_AMOUNT,
                    'description': "HSA",
                    'raw': csv_row
                })
            else:
                transactions_list.append({
                    'date': date_object,
                    'amount': amount_value,
                    'description': description,
                    'raw': csv_row
                })
    return transactions_list

def parse_amx_csv(file_path: str) -> List[Dict[str, Any]]:
    """Parses American Express (Gold/Plat) CSV files."""
    transactions_list: List[Dict[str, Any]] = []
    with open(file_path, mode='r', encoding='utf-8-sig') as csv_file:
        csv_reader: csv.DictReader = csv.DictReader(csv_file)
        for csv_row in csv_reader:
            # AMEX fields: 'Date', 'Description', 'Amount'
            date_string: Optional[str] = csv_row.get('Date')
            if not date_string:
                continue
            date_object: Optional[datetime.date] = parse_date_flexible(date_string)

            amount_string: Optional[str] = csv_row.get('Amount')
            if not amount_string:
                continue
            try:
                amount_value: float = float(amount_string.replace('$', '').replace(',', '').strip())
            except ValueError:
                continue

            # Negate: outflows are positive in CSV, should be negative in sheet.
            # Payments are negative in CSV, should be positive in sheet.
            amount_value = -amount_value

            description: str = csv_row.get('Description', '').strip()
            transactions_list.append({
                'date': date_object,
                'amount': amount_value,
                'description': description,
                'raw': csv_row
            })
    return transactions_list

def parse_chase_csv(file_path: str) -> List[Dict[str, Any]]:
    """Parses Chase Visa CSV files."""
    transactions_list: List[Dict[str, Any]] = []
    with open(file_path, mode='r', encoding='utf-8-sig') as csv_file:
        csv_reader: csv.DictReader = csv.DictReader(csv_file)
        for csv_row in csv_reader:
            # Chase fields: 'Transaction Date' or 'Post Date', 'Description', 'Amount'
            date_string: Optional[str] = csv_row.get('Transaction Date') or csv_row.get('Post Date')
            if not date_string:
                continue
            date_object: Optional[datetime.date] = parse_date_flexible(date_string)

            amount_string: Optional[str] = csv_row.get('Amount')
            if not amount_string:
                continue
            try:
                amount_value: float = float(amount_string.replace('$', '').replace(',', '').strip())
            except ValueError:
                continue

            # Keep sign as is (outflows are negative, inflows are positive)
            description: str = csv_row.get('Description', '').strip()
            transactions_list.append({
                'date': date_object,
                'amount': amount_value,
                'description': description,
                'raw': csv_row
            })
    return transactions_list
