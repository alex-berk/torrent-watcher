import pytest
from typing import Callable
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


def generate_mock_get(response_type: str = "") -> tuple[Callable[[str, any], PBResponse], dict]:
    buffer = {"url": "", "query": "", "calls": 0}

    def mock_get(url: str, **kwargs) -> PBResponse:
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
