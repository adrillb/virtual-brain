"""Shared configuration: API tokens, base URLs, headers."""

import os
from pathlib import Path
from dotenv import load_dotenv

_HERE = Path(__file__).resolve().parent
load_dotenv(_HERE / ".env")

# --- OpenAI ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# --- Telegram ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
USERS_FILE = _HERE / "users.json"

# --- Timezone ---
TIMEZONE = os.getenv("TIMEZONE", "Europe/Madrid")

# --- MeisterTask ---
MT_TOKEN = os.getenv("MEISTERTASK_TOKEN", "")
MT_BASE_URL = "https://www.meistertask.com/api"
MT_HEADERS = {
    "Authorization": f"Bearer {MT_TOKEN}",
    "Content-Type": "application/json",
}
