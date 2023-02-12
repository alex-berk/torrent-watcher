from transmission_rpc import Client, Torrent, error
import os
from dotenv import load_dotenv
from datetime import datetime
load_dotenv()


class TransmissionClient(Client):
    def __init__(self, host, download_paths: dict,) -> None:
        super().__init__(host=host)
        self.download_paths = download_paths

    _pending_statuses = ['downloading',
                         'download pending', 'check pending', 'checking',]

    def _filter_torrents_list(self, torrent: Torrent) -> bool:
        torrent_date = torrent.date_added.replace(tzinfo=None)
        current_date = datetime.today()
        torrent_age_days = (current_date - torrent_date).days
        return torrent_age_days <= 3 or torrent.status in self._pending_statuses

    def add_download(self, magnet_link: str, download_type: str) -> Torrent:
        download_dir = download_paths[download_type]
        return self.add_torrent(magnet_link, download_dir=download_dir)

    def download_from_file(self, filename, download_type):
        with open(filename, "rb") as f:
            self.add_download(f, download_type)

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
            self._filter_torrents_list, torrents)
        return tuple(pending_torrents)


download_paths = {
    "movie": os.path.join(os.getenv("MEDIA_DOWNLOAD_PATH"), "movies"),
    "show": os.path.join(os.getenv("MEDIA_DOWNLOAD_PATH"), "shows"),
    "video": os.path.join(os.getenv("MEDIA_DOWNLOAD_PATH"), "videos"),
    "other": os.getenv("REGULAR_DOWNLOAD_PATH"),
}

if __name__ == "__main__":
    try:
        c = TransmissionClient(os.getenv("TRANSMISSION_HOST"), download_paths)
        torrents = c.get_recent_downloads()
        # torrents = c.get_torrents()
        for torrent in torrents:
            print(torrent)
    except error.TransmissionConnectError:
        raise "can't connect to the host"
