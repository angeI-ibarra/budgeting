#!/usr/bin/env python3
import os
import sys
import unittest
import tempfile
import csv
from datetime import date

# Add parent directory to Python path to import app module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core import (
    parse_nfcu_csv, 
    parse_amx_csv, 
    parse_chase_csv, 
    match_transaction_type, 
    match_account_name,
    resolve_credentials,
    CONTRIBUTION_401K_AMOUNT,
    CONTRIBUTION_HSA_AMOUNT
)

MOCK_RULES = {
    "Rent": ["midtown station rent"],
    "Groceries": ["pcc - central", "costco"],
    "Dining Out": ["daves hot chi", "overcast coff", "temple pastri", "big marios", "tacos chukis", "broadcast coffee"],
    "Travel": ["united airlines", "axp centurion lounge", "volaris", "frontier airlines", "li\\.me"],
    "Insurance": ["banner life", "usaa"],
    "Investments": ["coinbase"],
    "Income": ["lyra health"],
    "Utilities": ["t-mobile", "astound"],
    "Subscriptions": ["disneyplus", "youtube", "1password"],
    "Shopping": ["lululemon", "tj maxx", "amazon"],
    "Home Improvement": ["home depot"],
    "Entertainment": ["met museum"],
    "Transfers": ["mobile payment", "payment thank you", "zelle", "amex epayment", "chase credit crd", "credit card payment", "transfer from", "transfer to"],
    "Fees": ["membership fee"]
}

