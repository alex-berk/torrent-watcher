from dotenv import load_dotenv
from os import getenv


load_dotenv()

MEDIA_DOWNLOAD_PATH: str = getenv("MEDIA_DOWNLOAD_PATH") or ""
REGULAR_DOWNLOAD_PATH: str = getenv("REGULAR_DOWNLOAD_PATH") or ""
TRANSMISSION_HOST: str = getenv("TRANSMISSION_HOST") or ""
TG_BOT_TOKEN: str = getenv("TG_BOT_TOKEN") or ""
ALLOWED_TG_IDS: str = getenv("ALLOWED_TG_IDS") or ""
