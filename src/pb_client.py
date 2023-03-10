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

    def __init__(self, default_query=None) -> None:
        self.default_query = default_query

    def __repr__(self) -> str:
        return f"(M) / {self.default_query}"

    @classmethod
    def generate_magnet_link(cls, torrent_details: TorrentDetails) -> str:
        trackers_list_formatted = "&tr=".join([""] + cls._trackers_list)
        link = f"magnet:?xt=urn:btih:{torrent_details.info_hash}&dn={torrent_details.name}{trackers_list_formatted}"
        return link

    def search_torrent(self, query: str) -> list[TorrentDetails]:
        r = requests.get(self._search_host, params={"q": query})
        search_results = json.loads(r.text)
        if len(search_results) == 1 and search_results[0]["name"] == "No results returned":
            return []
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

    def look(self):
        print(f"Monitor running: {self}")
        try:
            return self.search_torrent(self.default_query)[0]
        except IndexError:
            return


class PBMonitor(PBSearcher):
    def __init__(self, show_name: str, season_number: int, episode_number: int, size_limit_gb: int = None, only_vips=False):
        self.show_name = show_name
        self.season_number = season_number
        self.episode_number = episode_number
        self.size_limit_gb = size_limit_gb
        self.only_vips = only_vips

        self.whitelisted_statuses = (
            "vip",) if self.only_vips else ("vip", "trusted")

    def __repr__(self) -> str:
        items = ["(S)", self._generate_search_query()]
        if self.size_limit_gb:
            items += [f"<={self.size_limit_gb}Gb"]
        return " / ".join(items)

    def _generate_search_query(self) -> str:
        return f"{self.show_name} s{self.season_number:02d}e{self.episode_number:02d}"

    def _search_episode(self) -> tuple[TorrentDetails]:
        search_query = self._generate_search_query()
        return self.search_torrent(search_query)

    def find_new_episode(self):
        available_downloads = self._search_episode()
        if not available_downloads:
            return
        if self.size_limit_gb:
            available_downloads = filter(
                lambda x: x.size_gb <= self.size_limit_gb, available_downloads)
        available_downloads = filter(
            lambda x: x.status in self.whitelisted_statuses, available_downloads)
        try:
            new_episode = next(available_downloads)
            print(f"Monitor {self}: found new episode")
            self.episode_number += 1
            return new_episode
        except StopIteration:
            return

    def look(self):
        print(f"Monitor running: {self}")
        return self.find_new_episode()


if __name__ == "__main__":
    s = PBSearcher()
    results = s.search_torrent("akira")
    [print(result) for result in results[:10]]

    w = PBMonitor("chainsaw man 1080p", 1, 5, 4)
    new_ep = w.find_new_episode()
    print(new_ep)
