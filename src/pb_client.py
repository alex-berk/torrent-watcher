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
        try:
            return self.search_torrent(self.default_query)[0]
        except IndexError:
            return


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
        if not available_downloads:
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

    def look(self):
        return self.find_new_episode()


@dataclass
class MonitorSetting:
    owner_id: int
    searcher: PBSearcher or PBWatcher
    silent: bool = True


class MonitorOrchestrator:
    def __init__(self, monitor_settings_path="./monitor_settings.json") -> None:
        self._monitor_settings_path = monitor_settings_path
        self._settings: list[MonitorSetting] = []
        self._load_monitor_settings()

    def _load_monitor_settings(self) -> None:
        with open(self._monitor_settings_path, "r") as f:
            settings = json.load(f)
            for setting in settings:
                if setting.get("is_serial", True):
                    self._settings.append(
                        MonitorSetting(
                            owner_id=setting["owner_id"],
                            silent=setting.get("silent", True),
                            searcher=PBWatcher(
                                show_name=setting["query"],
                                season_number=setting["season"],
                                num_episodes_skip=setting["episodes_done"],
                                size_limit_gb=setting["size_limit"],
                            )
                        )
                    )
                else:
                    self._settings.append(
                        MonitorSetting(
                            owner_id=setting["owner_id"],
                            silent=setting.get("silent", True),
                            searcher=PBSearcher(
                                default_query=setting["query"]
                            )
                        )
                    )

    def _save_settings(self):
        settings_json = []
        for setting in self._settings:
            setting_obj = {
                "owner_id": setting.owner_id,
                "silent": setting.silent,
            }
            if type(setting.searcher) == PBSearcher:
                setting_obj["query"] = setting.searcher.default_query
                setting_obj["is_serial"] = False
            else:
                setting_obj["query"] = setting.searcher.show_name
                setting_obj["is_serial"] = True
                setting_obj["season"] = setting.searcher.season_number
                setting_obj["episodes_done"] = setting.searcher.num_episodes_skip
                setting_obj["size_limit"] = setting.searcher.size_limit_gb

            settings_json.append(setting_obj)
        with open(self._monitor_settings_path, 'w') as f:
            json.dump(settings_json, f, indent=2)

    def add_monitor_job(self, setting: MonitorSetting) -> None:
        self._settings.append(setting)
        self._save_settings()

    def run_search_jobs(self) -> filter:
        jobs = [(job.owner_id, job.searcher.look())
                for job in self._settings]
        jobs_with_results = filter(lambda x: x[1], jobs)
        return jobs_with_results


if __name__ == "__main__":
    # s = PBSearcher()
    # results = s.search_torrent("akira")
    # [print(result) for result in results[:10]]

    # w = PBWatcher("chainsaw man 1080p", 1, 5, 4)
    # new_ep = w.find_new_episode()
    # print(new_ep)

    o = MonitorOrchestrator()
    # for result in o._settings:
    #     print(result)

    # o.add_monitor_job(MonitorSetting(
    #     87794324, PBSearcher("avatar 2022"), False))

    for job in o.run_search_jobs():
        print(job)