import re
import datetime
from typing import List, Dict, Any, Type, Callable, Optional

class BaseCategoryRule:
    """Base class for all transaction matching category rules."""
    def matches(self, transaction: Dict[str, Any], account_key: str, all_transactions: Dict[str, List[Dict[str, Any]]]) -> bool:
        raise NotImplementedError

    def get_category(self, valid_types: List[str], transaction: Dict[str, Any]) -> str:
        raise NotImplementedError

    def apply(self, transaction: Dict[str, Any], account_key: str, all_transactions: Dict[str, List[Dict[str, Any]]], valid_types: List[str]) -> str:
        """Applies the category rule. Returns the matched category, or an empty string if no match."""
        if self.matches(transaction, account_key, all_transactions):
            return self.get_category(valid_types, transaction)
        return ""


_special_category_rules: List[Type[BaseCategoryRule]] = []


def register_category_rule(rule_class: Type[BaseCategoryRule]) -> Type[BaseCategoryRule]:
    """Decorator to register special category rules in priority order."""
    _special_category_rules.append(rule_class)
    return rule_class


@register_category_rule
class AccountTransferCategoryRule(BaseCategoryRule):
    """Rule to check if a transaction satisfies account transfer conditions."""
    def matches(self, transaction: Dict[str, Any], account_key: str, all_transactions: Dict[str, List[Dict[str, Any]]]) -> bool:
        description_uppercase: str = transaction['description'].upper()

        # Check preprocessed/rewritten descriptions
        if any(keyword in description_uppercase for keyword in [
            "TRANSFER FROM NFCU CHECKING",
            "TRANSFER TO NFCU AMEX",
            "TRANSFER TO NFCU VISA",
            "TRANSFER TO CHASE VISA",
            "TRANSFER TO AMX CARD",
            "TRANSFER TO AMX GOLD",
            "TRANSFER TO AMX PLATINUM"
        ]):
            return True

        # Checking inflows (amount is positive)
        if account_key == 'nfcu_checking' and transaction['amount'] > 0:
            if "TRANSFER FROM" in description_uppercase:
                if not any(keyword in description_uppercase for keyword in ["RAYMOND CASTILLO JR", "ZELLE"]):
                    return True

        return False

    def get_category(self, valid_types: List[str], transaction: Dict[str, Any]) -> str:
        return "Account Transfer"


@register_category_rule
class ExplicitContributionCategoryRule(BaseCategoryRule):
    """Matches 401k and HSA explicit contributions."""
    def matches(self, transaction: Dict[str, Any], account_key: str, all_transactions: Dict[str, List[Dict[str, Any]]]) -> bool:
        description_uppercase: str = transaction['description'].upper()
        return description_uppercase in ["401K", "HSA"]

    def get_category(self, valid_types: List[str], transaction: Dict[str, Any]) -> str:
        description_uppercase: str = transaction['description'].upper()
        return "401k" if description_uppercase == "401K" else "HSA"


@register_category_rule
class LyraPayrollCategoryRule(BaseCategoryRule):
    """Matches Lyra Health payroll deposits."""
    def matches(self, transaction: Dict[str, Any], account_key: str, all_transactions: Dict[str, List[Dict[str, Any]]]) -> bool:
        description_uppercase: str = transaction['description'].upper()
        return "LYRA" in description_uppercase and "COUPA" not in description_uppercase

    def get_category(self, valid_types: List[str], transaction: Dict[str, Any]) -> str:
        return "Balance Adjustment"


@register_category_rule
class MomAidSpecialCategoryRule(BaseCategoryRule):
    """Matches Mom aid"""
    def matches(self, transaction: Dict[str, Any], account_key: str, all_transactions: Dict[str, List[Dict[str, Any]]]) -> bool:
        description_uppercase: str = transaction['description'].upper()
        amount_value: float = transaction['amount']
        if "APPLE" in description_uppercase and abs(abs(amount_value) - 2.99) < 0.01:
            return True
        if account_key == 'nfcu_checking' and abs(amount_value) == 200 and "ZELLE" in description_uppercase:
            return True

    def get_category(self, valid_types: List[str], transaction: Dict[str, Any]) -> str:
        return "Mom Aid"

