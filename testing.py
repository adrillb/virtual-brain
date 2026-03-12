"""Quick one-shot trigger for send_daily_tasks (no schedule)."""

import asyncio
import logging

from telegram.ext import ApplicationBuilder

from config import TELEGRAM_TOKEN
from bot import send_daily_tasks
from users import load_users

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

for _noisy in ("httpx", "telegram.ext", "apscheduler"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)


async def main():
    users = load_users().get("users", {})
    telegram_id = next(
        (
            str(user_id)
            for user_id, user_data in users.items()
            if user_data.get("daily_summary", {}).get("enabled", False)
        ),
        "",
    )
    if not telegram_id:
        logging.warning("No hay usuarios con daily_summary.enabled=true en users.json")
        return

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    await app.initialize()
    await app.start()

    app.job_queue.run_once(
        send_daily_tasks,
        when=0,
        data={"telegram_id": telegram_id},
        name="test_daily_tasks",
    )
    await asyncio.sleep(5)

    await app.stop()
    await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())