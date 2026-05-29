import re

def match_transaction_type(transaction, account_key, all_transactions, valid_types, rules):
    """
    Matches a transaction against transfer rules, starting balances, or regex rules.
    Updates the transaction description if it is identified as an Account Transfer.
    """
    description = transaction['description']
    description_uppercase = description.upper()
    amount_value = transaction['amount']
    date_object = transaction['date']

    # 1. Check Account Transfer rules
    is_transfer = False
    new_description = description

    # AMX (Gold/Plat)
    if account_key in ['amx_gold', 'amx_plat']:
        if any(keyword in description_uppercase for keyword in ["MOBILE PAYMENT", "ONLINE PAYMENT"]):
            is_transfer = True
            new_description = "Transfer from NFCU Checking"

    # Chase Visa
    elif account_key == 'chase_visa':
        if "PAYMENT THANK YOU" in description_uppercase:
            is_transfer = True
            new_description = "Transfer from NFCU Checking"

    # NFCU Credit Cards (Visa/AMX)
    elif account_key in ['nfcu_visa', 'nfcu_amx']:
        if "CREDIT CARD PAYMENT" in description_uppercase:
            is_transfer = True
            new_description = "Transfer from NFCU Checking"

    # NFCU Checking
    elif account_key == 'nfcu_checking':
        # Checking outflows to credit cards (amount is negative)
        if amount_value < 0:
            if "TRANSFER TO CREDIT CARD -6915" in description_uppercase:
                is_transfer = True
                new_description = "Transfer to NFCU AMEX"
            elif "TRANSFER TO CREDIT CARD -4617" in description_uppercase:
                is_transfer = True
                new_description = "Transfer to NFCU Visa"
            elif "CHASE" in description_uppercase:
                is_transfer = True
                new_description = "Transfer to Chase Visa"
            elif any(keyword in description_uppercase for keyword in ["AMERICAN EXPRESS", "AMX", "AMEX"]):
                # Look-ahead/cross-referencing logic to find target card (Gold vs Plat)
                target_amount = abs(amount_value)
                matched_card = None

                # Check parsed AMX Gold transactions for the corresponding payment
                gold_transactions = all_transactions.get('amx_gold', [])
                for gold_transaction in gold_transactions:
                    if any(keyword in gold_transaction['description'].upper() for keyword in ["MOBILE PAYMENT", "ONLINE PAYMENT"]) and abs(gold_transaction['amount'] - target_amount) < 0.01:
                        if abs((gold_transaction['date'] - date_object).days) <= 5:
                            matched_card = "AMX Gold"
                            break

                # Check parsed AMX Platinum transactions
                if not matched_card:
                    platinum_transactions = all_transactions.get('amx_plat', [])
                    for platinum_transaction in platinum_transactions:
                        if any(keyword in platinum_transaction['description'].upper() for keyword in ["MOBILE PAYMENT", "ONLINE PAYMENT"]) and abs(platinum_transaction['amount'] - target_amount) < 0.01:
                            if abs((platinum_transaction['date'] - date_object).days) <= 5:
                                matched_card = "AMX Platinum"
                                break

                is_transfer = True
                if matched_card:
                    new_description = f"Transfer to {matched_card}"
                else:
                    new_description = "Transfer to AMX Card"

        # Checking inflows (amount is positive)
        else:
            if "TRANSFER FROM" in description_uppercase:
                # Exception: do not count as Account Transfer if it is from Raymond Castillo Jr or Zelle
                if not any(keyword in description_uppercase for keyword in ["RAYMOND CASTILLO JR", "ZELLE"]):
                    is_transfer = True

    if is_transfer:
        transaction['description'] = new_description
        return "Account Transfer"

    # 2. Check explicit contribution/Lyra rules
    if description_uppercase == "401K":
        return next((valid_type for valid_type in valid_types if valid_type.lower() == "401k"), "401k")
    if description_uppercase == "HSA":
        return next((valid_type for valid_type in valid_types if valid_type.lower() == "hsa"), "HSA")
    if "LYRA" in description_uppercase and "COUPA" not in description_uppercase:
        return next((valid_type for valid_type in valid_types if valid_type.lower() == "balance adjustment"), "Balance Adjustment")

    # 3. Check regular expression rules
    description_cleaned = re.sub(r'\s+', ' ', description.strip().lower())
    for category, patterns in rules.items():
        # Skip special categories handled above
        if category in ["Account Transfer", "Balance Adjustment", "Starting Balance"]:
            continue
        for pattern in patterns:
            try:
                if re.search(pattern, description_cleaned, re.IGNORECASE):
                    matched_value = next((valid_type for valid_type in valid_types if valid_type.lower() == category.lower()), None)
                    if matched_value:
                        return matched_value
            except re.error as error:
                print(f"Warning: Invalid regex '{pattern}' for category '{category}': {error}")

    # 4. Check Balance Adjustment (deposits in Checking not matched to transfer/income)
    if account_key == 'nfcu_checking' and amount_value > 0:
        matched_value = next((valid_type for valid_type in valid_types if valid_type.lower() == "balance adjustment"), "Balance Adjustment")
        return matched_value

    return ""

def match_account_name(target_name, account_list):
    """Fuzzy matches the target account name to the list of accounts from Google Sheets."""
    def normalize(name):
        normalized_name = name.lower()
        normalized_name = normalized_name.replace('nfcu', 'navy federal')
        normalized_name = normalized_name.replace('amx', 'amex')
        normalized_name = normalized_name.replace('american express', 'amex')
        return re.sub(r'[^a-z0-9]', '', normalized_name)

    target_normalized = normalize(target_name)

    # Try exact normalized match
    for account in account_list:
        account_normalized = normalize(account)
        if target_normalized == account_normalized:
            return account

    # Try substring match
    for account in account_list:
        account_normalized = normalize(account)
        if target_normalized in account_normalized or account_normalized in target_normalized:
            return account

    return target_name
