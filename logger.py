import sys
from loguru import logger
from logtail import LogtailHandler
from config import LOGTAIL_TOKEN


logtail_handler = LogtailHandler(source_token=LOGTAIL_TOKEN)

logger.remove(0)

logger.add(sys.stdout, colorize=True, format="<green>{time}</green> <level>{message}</level>", level="INFO")

logger.add(
    logtail_handler,
    format="{message}",
    level="INFO",
    backtrace=False,
    diagnose=False
)

logger.add(
    "logs/{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="1 month"
)
