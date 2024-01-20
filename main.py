from multiprocessing import Process
from time import sleep
from telegram.ext import ApplicationBuilder
from telegram.error import NetworkError as TelegramNetworkError
from config import TRANSMISSION_HOST, TG_BOT_TOKEN, ALLOWED_TG_IDS, HEARTBEAT_KEY
from logger import logger
from requests import get

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


def emit_heartbeat():
    get("https://uptime.betterstack.com/api/v1/heartbeat/" + HEARTBEAT_KEY)


def run_search_jobs_on_timer(timer_seconds):
    logger.debug("run_search_jobs_on_timer running")
    emit_heartbeat()
    runner.download_new_finds(admin_tg_id)
    sleep(timer_seconds)
    run_search_jobs_on_timer(timer_seconds)


@logger.catch
def bot_poll():
    logger.debug("bot_poll started")
    try:
        runner.tg_client.run_polling()
    except TelegramNetworkError as e:
        logger.warning("Telegram Network Error", {"error": e})


if __name__ == '__main__':
    [process.start() for process in
     (Process(target=run_search_jobs_on_timer, args=(PERIOD_SECONDS,)),
      Process(target=bot_poll))]
