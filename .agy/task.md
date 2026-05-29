# Code Modularization Refactoring Tasks

- [x] Create `core/` package files
  - [x] Create empty `core/__init__.py`
  - [x] Create `core/config.py` and populate with configuration constants and variables
  - [x] Create `core/auth.py` and populate with `resolve_credentials` logic
  - [x] Create `core/parser.py` and populate with CSV parsing functions and helpers
  - [x] Create `core/categorizer.py` and populate with categorization rules and matches
- [x] Refactor existing code references
  - [x] Refactor `app.py` to act as orchestrator, importing modules from `core`
  - [x] Refactor `test/test_app.py` to import helper functions from `core` modules
- [x] Verification & Testing
  - [x] Run test suite: `python3 test/test_app.py`
  - [x] Execute dry run: `python3 app.py --dry-run`
  - [x] Execute live sync: `python3 -u app.py`
