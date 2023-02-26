import os
from multiprocessing import Process
from time import sleep
from dotenv import load_dotenv

from transmission_client import TransmissionClient, download_paths, transmission_error
from pb_orchestrator import MonitorOrchestrator, PBMonitor
from pb_client import PBSearcher

from telegram.ext import ApplicationBuilder
from tg_bot import TgBotRunner

load_dotenv()
PERIOD_SECONDS = 60 * 60 * 8

torrent_searcher = PBSearcher()
monitors_orchestrator = MonitorOrchestrator()

try:
    transmission = TransmissionClient(
        os.getenv("TRANSMISSION_HOST"), download_paths)
except transmission_error.TransmissionConnectError:
    raise "can't connect to the host"

users_whitelist = [int(uid) for uid in os.getenv("ALLOWED_TG_IDS").split(",")]
admin_tgid = users_whitelist[0]
tg_client = ApplicationBuilder().token(os.getenv("TG_BOT_TOKEN")).build()

runner = TgBotRunner(tg_client=tg_client, torrent_client=transmission,
                     torrent_searcher=torrent_searcher, monitors_orchestrator=monitors_orchestrator, tg_user_whitelist=users_whitelist)


def run_search_jobs_on_timer(timer_seconds):
    search_results = runner.run_search_jobs(admin_tgid)
    if search_results:
        sleep(5)
        run_search_jobs_on_timer(timer_seconds)
    else:
        sleep(timer_seconds)
        run_search_jobs_on_timer(timer_seconds)


def bot_poll():
    runner.tg_client.run_polling()


if __name__ == '__main__':
    [process.start() for process in
     (Process(target=run_search_jobs_on_timer, args=(PERIOD_SECONDS,)),
      Process(target=bot_poll))]
