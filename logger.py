import sys
from loguru import logger
from logtail import LogtailHandler
from config import LOGTAIL_TOKEN


logtail_handler = LogtailHandler(source_token=LOGTAIL_TOKEN)

logger.remove(0)

logger.add(sys.stdout, colorize=True, format="<level>{time}</level> <green>{message}</green>", level="INFO")

logger.add(
    logtail_handler,
    format="{message}",
    level="DEBUG",
    backtrace=False,
    diagnose=False
)

logger.add(
    "logs/{time:YYYY-MM-DD}.log",
    rotation="0:00",
    retention="1 month",
    enqueue=True
)
