import os
import sys
import json
from google.oauth2.service_account import Credentials

def resolve_credentials(credentials_path, scopes=None):
    """Resolves and loads Google service account credentials, trying the Keychain, env var, and file fallback."""
    if scopes is None:
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]

    credentials = None

    # 1. Try Keychain loading via keyring library
    try:
        import keyring
        keyring_service = "BudgetingAutomation"
        keyring_account = "google_service_account"
        credentials_json_string = keyring.get_password(keyring_service, keyring_account)
        if credentials_json_string:
            print("\nConnecting to Google Sheets using credentials from macOS Keychain...")
            credentials_info = json.loads(credentials_json_string)
            credentials = Credentials.from_service_account_info(credentials_info, scopes=scopes)
            return credentials
    except Exception as keyring_error:
        # Silently pass if keyring fails or is not populated
        pass

    # 2. Try Environment Variable fallback
    credentials_env_value = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    if credentials_env_value:
        print("\nConnecting to Google Sheets using credentials from GOOGLE_APPLICATION_CREDENTIALS_JSON environment variable...")
        try:
            credentials_info = json.loads(credentials_env_value)
            credentials = Credentials.from_service_account_info(credentials_info, scopes=scopes)
            return credentials
        except Exception as env_error:
            print(f"Error loading credentials from environment variable: {env_error}")
            sys.exit(1)

    # 3. Try plain-text local file fallback
    absolute_credentials_path = os.path.abspath(credentials_path)
    if not os.path.exists(absolute_credentials_path):
        print(f"Error: Credentials not found in macOS Keychain, GOOGLE_APPLICATION_CREDENTIALS_JSON, or at file: {absolute_credentials_path}")
        print("Please follow the setup_guide.md to generate and securely store your service account key.")
        sys.exit(1)

    print(f"\nConnecting to Google Sheets using credentials file: {absolute_credentials_path}...")
    try:
        credentials = Credentials.from_service_account_file(absolute_credentials_path, scopes=scopes)
        return credentials
    except Exception as file_error:
        print(f"Error loading credentials file: {file_error}")
        sys.exit(1)
