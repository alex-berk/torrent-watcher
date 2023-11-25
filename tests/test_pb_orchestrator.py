import os
import json
from torrent_manager import MonitorOrchestrator, MonitorSetting, PBSearcher

jobs = [
    {
        "owner_id": 1111111,
        "silent": False,
        "query": "the last of us",
        "is_serial": True,
        "season": 1,
        "episode_number": 10,
        "size_limit": 0
    },
    {
        "owner_id": 1111111,
        "silent": True,
        "query": "chainsaw man",
        "is_serial": True,
        "season": 2,
        "episode_number": 1,
        "size_limit": 3
    },
    {
        "owner_id": 1111111,
        "silent": True,
        "query": "the matrix",
        "is_serial": False
    }
]


def read_settings_file() -> dict:
    with open("settings.json", "r") as file:
        saved_settings = json.load(file)
    return saved_settings


class TestMonitorOrchestrator:
    def setup_method(self, method):
        self.orchestrator = MonitorOrchestrator("settings.json")
        [self.orchestrator.add_monitor_job_from_dict(job) for job in jobs]
        self.owner_id = 1111111

    def teardown_method(self, method):
        os.remove("settings.json")

    def test_init(self):
        loaded_monitors = self.orchestrator.get_user_monitors(self.owner_id)
        assert len(loaded_monitors) == 3
        assert loaded_monitors[0].searcher.default_query == "the last of us s01e10"
        assert loaded_monitors[-1].searcher.default_query == "the matrix"

    def test_episode_update(self, mock_response):
        loaded_monitors = self.orchestrator.get_user_monitors(self.owner_id)
        assert len(loaded_monitors) == 3
        assert loaded_monitors[0].searcher.episode_number == 10

        self.orchestrator.run_search_job_iteration(self.owner_id)
        loaded_monitors = self.orchestrator.get_user_monitors(self.owner_id)
        assert len(loaded_monitors) == 2
        assert loaded_monitors[0].searcher.episode_number == 11

    def test_save_settings(self, mock_response):
        saved_settings = read_settings_file()
        assert len(saved_settings) == 3
        assert saved_settings[0]["episode_number"] == 10

        self.orchestrator.run_search_job_iteration(self.owner_id)
        saved_settings = read_settings_file()
        assert len(saved_settings) == 2
        assert saved_settings[0]["episode_number"] == 11

    def test_add_job(self):
        self.orchestrator.add_monitor_job(MonitorSetting(self.owner_id, PBSearcher("New Job")))
        monitor_list = self.orchestrator.get_user_monitors(self.owner_id)
        assert len(monitor_list) == 4
        assert monitor_list[-1].searcher.default_query == "New Job"
        saved_settings = read_settings_file()
        assert saved_settings[-1]["query"] == "New Job"

    def test_remove_job(self):
        monitor_list = self.orchestrator.get_user_monitors(self.owner_id)

        self.orchestrator.delete_monitor_job(monitor_list[1])
        monitor_list = self.orchestrator.get_user_monitors(self.owner_id)
        assert len(monitor_list) == 2
        saved_settings = read_settings_file()
        assert len(saved_settings) == 2
