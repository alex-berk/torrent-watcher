import pytest
from src.pb_client import PBSearcher, PBMonitor, requests
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


@pytest.fixture
def mock_response(monkeypatch: pytest.MonkeyPatch):
    buffer = {"url": "", "query": "", "calls": 0}

    def mock_get(url, **kwargs):
        query = kwargs.get("params").get("q")
        buffer["url"] = url
        buffer["query"] = query
        buffer["calls"] += 1

        if query == "query_with_no_results":
            return pb_response_no_results
        elif query.startswith("throw"):
            desired_status_code = int(query.split()[1])
            return PBResponse(status_code=desired_status_code)
        return pb_response

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
        self.searcher_empty_results = PBSearcher("query_with_no_results")

    def test_search_torrent_sorting(self, mock_response):
        results = self.searcher.search_torrent()
        torrent_names = [result.name for result in results]
        assert torrent_names == ["Torrent 3", "Torrent 1", "Torrent 2"]

    def test_search_torrent_no_results(self, mock_response):
        results = self.searcher.search_torrent("query_with_no_results")
        assert results == []

    def test_search_torrent_http_error_handling(self, mock_response):
        assert self.searcher.search_torrent("throw 404") == []
        assert self.searcher.search_torrent("throw 500") == []
        assert self.searcher.search_torrent("throw 301") == []

    def test_search_torrent_http_timeout(self, mock_timeout):
        results = self.searcher.search_torrent()
        assert results == []

    def test_look(self, mock_response):
        results = self.searcher.look()
        assert results

    def test_look_no_results(self, mock_response):
        results = self.searcher_empty_results.look()
        assert results == None

    def test_look_http_timeout(self, mock_timeout):
        results = self.searcher.look()
        assert results == None
