from transmission_rpc import Client, Torrent, error as transmission_error
from config import MEDIA_DOWNLOAD_PATH, REGULAR_DOWNLOAD_PATH, TRANSMISSION_HOST
from unittest.mock import patch, Mock
from os import path
from datetime import datetime


class TransmissionClient(Client):
    def __init__(self, host, download_paths: dict,) -> None:
        super().__init__(host=host)
        self.download_paths = download_paths

    _pending_statuses = ['downloading',
                         'download pending', 'check pending', 'checking',]

    def _filter_fresh_torrents(self, torrent: Torrent) -> bool:
        torrent_date = torrent.added_date.replace(tzinfo=None)
        current_date = datetime.today()
        torrent_age_days = (current_date - torrent_date).days
        return torrent_age_days <= 3 or torrent.status in self._pending_statuses

    def add_download(self, magnet_link: str, download_type: str) -> Torrent | None:
        download_dir = DOWNLOAD_PATHS[download_type]
        try:
            download = self.add_torrent(magnet_link, download_dir=download_dir)
        except transmission_error.TransmissionError:
            return
        return download

    def download_from_file(self, filename, download_type) -> Torrent:
        with open(filename, "rb") as f:
            return self.add_download(f, download_type)

    def find_torrent(self, torrent_name: str) -> Torrent:
        torrents_list = self.get_torrents()
        result = filter(lambda t: t.name == torrent_name, torrents_list)
        try:
            return next(result)
        except StopIteration:
            return

    def get_recent_downloads(self) -> list[Torrent]:
        torrents = self.get_torrents()
        pending_torrents = filter(
            self._filter_fresh_torrents, torrents)
        return tuple(pending_torrents)


# TODO: ?move inside the class, expose for easy export
DOWNLOAD_PATHS = {
    "movie": path.join(MEDIA_DOWNLOAD_PATH, "movies"),
    "show": path.join(MEDIA_DOWNLOAD_PATH, "shows"),
    "video": path.join(MEDIA_DOWNLOAD_PATH, "videos"),
    "other": REGULAR_DOWNLOAD_PATH,
}

if __name__ == "__main__":
    try:
        c = TransmissionClient(TRANSMISSION_HOST, DOWNLOAD_PATHS)
        torrents = c.get_recent_downloads()
        for torrent in torrents:
            print(torrent)
    except transmission_error.TransmissionConnectError:
        raise "can't connect to the host"
