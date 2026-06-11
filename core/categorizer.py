import re
import datetime
from typing import List, Dict, Any, Optional

from .category_rules import build_category_rules_registry, BaseCategoryRule

_category_rule_registry_cache: Dict[int, List[BaseCategoryRule]] = {}


def get_category_rule_registry(category_rules: Dict[str, List[str]]) -> List[BaseCategoryRule]:
    """Retrieves or compiles the registry of matching category rules."""
    global _category_rule_registry_cache
    category_rules_identity: int = id(category_rules)
    if category_rules_identity in _category_rule_registry_cache:
        return _category_rule_registry_cache[category_rules_identity]

    category_rule_registry: List[BaseCategoryRule] = build_category_rules_registry(category_rules)

    _category_rule_registry_cache[category_rules_identity] = category_rule_registry
    return category_rule_registry


def preprocess_transfer_description(transaction: Dict[str, Any], account_key: str, all_transactions: Dict[str, List[Dict[str, Any]]]) -> bool:
    """
    Identifies if a transaction is an account transfer and updates its description in place.
    Returns True if updated, False otherwise.
    """
    description_uppercase: str = transaction['description'].upper()
    amount_value: float = transaction['amount']
    date_object: datetime.date = transaction['date']

    # AMX (Gold/Plat)
    if account_key in ['amx_gold', 'amx_plat']:
        if any(keyword in description_uppercase for keyword in ["MOBILE PAYMENT", "ONLINE PAYMENT"]):
            transaction['description'] = "Transfer from NFCU Checking"
            return True

    # Chase Visa
    elif account_key == 'chase_visa':
        if "PAYMENT THANK YOU" in description_uppercase:
            transaction['description'] = "Transfer from NFCU Checking"
            return True

    # NFCU Credit Cards (Visa/AMX)
    elif account_key in ['nfcu_visa', 'nfcu_amx']:
        if "CREDIT CARD PAYMENT" in description_uppercase:
            transaction['description'] = "Transfer from NFCU Checking"
            return True

    # NFCU Checking
    elif account_key == 'nfcu_checking':
        if amount_value < 0:
            if "TRANSFER TO CREDIT CARD -6915" in description_uppercase:
                transaction['description'] = "Transfer to NFCU AMEX"
                return True
            elif "TRANSFER TO CREDIT CARD -4617" in description_uppercase:
                transaction['description'] = "Transfer to NFCU Visa"
                return True
            elif "CHASE" in description_uppercase:
                transaction['description'] = "Transfer to Chase Visa"
                return True
            elif any(re.search(rf"\b{keyword}\b", description_uppercase) for keyword in ["AMERICAN EXPRESS", "AMX", "AMEX"]):
                # Note: NFCU Checking statements log a generic outflow (e.g., "Amex Epayment")
                # without specifying the destination card (Gold vs. Platinum).
                # To resolve this, we perform a look-ahead cross-reference scan over parsed AMX Gold
                # and Platinum transactions in memory to find the card that received the matching
                # payment of the same amount within a 5-day window.
                # If found, we dynamically rewrite the description; otherwise, we fall back to a generic name.
                target_amount: float = abs(amount_value)
                matched_card: Optional[str] = None

                # Check parsed AMX Gold transactions for the corresponding payment
                gold_transactions: List[Dict[str, Any]] = all_transactions.get('amx_gold', [])
                for gold_transaction in gold_transactions:
                    gold_desc_upper: str = gold_transaction['description'].upper()
                    if any(keyword in gold_desc_upper for keyword in ["MOBILE PAYMENT", "ONLINE PAYMENT"]) and abs(gold_transaction['amount'] - target_amount) < 0.01:
                        if abs((gold_transaction['date'] - date_object).days) <= 5:
                            matched_card = "AMX Gold"
                            break

                # Check parsed AMX Platinum transactions
                if not matched_card:
                    platinum_transactions: List[Dict[str, Any]] = all_transactions.get('amx_plat', [])
                    for platinum_transaction in platinum_transactions:
                        plat_desc_upper: str = platinum_transaction['description'].upper()
                        if any(keyword in plat_desc_upper for keyword in ["MOBILE PAYMENT", "ONLINE PAYMENT"]) and abs(platinum_transaction['amount'] - target_amount) < 0.01:
                            if abs((platinum_transaction['date'] - date_object).days) <= 5:
                                matched_card = "AMX Platinum"
                                break

                if matched_card:
                    transaction['description'] = f"Transfer to {matched_card}"
                else:
                    transaction['description'] = "Transfer to AMX Card"
                return True

        # Checking inflows (amount is positive)
        else:
            if "TRANSFER FROM" in description_uppercase:
                # Exception: do not count as Account Transfer if it is from Raymond Castillo Jr or Zelle
                if not any(keyword in description_uppercase for keyword in ["RAYMOND CASTILLO JR", "ZELLE"]):
                    return True

    return False


def match_transaction_type(transaction: Dict[str, Any], account_key: str, all_transactions: Dict[str, List[Dict[str, Any]]], valid_types: List[str], category_rules: Dict[str, List[str]]) -> str:
    """
    Matches a transaction against transfer category rules, starting balances, or regex category rules
    using a sequential category rule registry.
    """
    # Preprocess description to handle transfer rewriting in place
    preprocess_transfer_description(transaction, account_key, all_transactions)

    category_rule_registry: List[BaseCategoryRule] = get_category_rule_registry(category_rules)
    for category_rule in category_rule_registry:
        matched_category: str = category_rule.apply(transaction, account_key, all_transactions, valid_types)
        if matched_category:
            return matched_category

    return ""

def match_account_name(target_name: str, account_list: List[str]) -> str:
    """Fuzzy matches the target account name to the list of accounts from Google Sheets."""
    def normalize(name: str) -> str:
        normalized_name: str = name.lower()
        normalized_name = normalized_name.replace('nfcu', 'navy federal')
        normalized_name = normalized_name.replace('amx', 'amex')
        normalized_name = normalized_name.replace('american express', 'amex')
        return re.sub(r'[^a-z0-9]', '', normalized_name)

    target_normalized: str = normalize(target_name)

    # Try exact normalized match
    for account in account_list:
        account_normalized: str = normalize(account)
        if target_normalized == account_normalized:
            return account

    # Try substring match
    for account in account_list:
        account_normalized = normalize(account)
        if target_normalized in account_normalized or account_normalized in target_normalized:
            return account

    return target_name
