from loguru import logger
from logtail import LogtailHandler
from config import LOGTAIL_TOKEN


logtail_handler = LogtailHandler(source_token=LOGTAIL_TOKEN)

logger.add(
    logtail_handler,
    format="{message}",
    level="INFO",
    backtrace=False,
    diagnose=False
)