@register_category_rule
class RothIraCategoryRule(BaseCategoryRule):
    "Matches Roth IRA"
    def matches(self, transaction: Dict[str, Any], account_key: str, all_transactions: Dict[str, List[Dict[str, Any]]]) -> bool:
        description_uppercase: str = transaction['description'].upper()
        amount_value: float = transaction['amount']
        if "FIDELITY INVESTMENTS" in description_uppercase and  abs(abs(amount_value) - 318.18) < 0.01:
            return True

    def get_category(self, valid_types: List[str], transaction: Dict[str, Any]) -> str:
        return "Roth IRA"

@register_category_rule
class EmergencyFundCategoryRule(BaseCategoryRule):
    "Matches Emergency Fund"
    def matches(self, transaction: Dict[str, Any], account_key: str, all_transactions: Dict[str, List[Dict[str, Any]]]) -> bool:
        description_uppercase: str = transaction['description'].upper()
        amount_value: float = transaction['amount']
        if "FIDELITY INVESTMENTS" in description_uppercase and  abs(abs(amount_value) - 400) < 0.01:
            return True

    def get_category(self, valid_types: List[str], transaction: Dict[str, Any]) -> str:
        return "Emergency Fund"


class RegexCategoryRule(BaseCategoryRule):
    """Standard regex pattern matching category rule compiled from json rules."""
    category: str
    pattern_string: str
    compiled_pattern: Optional[re.Pattern]

    def __init__(self, category: str, pattern_string: str):
        self.category = category
        self.pattern_string = pattern_string
        try:
            self.compiled_pattern = re.compile(pattern_string, re.IGNORECASE)
        except re.error as error:
            print(f"Warning: Invalid regex '{pattern_string}' for category '{self.category}': {error}")
            self.compiled_pattern = None

    def matches(self, transaction: Dict[str, Any], account_key: str, all_transactions: Dict[str, List[Dict[str, Any]]]) -> bool:
        if not self.compiled_pattern:
            return False
        description_cleaned: str = re.sub(r'\s+', ' ', transaction['description'].strip().lower())
        return bool(self.compiled_pattern.search(description_cleaned))

    def get_category(self, valid_types: List[str], transaction: Dict[str, Any]) -> str:
        return next((valid_type for valid_type in valid_types if valid_type.lower() == self.category.lower()), "")


class NfcuCheckingBalanceAdjustmentCategoryRule(BaseCategoryRule):
    """Fallback rule: checking deposits (amount > 0) that haven't been matched."""
    def matches(self, transaction: Dict[str, Any], account_key: str, all_transactions: Dict[str, List[Dict[str, Any]]]) -> bool:
        amount_value: float = transaction['amount']
        return account_key == 'nfcu_checking' and amount_value > 0

    def get_category(self, valid_types: List[str], transaction: Dict[str, Any]) -> str:
        return "Balance Adjustment"


def build_category_rules_registry(category_rules: Dict[str, List[str]]) -> List[BaseCategoryRule]:
    """Assembles the full sequential list of matching category rules."""
    registry: List[BaseCategoryRule] = [rule_class() for rule_class in _special_category_rules]

    for category, patterns in category_rules.items():
        for pattern in patterns:
            registry.append(RegexCategoryRule(category, pattern))

    # Note: NfcuCheckingBalanceAdjustmentCategoryRule acts as a catch-all fallback for any positive checking
    # deposit that didn't match a transfer, paycheck, or custom regex rule. It must be evaluated
    # at the very end of the registry (not registered via @register_category_rule which runs before regexes)
    # to avoid prematurely matching checking deposits that should match specific regex rules.
    registry.append(NfcuCheckingBalanceAdjustmentCategoryRule())
    return registry
