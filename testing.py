"""Quick one-shot trigger for send_daily_tasks (no schedule)."""

import asyncio
import logging

from telegram.ext import ApplicationBuilder

from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
from bot import send_daily_tasks

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

for _noisy in ("httpx", "telegram.ext", "apscheduler"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)


async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    await app.initialize()
    await app.start()

    app.job_queue.run_once(send_daily_tasks, when=0, data=TELEGRAM_CHAT_ID, name="test_daily_tasks")
    await asyncio.sleep(5)

    await app.stop()
    await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())