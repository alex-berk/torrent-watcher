import requests
import json
from dataclasses import dataclass
from uuid import uuid4
from logger import logger


@dataclass
class TorrentDetails:
    name: str
    link: str
    size_gb: float
    seeds: int
    status: str
    info_hash: str

# TODO: add an ABC class for monitor with look() abstr method, make general class not aware of data provider


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

    def __init__(self, default_query: str = "", uuid: str = "") -> None:
        self.default_query = default_query
        self.monitor_type = "movie"
        self.uuid = uuid or str(uuid4())

    def __repr__(self):
        return f"PBSearcher(default_query={self.default_query}, uuid={self.uuid})"

    def __str__(self) -> str:
        return f"(M) / {self.default_query}"

    def to_dict(self) -> dict:
        return {"monitor_type": self.monitor_type, "default_query": self.default_query, "uuid": self.uuid}

    @classmethod
    def generate_magnet_link(cls, torrent_details: TorrentDetails) -> str:
        trackers_list_formatted = "&tr=".join([""] + cls._trackers_list)
        link = f"magnet:?xt=urn:btih:{torrent_details.info_hash}&dn=\
            {torrent_details.name}{trackers_list_formatted}"
        return link

    def search_torrent(self, query: str = "") -> list[TorrentDetails]:
        if not query:
            query = self.default_query
        try:
            r = requests.get(self._search_host, params={"q": query}, timeout=1)
        except requests.exceptions.ReadTimeout:
            logger.warning("timeout waiting response from external host", query=query)
            return []
        if (status_code := r.status_code) != 200:
            logger.warning("error from external host", query=query, status_code=status_code)
            return []
        search_results = json.loads(r.text)
        logger.debug("search_torrent ran", query=query, results_len=len(search_results))
        if len(search_results) == 1 and \
                search_results[0]["name"] == "No results returned":
            return []
        search_results_formatted = (TorrentDetails(
            name=result["name"],
            link=self._details_page_prefix + result["id"],
            size_gb=int(result["size"]) / 8**10,
            seeds=int(result["seeders"]),
            status=result["status"],
            info_hash=result["info_hash"]
        ) for result in search_results)
        search_results_formatted = sorted(
            search_results_formatted, key=lambda x: x.seeds, reverse=True)
        return search_results_formatted

    def look(self) -> TorrentDetails | None:
        logger.info(f"Monitor running: {self}", **self.to_dict())
        if result := self.search_torrent(self.default_query):
            logger.success(f"Monitor {self} found results", **self.to_dict())
            return result[0]
        logger.debug(f"Monitor {self} didn't find any results", **self.to_dict())


class PBMonitor(PBSearcher):
    def __init__(self, show_name: str, season_number: int, episode_number: int,
                 uuid: str = "", size_limit_gb: float = 0, only_vips=False):
        self.monitor_type = "show"
        self.show_name = show_name
        self.season_number = season_number
        self.episode_number = episode_number
        self.size_limit_gb = size_limit_gb
        self.only_vips = only_vips
        self.whitelisted_statuses = (
            "vip",) if self.only_vips else ("vip", "trusted")
        self.uuid = uuid or str(uuid4())

    def __repr__(self):
        fields_str = ", ".join((f"{key}={val}" for key, val in self.to_dict().items()
                                if key != "monitor_type"))
        return f"PBMonitor({fields_str})"

    def __str__(self) -> str:
        items = ["(S)", self.default_query]
        if self.size_limit_gb:
            items += [f"<={self.size_limit_gb}Gb"]
        return " / ".join(items)

    def to_dict(self) -> dict:
        fields = {
            "show_name": self.show_name,
            "season_number": self.season_number,
            "episode_number": self.episode_number,
            "uuid": self.uuid,
            "monitor_type": self.monitor_type
        }
        for optional_field_key, optional_field_val in (("size_limit_gb", self.size_limit_gb),
                                                       ("only_vips", self.only_vips),
                                                       ("whitelisted_statuses", self.whitelisted_statuses)):
            if optional_field_val:
                fields[optional_field_key] = optional_field_val

        return fields

    @property
    def default_query(self) -> str:
        return f"{self.show_name} s{self.season_number:02d}e{self.episode_number:02d}"

    def _search_episode(self) -> list[TorrentDetails]:
        search_query = self.default_query
        return self.search_torrent(search_query)

    def _find_new_episode(self) -> TorrentDetails | None:
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
            logger.success(f"Monitor {self}: found new episode", **self.to_dict())
            self.episode_number += 1
            return new_episode
        except StopIteration:
            return

    def look(self) -> TorrentDetails | None:
        logger.info(f"Monitor running: {self}", **self.to_dict())
        return self._find_new_episode()
