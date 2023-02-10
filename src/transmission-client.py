from transmission_rpc import Client, Torrent, error
import os
from dotenv import load_dotenv
load_dotenv()


class TransmissionClient(Client):
    def __init__(self, host, download_paths: dict,) -> None:
        super().__init__(host=host)
        self.download_paths = download_paths

    def add_download(self, magnet_link: str, download_type: str) -> Torrent:
        download_dir = download_paths[download_type]
        return self.add_torrent(magnet_link, download_dir=download_dir)

    def find_torrent(self, torrent_name: str) -> Torrent:
        torrents_list = self.get_torrents()
        result = filter(lambda t: t.name == torrent_name, torrents_list)
        try:
            return next(result)
        except StopIteration:
            return


download_paths = {
    "movie": os.path.join(os.getenv("MEDIA_DOWNLOAD_PATH"), "movies"),
    "show": os.path.join(os.getenv("MEDIA_DOWNLOAD_PATH"), "shows"),
    "video": os.path.join(os.getenv("MEDIA_DOWNLOAD_PATH"), "videos"),
    "other": os.getenv("REGULAR_DOWNLOAD_PATH"),
}

if __name__ == "__main__":
    try:
        c = TransmissionClient(os.getenv("TRANSMISSION_HOST"), download_paths)
    except error.TransmissionConnectError:
        raise "can't connect to the host"
