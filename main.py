from time import sleep
from telegram.ext import ApplicationBuilder
from config import TRANSMISSION_HOST, TG_BOT_TOKEN, ALLOWED_TG_IDS, HEARTBEAT_KEY
from logger import logger
from httpx import AsyncClient
import asyncio

from torrent_manager import TransmissionClient, MonitorOrchestrator, PBSearcher
from tg_bot import TgBotRunner


PERIOD_SECONDS = 60 * 60 * 8
users_whitelist = [int(uid) for uid in ALLOWED_TG_IDS.split(",")]
admin_tg_id = users_whitelist[0]

torrent_searcher = PBSearcher()
monitors_orchestrator = MonitorOrchestrator()
transmission = TransmissionClient(TRANSMISSION_HOST)

runner = TgBotRunner(tg_client=ApplicationBuilder().token(TG_BOT_TOKEN).build(),
                     torrent_client=transmission,
                     torrent_searcher=torrent_searcher,
                     monitors_orchestrator=monitors_orchestrator,
                     tg_user_whitelist=users_whitelist)


async def emit_heartbeat():
    async with AsyncClient(timeout=10) as client:
        await client.get("https://uptime.betterstack.com/api/v1/heartbeat/" + HEARTBEAT_KEY)


@logger.catch
async def run_search_jobs_on_timer(timer_seconds):
    logger.debug("run_search_jobs_on_timer running")
    await emit_heartbeat()
    await runner.download_new_finds(admin_tg_id)
    sleep(timer_seconds)
    await run_search_jobs_on_timer(timer_seconds)


# @logger.catch(level="WARNING")
async def bot_poll():
    logger.debug("bot_poll started")
    runner.tg_client.run_polling()


async def main():
    await asyncio.gather(run_search_jobs_on_timer(PERIOD_SECONDS), bot_poll())


if __name__ == '__main__':
    asyncio.run(run_search_jobs_on_timer(PERIOD_SECONDS))