class TestBudgetAutomation(unittest.TestCase):

    def setUp(self):
        # Create temporary directory for mock statements
        self.temporary_directory = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_parse_nfcu_checking(self):
        # Write mock NFCU Checking CSV file (all raw amounts are positive in YTD exports)
        file_path = os.path.join(self.temporary_directory.name, "Checking.csv")
        with open(file_path, mode='w', newline='', encoding='utf-8') as mock_file:
            csv_writer = csv.writer(mock_file)
            csv_writer.writerow(["Posting Date", "Transaction Date", "Amount", "Description"])
            csv_writer.writerow(["05/21/2026", "05/21/2026", "73.64", "Payment to Banner Life Insurance Company"])
            csv_writer.writerow(["05/18/2026", "05/18/2026", "120.00", "Transfer From Raymond Castillo"])
            csv_writer.writerow(["05/14/2026", "05/14/2026", "4215.90", "Deposit Lyra Health - Payroll"])
            csv_writer.writerow(["05/10/2026", "05/10/2026", "500.00", "Deposit Lyra via Coupa Inc"])
            csv_writer.writerow(["05/01/2026", "05/01/2026", "50.00", "Transfer to Coinbase"])

        # Parse with account_type='cash'
        transactions = parse_nfcu_csv(file_path, account_type='cash')
        self.assertEqual(len(transactions), 7)
        
        # Outflow: Payment to Banner Life -> -73.64
        self.assertEqual(transactions[0]['date'], date(2026, 5, 21))
        self.assertEqual(transactions[0]['amount'], -73.64)
        self.assertEqual(transactions[0]['description'], "Payment to Banner Life Insurance Company")

        # Inflow: "Transfer From ..." -> +120.00
        self.assertEqual(transactions[1]['date'], date(2026, 5, 18))
        self.assertEqual(transactions[1]['amount'], 120.00)

        # Inflow: "Deposit Lyra..." -> +5366.73 (4215.90 + CONTRIBUTION_401K_AMOUNT + CONTRIBUTION_HSA_AMOUNT)
        self.assertEqual(transactions[2]['date'], date(2026, 5, 14))
        self.assertEqual(transactions[2]['amount'], 4215.90 + CONTRIBUTION_401K_AMOUNT + CONTRIBUTION_HSA_AMOUNT)

        # 401k Contribution
        self.assertEqual(transactions[3]['date'], date(2026, 5, 14))
        self.assertEqual(transactions[3]['amount'], -CONTRIBUTION_401K_AMOUNT)
        self.assertEqual(transactions[3]['description'], "401k")

        # HSA Contribution
        self.assertEqual(transactions[4]['date'], date(2026, 5, 14))
        self.assertEqual(transactions[4]['amount'], -CONTRIBUTION_HSA_AMOUNT)
        self.assertEqual(transactions[4]['description'], "HSA")

        # Inflow containing both Lyra and Coupa (should remain unadjusted)
        self.assertEqual(transactions[5]['date'], date(2026, 5, 10))
        self.assertEqual(transactions[5]['amount'], 500.00)
        self.assertEqual(transactions[5]['description'], "Deposit Lyra via Coupa Inc")

        # Outflow: "Transfer to ..." -> -50.00
        self.assertEqual(transactions[6]['date'], date(2026, 5, 1))
        self.assertEqual(transactions[6]['amount'], -50.00)

    def test_parse_nfcu_credit_card(self):
        # Write mock NFCU Visa/AMX credit card CSV (raw amounts positive)
        file_path = os.path.join(self.temporary_directory.name, "Visa.csv")
        with open(file_path, mode='w', newline='', encoding='utf-8') as mock_file:
            csv_writer = csv.writer(mock_file)
            csv_writer.writerow(["Posting Date", "Transaction Date", "Amount", "Description", "Type Group"])
            csv_writer.writerow(["05/01/2026", "05/01/2026", "70.00", "Credit Card Payment Received", "Payment"])
            csv_writer.writerow(["04/01/2026", "03/31/2026", "70.00", "Astound Wilkes-Barre", "Purchase"])

        # Parse with account_type='credit'
        transactions = parse_nfcu_csv(file_path, account_type='credit')
        self.assertEqual(len(transactions), 2)

        # Payment -> Should be positive (70.00)
        self.assertEqual(transactions[0]['date'], date(2026, 5, 1))
        self.assertEqual(transactions[0]['amount'], 70.00)

        # Purchase -> Should be negative (-70.00)
        self.assertEqual(transactions[1]['date'], date(2026, 3, 31))
        self.assertEqual(transactions[1]['amount'], -70.00)

    def test_parse_amx(self):
        # Write mock AMX CSV file (charges positive, payments negative in source)
        file_path = os.path.join(self.temporary_directory.name, "Gold.csv")
        with open(file_path, mode='w', newline='', encoding='utf-8') as mock_file:
            csv_writer = csv.writer(mock_file)
            csv_writer.writerow(["Date", "Description", "Amount"])
            csv_writer.writerow(["05/23/2026", "THURSDAY LONDON GB", "49.50"])
            csv_writer.writerow(["05/01/2026", "MOBILE PAYMENT - THANK YOU", "-548.42"])

        transactions = parse_amx_csv(file_path)
        self.assertEqual(len(transactions), 2)

        # AMX charge: 49.50 -> -49.50
        self.assertEqual(transactions[0]['date'], date(2026, 5, 23))
        self.assertEqual(transactions[0]['amount'], -49.50)

        # AMX payment: -548.42 -> 548.42
        self.assertEqual(transactions[1]['date'], date(2026, 5, 1))
        self.assertEqual(transactions[1]['amount'], 548.42)

    def test_parse_chase(self):
        # Write mock Chase CSV file (charges negative, payments positive in source)
        file_path = os.path.join(self.temporary_directory.name, "Visa.CSV")
        with open(file_path, mode='w', newline='', encoding='utf-8') as mock_file:
            csv_writer = csv.writer(mock_file)
            csv_writer.writerow(["Transaction Date", "Post Date", "Description", "Category", "Type", "Amount", "Memo"])
            csv_writer.writerow(["05/21/2026", "05/22/2026", "AMAZON MKTPL*W56XT6GQ3", "Shopping", "Sale", "-29.84", ""])
            csv_writer.writerow(["05/01/2026", "05/01/2026", "Payment Thank You-Mobile", "", "Payment", "1234.38", ""])

        transactions = parse_chase_csv(file_path)
        self.assertEqual(len(transactions), 2)

        # Chase charge: -29.84 -> -29.84
        self.assertEqual(transactions[0]['amount'], -29.84)

        # Chase payment: 1234.38 -> 1234.38
        self.assertEqual(transactions[1]['amount'], 1234.38)

    def test_match_transaction_type_rules(self):
        valid_types = ["Account Transfer", "Balance Adjustment", "Starting Balance", "Dining Out", "Rent", "Income"]
        
        # Test basic regex matches
        transaction_dining = {'description': "Daves Hot Chicken", 'amount': -15.50, 'date': date(2026, 5, 20)}
        self.assertEqual(match_transaction_type(transaction_dining, 'chase_visa', {}, valid_types, MOCK_RULES), "Dining Out")

        transaction_rent = {'description': "Midtown Station Rent", 'amount': -2500.00, 'date': date(2026, 5, 5)}
        self.assertEqual(match_transaction_type(transaction_rent, 'nfcu_checking', {}, valid_types, MOCK_RULES), "Rent")

        # Test Balance Adjustment (deposit not matched to income/transfer)
        transaction_adjustment = {'description': "Random Deposit from Friend", 'amount': 50.00, 'date': date(2026, 5, 10)}
        self.assertEqual(match_transaction_type(transaction_adjustment, 'nfcu_checking', {}, valid_types, MOCK_RULES), "Balance Adjustment")

        # Test Lyra Health -> Balance Adjustment
        transaction_lyra = {'description': "Deposit Lyra Health - Payroll", 'amount': 4215.90 + CONTRIBUTION_401K_AMOUNT + CONTRIBUTION_HSA_AMOUNT, 'date': date(2026, 5, 14)}
        self.assertEqual(match_transaction_type(transaction_lyra, 'nfcu_checking', {}, valid_types, MOCK_RULES), "Balance Adjustment")

        # Test 401k Contribution -> 401k
        valid_types_with_contribs = valid_types + ["401k", "HSA"]
        transaction_401k = {'description': "401k", 'amount': -CONTRIBUTION_401K_AMOUNT, 'date': date(2026, 5, 14)}
        self.assertEqual(match_transaction_type(transaction_401k, 'nfcu_checking', {}, valid_types_with_contribs, MOCK_RULES), "401k")

        # Test HSA Contribution -> HSA
        transaction_hsa = {'description': "HSA", 'amount': -CONTRIBUTION_HSA_AMOUNT, 'date': date(2026, 5, 14)}
        self.assertEqual(match_transaction_type(transaction_hsa, 'nfcu_checking', {}, valid_types_with_contribs, MOCK_RULES), "HSA")

    def test_match_transaction_type_transfers(self):
        valid_types = ["Account Transfer"]
        
        # AMX credit card payment
        transaction_american_express = {'description': "MOBILE PAYMENT - THANK YOU", 'amount': 548.42, 'date': date(2026, 5, 1)}
        type_american_express = match_transaction_type(transaction_american_express, 'amx_gold', {}, valid_types, MOCK_RULES)
        self.assertEqual(type_american_express, "Account Transfer")
        self.assertEqual(transaction_american_express['description'], "Transfer from NFCU Checking")

        # Chase credit card payment
        transaction_chase = {'description': "Payment Thank You-Mobile", 'amount': 1234.38, 'date': date(2026, 5, 1)}
        type_chase = match_transaction_type(transaction_chase, 'chase_visa', {}, valid_types, MOCK_RULES)
        self.assertEqual(type_chase, "Account Transfer")
        self.assertEqual(transaction_chase['description'], "Transfer from NFCU Checking")

        # Checking transfer to NFCU AMX
        transaction_to_american_express = {'description': "Transfer To Credit Card -6915", 'amount': -70.00, 'date': date(2026, 5, 1)}
        type_to_american_express = match_transaction_type(transaction_to_american_express, 'nfcu_checking', {}, valid_types, MOCK_RULES)
        self.assertEqual(type_to_american_express, "Account Transfer")
        self.assertEqual(transaction_to_american_express['description'], "Transfer to NFCU AMEX")

        # Checking transfer to AMX Gold (Cross-referenced with MOBILE PAYMENT)
        all_parsed_transactions = {
            'amx_gold': [
                {'date': date(2026, 5, 3), 'amount': 548.42, 'description': "MOBILE PAYMENT - THANK YOU"}
            ]
        }
        transaction_checking_american_express = {'description': "Amex Epayment ACH Pmt", 'amount': -548.42, 'date': date(2026, 5, 4)}
        type_checking_american_express = match_transaction_type(transaction_checking_american_express, 'nfcu_checking', all_parsed_transactions, valid_types, MOCK_RULES)
        self.assertEqual(type_checking_american_express, "Account Transfer")
        self.assertEqual(transaction_checking_american_express['description'], "Transfer to AMX Gold")


        # Checking transfer to AMX Gold (Cross-referenced with ONLINE PAYMENT)
        all_parsed_transactions_online = {
            'amx_gold': [
                {'date': date(2026, 5, 3), 'amount': 3873.05, 'description': "ONLINE PAYMENT - THANK YOU"}
            ]
        }
        transaction_checking_online = {'description': "Amex Epayment ACH Pmt", 'amount': -3873.05, 'date': date(2026, 5, 4)}
        type_checking_online = match_transaction_type(transaction_checking_online, 'nfcu_checking', all_parsed_transactions_online, valid_types, MOCK_RULES)
        self.assertEqual(type_checking_online, "Account Transfer")
        self.assertEqual(transaction_checking_online['description'], "Transfer to AMX Gold")

        # Checking inflow transfer (should maintain original description)
        transaction_checking_inflow = {'description': "Transfer From Raymond Castillo", 'amount': 120.00, 'date': date(2026, 5, 18)}
        type_checking_inflow = match_transaction_type(transaction_checking_inflow, 'nfcu_checking', {}, valid_types, MOCK_RULES)
        self.assertEqual(type_checking_inflow, "Account Transfer")
        self.assertEqual(transaction_checking_inflow['description'], "Transfer From Raymond Castillo")

        # Checking inflow transfer exceptions (should not be marked as Account Transfer, fallback to Balance Adjustment)
        transaction_checking_exception_1 = {'description': "Transfer From Raymond Castillo Jr -0362", 'amount': 120.00, 'date': date(2026, 5, 18)}
        type_checking_exception_1 = match_transaction_type(transaction_checking_exception_1, 'nfcu_checking', {}, valid_types, MOCK_RULES)
        self.assertEqual(type_checking_exception_1, "Balance Adjustment")
        self.assertEqual(transaction_checking_exception_1['description'], "Transfer From Raymond Castillo Jr -0362")

        transaction_checking_exception_2 = {'description': "Transfer from Zelle", 'amount': 200.00, 'date': date(2026, 5, 13)}
        type_checking_exception_2 = match_transaction_type(transaction_checking_exception_2, 'nfcu_checking', {}, valid_types, MOCK_RULES)
        self.assertEqual(type_checking_exception_2, "Balance Adjustment")
        self.assertEqual(transaction_checking_exception_2['description'], "Transfer from Zelle")

    def test_match_account_name(self):
        accounts_list = ["Navy Federal Checking", "AMX Gold Card", "Chase Visa", "Navy Federal Visa"]
        self.assertEqual(match_account_name("NFCU Checking", accounts_list), "Navy Federal Checking")
        self.assertEqual(match_account_name("AMX Gold", accounts_list), "AMX Gold Card")
        self.assertEqual(match_account_name("Chase Visa", accounts_list), "Chase Visa")

    def test_resolve_credentials_keyring(self):
        from unittest.mock import patch, MagicMock
        
        # Test case 1: Keyring yields credentials
        mock_credentials_object = MagicMock()
        mock_json_string = '{"type": "service_account", "project_id": "test"}'
        
        with patch('keyring.get_password') as mock_get_password, \
             patch('google.oauth2.service_account.Credentials.from_service_account_info') as mock_from_info:
            mock_get_password.return_value = mock_json_string
            mock_from_info.return_value = mock_credentials_object
            
            resolved_credentials = resolve_credentials("dummy_path.json")
            self.assertEqual(resolved_credentials, mock_credentials_object)
            mock_get_password.assert_called_once_with("BudgetingAutomation", "google_service_account")

    def test_resolve_credentials_env_variable(self):
        from unittest.mock import patch, MagicMock
        
        # Test case 2: Keyring is empty, environment variable yields credentials
        mock_credentials_object = MagicMock()
        mock_json_string = '{"type": "service_account", "project_id": "test_env"}'
        
        with patch('keyring.get_password') as mock_get_password, \
             patch('google.oauth2.service_account.Credentials.from_service_account_info') as mock_from_info, \
             patch.dict('os.environ', {'GOOGLE_APPLICATION_CREDENTIALS_JSON': mock_json_string}):
            mock_get_password.return_value = None
            mock_from_info.return_value = mock_credentials_object
            
            resolved_credentials = resolve_credentials("dummy_path.json")
            self.assertEqual(resolved_credentials, mock_credentials_object)

    def test_resolve_credentials_file_fallback(self):
        from unittest.mock import patch, MagicMock
        
        # Test case 3: Keyring is empty, env var is empty, file exists and yields credentials
        mock_credentials_object = MagicMock()
        
        with patch('keyring.get_password') as mock_get_password, \
             patch.dict('os.environ', {}, clear=True), \
             patch('os.path.exists') as mock_path_exists, \
             patch('google.oauth2.service_account.Credentials.from_service_account_file') as mock_from_file:
            mock_get_password.return_value = None
            mock_path_exists.return_value = True
            mock_from_file.return_value = mock_credentials_object
            
            resolved_credentials = resolve_credentials("dummy_path.json")
            self.assertEqual(resolved_credentials, mock_credentials_object)

if __name__ == '__main__':
    unittest.main()
