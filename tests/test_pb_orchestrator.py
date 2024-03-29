import pytest
import os
import json
from torrent_manager import MonitorOrchestrator, MonitorSetting, PBSearcher, PBMonitor, JobResult

jobs = [
    {
        "owner_id": 1111111,
        "silent": False,
        "name": "the last of us",
        "monitor_type": "show",
        "season": 1,
        "episode": 10,
        "size_limit": 0,
        "uuid": "AA45815E-3E20-4132-BCE6-331F6C9C42D3"
    },
    {
        "owner_id": 1111111,
        "silent": True,
        "name": "chainsaw man",
        "monitor_type": "show",
        "season": 2,
        "episode": 1,
        "size_limit": 3,
        "uuid": "8C7C1197-1EB3-451F-B4F5-CC906560387E"
    },
    {
        "owner_id": 1111111,
        "silent": True,
        "name": "the matrix",
        "monitor_type": "movie",
        "uuid": "D995C8CC-4B2F-4598-B024-7321F4C3A8EF"
    }
]


def read_settings_file() -> dict:
    with open("settings.json", "r") as file:
        saved_settings = json.load(file)
    return saved_settings


class TestMonitorOrchestrator:
    def setup_method(self, method):
        self.orchestrator = MonitorOrchestrator("settings.json")
        [self.orchestrator.add_monitor_job_from_dict(job, False) for job in jobs]
        self.owner_id = 1111111
        self.loaded_monitors = self.orchestrator.get_user_monitors(self.owner_id)

    def teardown_method(self, method):
        os.remove("settings.json")

    def test_job_from_dict(self):
        assert len(self.loaded_monitors) == 3
        assert self.loaded_monitors[0].searcher.default_query == "the last of us s01e10"
        assert self.loaded_monitors[-1].searcher.default_query == "the matrix"

    def test_job_from_dict_invalid_monitor_type(self):
        with pytest.raises(ValueError):
            self.orchestrator.add_monitor_job_from_dict({
                "monitor_type": "invalid_monitor_type"
            })

    def test_search_results(self, mock_response):
        jobs_results = self.orchestrator.run_search_job_iteration(owner_id=self.owner_id)
        jobs_results_list = list(jobs_results)
        torrent_names = [job.result.name for job in jobs_results_list]
        assert torrent_names == ["Torrent 3", "Torrent 1", "Torrent 3"]
        assert len(jobs_results_list) == 3

    def test_run_search_jobs(self, mock_response_iteration):
        jobs_results = self.orchestrator.run_search_jobs(owner_id=self.owner_id)
        jobs_results_list = list(jobs_results)

        assert len(jobs_results_list) == 5
        expected_queries = ['the last of us s01e10', 'chainsaw man s02e01', 'the matrix',
                            'the last of us s01e11', 'chainsaw man s02e02', 'the last of us s01e12',
                            'chainsaw man s02e03']
        assert mock_response_iteration.queries == expected_queries

    def test_search_results_empty(self, mock_response_empty):
        assert len(self.loaded_monitors) == 3
        assert self.loaded_monitors[0].searcher.episode_number == 10

        jobs_results = self.orchestrator.run_search_job_iteration(owner_id=self.owner_id)
        jobs_results_list = list(jobs_results)
        assert len(jobs_results_list) == 0
        assert len(self.loaded_monitors) == 3  # without search results JobSetting didn't change
        assert self.loaded_monitors[0].searcher.episode_number == 10

    def test_search_results_error(self, mock_response_404):
        jobs_results = self.orchestrator.run_search_job_iteration(owner_id=self.owner_id)
        jobs_results_list = list(jobs_results)
        assert len(jobs_results_list) == 0

    def test_episode_update(self, mock_response):
        assert len(self.loaded_monitors) == 3
        assert self.loaded_monitors[0].searcher.episode_number == 10

        self.orchestrator.run_search_job_iteration(owner_id=self.owner_id)
        self.loaded_monitors = self.orchestrator.get_user_monitors(self.owner_id)
        assert len(self.loaded_monitors) == 2
        assert self.loaded_monitors[0].searcher.episode_number == 11

    def test_save_settings(self, mock_response):
        saved_settings = read_settings_file()
        assert len(saved_settings) == 3
        assert saved_settings[0]["episode"] == 10

        self.orchestrator.run_search_job_iteration(owner_id=self.owner_id)
        saved_settings = read_settings_file()
        assert len(saved_settings) == 2
        assert saved_settings[0]["episode"] == 11

    def test_add_job(self):
        result = self.orchestrator.add_monitor_job(MonitorSetting(self.owner_id, PBSearcher("New Job")), False)
        assert len(result) == 0

        monitor_list = self.orchestrator.get_user_monitors(self.owner_id)
        assert len(monitor_list) == 4
        assert monitor_list[-1].searcher.default_query == "New Job"
        saved_settings = read_settings_file()
        assert saved_settings[-1]["name"] == "New Job"

    def test_add_job_autostart(self, mock_response):
        result = self.orchestrator.add_monitor_job(MonitorSetting(self.owner_id, PBSearcher("New Job")), True)
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], JobResult)
        assert mock_response.calls == 1

    def test_add_job_autostart_multiple_results(self, mock_response_iteration):
        result = self.orchestrator.add_monitor_job(MonitorSetting(self.owner_id, PBMonitor("New Job", 1, 1)), True)
        assert isinstance(result, list)
        assert len(result) == 5
        assert isinstance(result[0], JobResult)
        assert mock_response_iteration.calls == 6  # check that only this job was using search

    def test_remove_job(self):
        self.orchestrator.delete_monitor_job(self.loaded_monitors[1])
        self.loaded_monitors = self.orchestrator.get_user_monitors(self.owner_id)
        assert len(self.loaded_monitors) == 2
        saved_settings = read_settings_file()
        assert len(saved_settings) == 2
