from torrent_manager.transmission_client import TransmissionClient
from config import TRANSMISSION_HOST


class SRMonitor:
    def __init__(self, name: str, torrent_file: str) -> None:
        self.name = name
        self.torrent_file = torrent_file
        self.torrent_client = TransmissionClient(TRANSMISSION_HOST)

    def refresh(self):
        self.torrent_client.download_from_file(self.torrent_file)

    def look(self):
        self.refresh()
