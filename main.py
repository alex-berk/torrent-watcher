from multiprocessing import Process
from time import sleep
from telegram.ext import ApplicationBuilder
from config import TRANSMISSION_HOST, TG_BOT_TOKEN, ALLOWED_TG_IDS

from torrent_manager import TransmissionClient, transmission_error, MonitorOrchestrator, PBSearcher
from tg_bot import TgBotRunner


PERIOD_SECONDS = 60 * 60 * 8

torrent_searcher = PBSearcher()
monitors_orchestrator = MonitorOrchestrator()

try:
    transmission = TransmissionClient(TRANSMISSION_HOST)
except transmission_error.TransmissionConnectError:
    raise "can't connect to the host"

users_whitelist = [int(uid) for uid in ALLOWED_TG_IDS.split(",")]
admin_tgid = users_whitelist[0]
tg_client = ApplicationBuilder().token(TG_BOT_TOKEN).build()

runner = TgBotRunner(tg_client=tg_client,
                     torrent_client=transmission,
                     torrent_searcher=torrent_searcher,
                     monitors_orchestrator=monitors_orchestrator,
                     tg_user_whitelist=users_whitelist)


def run_search_jobs_on_timer(timer_seconds):
    search_results = runner.download_new_finds(admin_tgid)
    sleep(5 if search_results else timer_seconds)
    run_search_jobs_on_timer(timer_seconds)


def bot_poll():
    runner.tg_client.run_polling()


if __name__ == '__main__':
    [process.start() for process in
     (Process(target=run_search_jobs_on_timer, args=(PERIOD_SECONDS,)),
      Process(target=bot_poll))]
