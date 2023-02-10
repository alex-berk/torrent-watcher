import requests
import json
from dataclasses import dataclass


@dataclass
class TorrentDetails:
    name: str
    link: str
    size_gb: int
    seeds: int
    status: str
    info_hash: str


class PBSearcher:
    _search_host = "https://apibay.org/q.php"
    _details_page_prefix = "https://thepiratebay.org/description.php?id="
    _trackers_list = [
        "udp://tracker.coppersurfer.tk:6969/announce",
        "udp://tracker.openbittorrent.com:6969/announce",
        "udp://9.rarbg.to:2710/announce",
        "udp://9.rarbg.me:2780/announce",
        "udp://9.rarbg.to:2730/announce",
        "udp://tracker.opentrackr.org:1337",
        "http://p4p.arenabg.com:1337/announce",
        "udp://tracker.torrent.eu.org:451/announce",
        "udp://tracker.tiny-vps.com:6969/announce",
        "udp://open.stealth.si:80/announce",
    ]

    @classmethod
    def generate_magnet_link(cls, torrent_details: TorrentDetails) -> str:
        trackers_list_formatted = "&tr=".join([""] + cls._trackers_list)
        link = f"magnet:?xt=urn:btih:{torrent_details.info_hash}&dn={torrent_details.name}{trackers_list_formatted}"
        return link

    def search_torrent(self, query: str) -> list[TorrentDetails]:
        r = requests.get(self._search_host, params={"q": query})
        search_results = json.loads(r.text)
        search_results_formatted = [TorrentDetails(
            result["name"],
            self._details_page_prefix + result["id"],
            int(result["size"]) / 8**10,
            int(result["seeders"]),
            result["status"],
            result["info_hash"]
        ) for result in search_results]
        search_results_formatted = sorted(
            search_results_formatted, key=lambda x: x.seeds, reverse=True)
        return search_results_formatted


class PBWatcher(PBSearcher):
    def __init__(self, show_name: str, season_number: int, num_episodes_skip: int, size_limit_gb: int = None, only_vips=False):
        self.show_name = show_name
        self.season_number = season_number
        self.num_episodes_skip = num_episodes_skip
        self.size_limit_gb = size_limit_gb
        self.only_vips = only_vips

        self.episode_number = None
        self.whitelisted_statuses = (
            "vip",) if self.only_vips else ("vip", "trusted")

    def _generate_search_query(self) -> str:
        return f"{self.show_name} s{self.season_number:02d}e{self.episode_number:02d}"

    def _search_episode(self) -> tuple[TorrentDetails]:
        search_query = self._generate_search_query()
        return self.search_torrent(search_query)

    def find_new_episode(self):
        self.episode_number = self.num_episodes_skip + 1
        available_downloads = self._search_episode()
        if available_downloads[0].name == "No results returned":
            return
        if self.size_limit_gb:
            available_downloads = filter(
                lambda x: x.size_gb <= self.size_limit_gb, available_downloads)
        available_downloads = filter(
            lambda x: x.status in self.whitelisted_statuses, available_downloads)
        try:
            return next(available_downloads)
        except StopIteration:
            return



