from typing import Generator, Iterable
from torrent_manager.pb_client import PBSearcher, PBMonitor, TorrentDetails
import os
from dataclasses import dataclass
import json


@dataclass
class MonitorSetting:
    owner_id: int
    searcher: PBSearcher | PBMonitor
    silent: bool = True


@dataclass
class JobResult:
    result: TorrentDetails
    job_settings: MonitorSetting


class MonitorOrchestrator:
    def __init__(self, monitor_settings_path=None) -> None:
        self._monitor_settings_path = monitor_settings_path or \
            os.path.join(os.getcwd(), "data", "monitor_settings.json")
        self._settings: list[MonitorSetting] = []
        self._update_monitor_settings_from_json()

    def get_user_monitors(self, uid: int) -> list[MonitorSetting]:
        return [monitor for monitor in self._settings if str(monitor.owner_id) == str(uid)]

    def _update_monitor_settings_from_json(self) -> None:
        if not os.path.exists(self._monitor_settings_path):
            with open(self._monitor_settings_path, "w") as f:
                f.write("[]")

        with open(self._monitor_settings_path, "r") as f:
            settings = json.load(f)
            self._settings = [self._dict_to_setting(setting) for setting in settings]

    @staticmethod
    def _dict_to_setting(setting: dict) -> MonitorSetting:
        match setting["monitor_type"]:
            case "show":
                return MonitorSetting(
                    owner_id=setting["owner_id"],
                    silent=setting.get("silent", True),
                    searcher=PBMonitor(
                        show_name=setting["name"],
                        season_number=setting["season"],
                        episode_number=setting["episode"],
                        size_limit_gb=setting.get("size_limit", 0),
                        uuid=setting.get("uuid")
                    )
                )
            case "movie":
                return MonitorSetting(
                    owner_id=setting["owner_id"],
                    silent=setting.get("silent", True),
                    searcher=PBSearcher(
                        default_query=setting["name"],
                        uuid=setting.get("uuid")
                    )
                )

    @staticmethod
    def _setting_to_dict(setting: MonitorSetting) -> dict:
        setting_obj = {
            "owner_id": setting.owner_id,
            "silent": setting.silent,
            "monitor_type": setting.searcher.monitor_type,
            "uuid": setting.searcher.uuid
        }
        if setting.searcher.monitor_type == "movie":
            setting_obj["name"] = setting.searcher.default_query
        else:
            setting_obj["name"] = setting.searcher.show_name
            setting_obj["season"] = setting.searcher.season_number
            setting_obj["episode"] = setting.searcher.episode_number
            setting_obj["size_limit"] = setting.searcher.size_limit_gb

        return setting_obj

    def _save_settings(self) -> None:
        with open(self._monitor_settings_path, 'w') as f:
            settings_json = list(map(self._setting_to_dict, self._settings))
            json.dump(settings_json, f, indent=2)

    def get_monitor_by_uuid(self, uuid) -> MonitorSetting | None:
        job_with_uuid = filter(lambda j: j.searcher.uuid == uuid, self._settings)
        try:
            return next(job_with_uuid)
        except StopIteration:
            return

    def add_monitor_job(self, setting: MonitorSetting) -> None:
        self._settings.append(setting)
        self._save_settings()

    def delete_monitor_job(self, job) -> None:
        self._settings.remove(job)
        self._save_settings()

    def add_monitor_job_from_dict(self, settings_dict: dict) -> None:
        settings = self._dict_to_setting(settings_dict)
        self.add_monitor_job(settings)

    def get_jobs_by_owner_id(self, owner_id) -> Generator[MonitorSetting, None, None]:
        self._update_monitor_settings_from_json()
        jobs_filtered = filter(lambda x: x.owner_id == owner_id,
                               self._settings)
        return jobs_filtered

    def run_search_job_iteration(self, owner_id, jobs_to_run: Iterable[MonitorSetting] = None) \
            -> Generator[JobResult, None, None]:
        eligible_jobs = jobs_to_run or self.get_jobs_by_owner_id(owner_id)
        jobs = [JobResult(job.searcher.look(), job)
                for job in eligible_jobs]
        jobs_with_results = (j for j in jobs if j.result)
        done_jobs = (j for j in jobs
                     if j.job_settings.searcher.monitor_type == "movie")
        [self.delete_monitor_job(job.job_settings) for job in done_jobs]
        self._save_settings()
        return jobs_with_results

    def run_search_jobs(self, owner_id: str = None) -> list[JobResult]:
        jobs_with_results_all: list[JobResult] = []
        iteration_result = self.run_search_job_iteration(owner_id)
        while iteration_result:
            jobs_with_results_all.extend(iteration_result)
            jobs_for_next_iteration = (job for job in iteration_result
                                       if job.job_settings.searcher.type == "show")
            iteration_result = self.run_search_job_iteration(owner_id, jobs_for_next_iteration)
        return jobs_with_results_all
