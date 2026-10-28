"""All configuration comes from environment variables (the .env file)."""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # Without python-dotenv it still runs if you export the vars yourself
    pass

BASE_DIR = Path(__file__).resolve().parent

TOKEN = os.getenv("DISCORD_TOKEN", "")
PREFIX = os.getenv("COMMAND_PREFIX", "!")
DATA_FILE = Path(os.getenv("DATA_FILE", BASE_DIR / "data.json"))

# Hour (Thai time) at which the daily digest is posted
REMINDER_HOUR = int(os.getenv("REMINDER_HOUR", "8"))
# How many days ahead to warn
REMINDER_LEAD_DAYS = int(os.getenv("REMINDER_LEAD_DAYS", "1"))
# How often the bot wakes up to check whether the digest is due
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "15"))
