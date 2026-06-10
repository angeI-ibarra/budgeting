import os
from typing import Dict, Any

# Google Sheet Name
SHEET_NAME: str = "Budgeting Sheet"

# Directories (SCRIPT_DIR points to repository root, i.e., parent of core/)
CORE_DIR: str = os.path.dirname(os.path.abspath(__file__))
SCRIPT_DIR: str = os.path.dirname(CORE_DIR)
STATEMENTS_DIR: str = os.path.join(SCRIPT_DIR, "statements")

# Contribution tracking constants
CONTRIBUTION_401K_AMOUNT: float = 1020.83
CONTRIBUTION_HSA_AMOUNT: float = 130.00

# Configuration of bank accounts and statement file patterns
ACCOUNTS_CONFIG: Dict[str, Dict[str, Any]] = {
    'nfcu_checking': {
        'folder': 'NFCU',
        'pattern': r'^checking?\.csv$',
        'account_type': 'cash',
        'default_name': 'NFCU Checking',
        'parser': 'nfcu'
    },
    'nfcu_visa': {
        'folder': 'NFCU',
        'pattern': r'^visa\.csv$',
        'account_type': 'credit',
        'default_name': 'NFCU Visa',
        'parser': 'nfcu'
    },
    'nfcu_amx': {
        'folder': 'NFCU',
        'pattern': r'^amx\.csv$',
        'account_type': 'credit',
        'default_name': 'NFCU AMEX',
        'parser': 'nfcu'
    },
    'amx_gold': {
        'folder': 'AMX',
        'pattern': r'^gold\.csv$',
        'account_type': 'credit',
        'default_name': 'AMX Gold',
        'parser': 'amx'
    },
    'amx_plat': {
        'folder': 'AMX',
        'pattern': r'^plat(inum)?\.csv$',
        'account_type': 'credit',
        'default_name': 'AMX Platinum',
        'parser': 'amx'
    },
    'chase_visa': {
        'folder': 'Chase',
        'pattern': r'^visa\.csv$',
        'account_type': 'credit',
        'default_name': 'Chase Visa',
        'parser': 'chase'
    }
}
