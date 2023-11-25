import pytest
from torrent_manager import PBSearcher, PBMonitor
from torrent_manager.pb_client import requests
from dataclasses import dataclass
import json


@dataclass
class PBResponse:
    data: dict = None
    status_code: int = 200
    text: str = None

    def __post_init__(self):
        if self.data:
            self.text = json.dumps(self.data)


with open("tests/fixtures/pb_response_no_data.json", "r") as file:
    data = json.load(file)
    pb_response_no_results = PBResponse(data)

with open("tests/fixtures/pb_response.json", "r") as file:
    data = json.load(file)
    pb_response = PBResponse(data)


def generate_mock_get(response_type: str = "") -> (callable, dict):
    buffer = {"url": "", "query": "", "calls": 0}

    def mock_get(url, **kwargs):
        query = kwargs.get("params").get("q")
        buffer["url"] = url
        buffer["query"] = query
        buffer["calls"] += 1

        if response_type == "empty":
            return pb_response_no_results
        elif response_type == "404":
            return PBResponse(status_code=404)
        return pb_response

    return mock_get, buffer


@pytest.fixture
def mock_response(monkeypatch: pytest.MonkeyPatch):
    mock_get, buffer = generate_mock_get()
    monkeypatch.setattr(requests, "get", mock_get)
    return buffer


@pytest.fixture
def mock_response_empty(monkeypatch: pytest.MonkeyPatch):
    mock_get, buffer = generate_mock_get("empty")
    monkeypatch.setattr(requests, "get", mock_get)
    return buffer


@pytest.fixture
def mock_response_404(monkeypatch: pytest.MonkeyPatch):
    mock_get, buffer = generate_mock_get("404")
    monkeypatch.setattr(requests, "get", mock_get)
    return buffer


@pytest.fixture
def mock_timeout(monkeypatch: pytest.MonkeyPatch):
    def throw_timeout(*args, **kwargs):
        raise requests.exceptions.ReadTimeout
    monkeypatch.setattr(requests, "get", throw_timeout)


class TestPBSearcher:
    def setup_method(self, method):
        self.searcher = PBSearcher("akira")
        self.searcher_empty_results = PBSearcher("akira")

    def test_search_torrent_sorting(self, mock_response):
        results = self.searcher.search_torrent()
        torrent_names = [result.name for result in results]
        assert torrent_names == ["Torrent 3", "Torrent 1", "Torrent 2"]

    def test_search_torrent_no_results(self, mock_response_empty):
        results = self.searcher.search_torrent("non existing")
        assert results == []

    def test_search_torrent_http_error_handling(self, mock_response_404):
        assert self.searcher.search_torrent("its not working") == []

    def test_search_torrent_http_timeout(self, mock_timeout):
        results = self.searcher.search_torrent()
        assert results == []

    def test_look(self, mock_response):
        results = self.searcher.look()
        assert results

    def test_look_no_results(self, mock_response_empty):
        results = self.searcher_empty_results.look()
        assert results is None

    def test_look_http_timeout(self, mock_timeout):
        results = self.searcher.look()
        assert results is None


class TestPBMonitor:
    def setup_method(self, method):
        self.monitor = PBMonitor(
            "attack on titan", episode_number=1, season_number=1)

    def test_look(self, mock_response):
        assert self.monitor.episode_number == 1
        self.monitor.look()
        assert self.monitor.episode_number == 2

    def test_look_max_seeders(self, mock_response):
        result = self.monitor.look()
        assert result.name == "Torrent 3"

    def test_look_no_episodes(self, mock_response_empty):
        assert self.monitor.episode_number == 1
        result = self.monitor.look()
        assert result is None
        assert self.monitor.episode_number == 1

    def test_look_max_seeders_with_size_limit(self, mock_response):
        self.monitor.size_limit_gb = 1
        result = self.monitor.look()
        assert result.name == "Torrent 1"

    def test_look_max_seeders_with_small_size_limit(self, mock_response):
        assert self.monitor.episode_number == 1
        self.monitor.size_limit_gb = 0.5
        result = self.monitor.look()
        assert result is None
        assert self.monitor.episode_number == 1

    def test_look_http_error(self, mock_response_404):
        self.monitor.look()
        assert self.monitor.episode_number == 1

    def test_look_timeout(self, mock_timeout):
        self.monitor.look()
        assert self.monitor.episode_number == 1

    def test_look_zero_episode(self, mock_response):
        self.monitor.episode_number = 0
        self.monitor.season_number = 0
        self.monitor.look()
        assert mock_response["query"] == "attack on titan s00e00"
        self.monitor.look()
        assert mock_response["query"] == "attack on titan s00e01"
