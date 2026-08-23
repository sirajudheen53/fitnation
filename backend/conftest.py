"""Pytest configuration — use SQLite for tests."""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///test_db.sqlite3")