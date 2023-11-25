from dotenv import load_dotenv
from os import getenv


load_dotenv()

MEDIA_DOWNLOAD_PATH = getenv("MEDIA_DOWNLOAD_PATH")
REGULAR_DOWNLOAD_PATH = getenv("REGULAR_DOWNLOAD_PATH")
TRANSMISSION_HOST = getenv("TRANSMISSION_HOST")
TG_BOT_TOKEN = getenv("TG_BOT_TOKEN")
ALLOWED_TG_IDS = getenv("ALLOWED_TG_IDS")
