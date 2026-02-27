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
# Logging: console + daily rotated file in logs/
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
LOG_DIR = _HERE / "logs"
LOG_DIR.mkdir(exist_ok=True)

log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

# Console handler (all loggers — for live terminal output)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(log_format))

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(console_handler)

# Silence noisy third-party loggers (getUpdates polling)
for _noisy in ("httpx", "telegram.ext", "apscheduler"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

# File handler: one file per day, e.g. logs/virtual_brain_2026-02-16.txt
# Only attached to OUR loggers (bot, __main__) — not to httpx/telegram internals
log_filename = LOG_DIR / f"virtual_brain_{datetime.now():%Y-%m-%d}.txt"
file_handler = TimedRotatingFileHandler(
    log_filename, when="midnight", interval=1, backupCount=30, encoding="utf-8"
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(log_format))
file_handler.namer = lambda name: name.replace(".txt.", "_") + ".txt" if ".txt." in name else name

for logger_name in ("bot", "__main__"):
    _logger = logging.getLogger(logger_name)
    _logger.addHandler(file_handler)


# ---------------------------------------------------------------------------
# Global error handler: send exception info to the user via Telegram
# ---------------------------------------------------------------------------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a message to the user."""
    logger = logging.getLogger(__name__)
    logger.error("Excepción no controlada: %s", context.error, exc_info=context.error)

    if isinstance(update, Update) and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"⚠️ Error interno:\n{type(context.error).__name__}: {context.error}",
            )
        except Exception:
            logger.error("No se pudo enviar el mensaje de error al chat.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.add_error_handler(error_handler)

    # ---- Proactive daily tasks summary at 08:00 (Europe/Madrid) ----
    if TELEGRAM_CHAT_ID:
        tz = ZoneInfo(TIMEZONE)
        app.job_queue.run_daily(
            send_daily_tasks,
            time=time(hour=18, minute=48, tzinfo=tz),
            data=TELEGRAM_CHAT_ID,
            name="daily_tasks_summary",
        )
        logging.info("Resumen diario programado a las 06:30 (%s) para chat=%s", TIMEZONE, TELEGRAM_CHAT_ID)
    else:
        logging.warning("TELEGRAM_CHAT_ID no configurado: el resumen diario de tareas está desactivado.")

    logging.info("Virtual Brain conectado a MeisterTask...")
    app.run_polling()
