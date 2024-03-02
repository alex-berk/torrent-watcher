from typing import Iterable
import os
from dataclasses import dataclass
import json
from torrent_manager.pb_client import PBSearcher, PBMonitor, TorrentDetails
from logger import logger
import asyncio


@dataclass
class MonitorSetting:
    owner_id: int
    searcher: PBSearcher | PBMonitor  # TODO: definitely add interface
    silent: bool = True


@dataclass
class JobResult:
    result: TorrentDetails
    job_settings: MonitorSetting

    @property
    def magnet_link(self) -> str:
        return self.job_settings.searcher.generate_magnet_link(self.result)


class MonitorOrchestrator:
    def __init__(self, monitor_settings_path: str = "") -> None:
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
                        uuid=setting.get("uuid", "")
                    )
                )
            case "movie":
                return MonitorSetting(
                    owner_id=setting["owner_id"],
                    silent=setting.get("silent", True),
                    searcher=PBSearcher(
                        default_query=setting["name"],
                        uuid=setting.get("uuid", "")
                    )
                )
            case provided_type:
                raise ValueError(f"dont recognize the type {provided_type} of the monitor")

    @staticmethod
    def _setting_to_dict(setting: MonitorSetting) -> dict:
        setting_obj = {
            "owner_id": setting.owner_id,
            "silent": setting.silent,
            "monitor_type": setting.searcher.monitor_type,
            "uuid": setting.searcher.uuid
        }
        match setting.searcher.monitor_type:
            case "movie":
                setting_obj["name"] = setting.searcher.default_query
            case "show":
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

    async def add_monitor_job(self, setting: MonitorSetting, run_after_init) -> list[JobResult]:
        self._settings.append(setting)
        self._save_settings()
        # TODO: refactor self._settings into subscribable, so this function wouldn't have to return anything
        if run_after_init:
            return await self.run_search_jobs([setting])
        return []

    def delete_monitor_job(self, job) -> None:
        self._settings.remove(job)
        self._save_settings()

    async def add_monitor_job_from_dict(self, settings_dict: dict,
                                  run_after_init: bool = True) -> list[JobResult]:
        settings = self._dict_to_setting(settings_dict)
        return await self.add_monitor_job(settings, run_after_init)

    def get_jobs_by_owner_id(self, owner_id) -> Iterable[MonitorSetting]:
        self._update_monitor_settings_from_json()
        jobs_filtered = (s for s in self._settings
                         if s.owner_id == owner_id)
        return jobs_filtered

    async def run_search_job_iteration(self, jobs_to_run: Iterable[MonitorSetting] | None = None, owner_id=None) \
            -> list[JobResult]:
        eligible_jobs = jobs_to_run or self.get_jobs_by_owner_id(owner_id)
        jobs_promises = ((asyncio.create_task(job.searcher.look()), job) for job in eligible_jobs)
        jobs = await asyncio.gather(*[job.searcher.look() for job in eligible_jobs])
        jobs_with_results = [JobResult(result, job)
                             for job in eligible_jobs
                             if (result := await asyncio.gather(job.searcher.look()))]
        done_jobs = (j for j in jobs_with_results
                     if j.job_settings.searcher.monitor_type == "movie")
        for job in done_jobs:
            self.delete_monitor_job(job.job_settings)
        self._save_settings()
        return jobs_with_results

    async def run_search_jobs(self, jobs_to_run: Iterable[MonitorSetting] | None = None,
                        owner_id: int = 0) -> list[JobResult]:
        logger.debug("running search jobs")
        jobs_with_results_all: list[JobResult] = []
        if jobs_to_run:
            iteration_result = await self.run_search_job_iteration(jobs_to_run)
        else:
            iteration_result = await self.run_search_job_iteration(owner_id=owner_id)
        while iteration_result:
            jobs_with_results_all.extend(iteration_result)
            jobs_for_next_iteration = (job.job_settings for job in iteration_result
                                       if job.job_settings.searcher.monitor_type == "show")
            iteration_result = await self.run_search_job_iteration(jobs_for_next_iteration)
        return jobs_with_results_all
