from pb_client import PBSearcher, PBMonitor, TorrentDetails
from os import path
from dataclasses import dataclass
import json


@dataclass
class MonitorSetting:
    owner_id: int
    searcher: PBSearcher or PBMonitor
    silent: bool = True


@dataclass
class JobResult:
    result: TorrentDetails
    job_settings: MonitorSetting


class MonitorOrchestrator:
    def __init__(self, monitor_settings_path="./monitor_settings.json") -> None:
        self._monitor_settings_path = monitor_settings_path
        self._settings: list[MonitorSetting] = []
        self.update_monitor_settings_from_json()

    def get_user_monitors(self, uid: int):  # -> filter[MonitorSetting]:
        return filter(lambda x: x.owner_id == uid, self._settings)

    def update_monitor_settings_from_json(self) -> None:
        if not path.exists(self._monitor_settings_path):
            open(self._monitor_settings_path, "w")
        with open(self._monitor_settings_path, "r") as f:
            try:
                settings = json.load(f)
            except json.decoder.JSONDecodeError:
                settings = []
            self._settings = list(map(self._dict_to_setting, settings))

    @staticmethod
    def _dict_to_setting(setting) -> MonitorSetting:
        if setting.get("is_serial", True):
            return MonitorSetting(
                owner_id=setting["owner_id"],
                silent=setting.get("silent", True),
                searcher=PBMonitor(
                    show_name=setting["query"],
                    season_number=setting["season"],
                    num_episodes_skip=setting["episodes_done"],
                    size_limit_gb=setting["size_limit"],
                )
            )
        return MonitorSetting(
            owner_id=setting["owner_id"],
            silent=setting.get("silent", True),
            searcher=PBSearcher(
                default_query=setting["query"]
            )
        )

    @staticmethod
    def _setting_to_dict(setting) -> dict:
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

        return setting_obj

    def _save_settings(self) -> None:
        with open(self._monitor_settings_path, 'w') as f:
            settings_json = list(map(self._setting_to_dict, self._settings))
            json.dump(settings_json, f, indent=2)

    def add_monitor_job(self, setting: MonitorSetting) -> None:
        self._settings.append(setting)
        self._save_settings()

    def delete_monitor_job(self, job) -> None:
        self._settings.remove(job)
        self._save_settings()

    def add_monitor_job_from_dict(self, settings_dict: dict) -> None:
        settings = self._dict_to_setting(settings_dict)
        self.add_monitor_job(settings)

    def run_search_jobs(self) -> list[JobResult]:
        self.update_monitor_settings_from_json()
        jobs = [JobResult(job.searcher.look(), job)
                for job in self._settings]
        jobs_with_results = list(filter(lambda j: j.result, jobs))
        done_jobs = filter(lambda j: type(j.job_settings.searcher)
                           == PBSearcher, jobs_with_results)
        [self.delete_monitor_job(job.job_settings) for job in done_jobs]
        self._save_settings()
        return jobs_with_results


if __name__ == "__main__":
    o = MonitorOrchestrator()

    # o.add_monitor_job(MonitorSetting(
    #     123, PBMonitor("one punch man", 1, 2, 3), False))
    # o.add_monitor_job_from_dict({
    #     "owner_id": 123,
    #     "silent": False,
    #     "query": "avatar 2022",
    #     "is_serial": False
    # })

    for job in o.run_search_jobs():
        print(job)

    print()
    for result in o._settings:
        print(result)
