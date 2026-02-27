"""
Virtual Brain -- entry point.
Run: python main.py
"""

import logging
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo
from logging.handlers import TimedRotatingFileHandler

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, TIMEZONE
from bot import handle_message, handle_voice, send_daily_tasks


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))

    # ---- Proactive daily tasks summary at 08:00 (Europe/Madrid) ----
    if TELEGRAM_CHAT_ID:
        tz = ZoneInfo(TIMEZONE)
        send_daily_tasks()
    else:
        logging.warning("TELEGRAM_CHAT_ID no configurado: el resumen diario de tareas está desactivado.")

    logging.info("Virtual Brain conectado a MeisterTask...")
    app.run_polling()
