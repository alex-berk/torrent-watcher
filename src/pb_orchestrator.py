from pb_client import PBSearcher, PBMonitor, TorrentDetails
import os
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
    def __init__(self, monitor_settings_path=os.path.join(os.getcwd(), "data", "monitor_settings.json")) -> None:
        self._monitor_settings_path = monitor_settings_path
        self._settings: list[MonitorSetting] = []
        self.update_monitor_settings_from_json()

    def get_user_monitors(self, uid: int) -> list[MonitorSetting]:
        return list(filter(lambda x: str(x.owner_id) == str(uid), self._settings))

    def update_monitor_settings_from_json(self) -> None:
        # TODO: refactor, make sure file closed after use, remove "except json.decoder.JSONDecodeError"
        if not os.path.exists(self._monitor_settings_path):
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
                    episode_number=setting["episode_number"],
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
            setting_obj["episode_number"] = setting.searcher.episode_number
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

    def get_jobs_by_owner_id(self, owner_id) -> filter:
        self.update_monitor_settings_from_json()
        jobs_filtered = filter(lambda x: x.owner_id ==
                               owner_id, self._settings)
        return jobs_filtered

    def run_search_job_iteration(self, owner_id) -> list[JobResult]:
        self.update_monitor_settings_from_json()
        eligible_jobs = self.get_jobs_by_owner_id(
            owner_id) if owner_id else self._settings
        jobs = [JobResult(job.searcher.look(), job)
                for job in eligible_jobs]
        jobs_with_results = list(filter(lambda j: j.result, jobs))
        done_jobs = filter(lambda j: type(j.job_settings.searcher)
                           == PBSearcher, jobs_with_results)
        [self.delete_monitor_job(job.job_settings) for job in done_jobs]
        self._save_settings()
        return jobs_with_results

    def run_search_jobs(self, owner_id=None) -> list[JobResult]:
        jobs_with_results_all: list[JobResult] = []
        iteration_result = self.run_search_job_iteration(owner_id)
        while iteration_result:
            jobs_with_results_all.extend(iteration_result)
            iteration_result = self.run_search_job_iteration(owner_id)
        return jobs_with_results_all


if __name__ == "__main__":
    o = MonitorOrchestrator()
