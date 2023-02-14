# from concurrent.futures import ThreadPoolExecutor
# import concurrent.futures
from multiprocessing import Process
from time import sleep
from pb_orchestrator import MonitorOrchestrator, PBMonitor
from tg_bot import runner


monitors = MonitorOrchestrator()


def run_search_jobs_on_timer(timer_seconds):
    search_results = monitors.run_search_jobs()
    print(search_results)
    if search_results:
        sleep(5)
        run_search_jobs_on_timer(timer_seconds)
    else:
        sleep(timer_seconds)
        run_search_jobs_on_timer(timer_seconds)


def bot_poll():
    runner.tg_client.run_polling()


if __name__ == '__main__':
    [p.start() for p in
     (Process(target=run_search_jobs_on_timer, args=(15,)),
      Process(target=bot_poll))]
