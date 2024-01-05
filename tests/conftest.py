import pytest
from typing import Callable
from torrent_manager.pb_client import requests
from dataclasses import dataclass, field
from enum import Enum
import json


@dataclass
class PBResponse:
    data: dict = field(default_factory=dict)
    status_code: int = 200
    text: str = ""

    def __post_init__(self):
        if self.data:
            self.text = json.dumps(self.data)


@dataclass
class Buffer:
    urls: list = field(default_factory=list)
    queries: list = field(default_factory=list)
    calls: int = 0


class ResponseType(Enum):
    EMPTY = "empty"
    NOT_FOUND = "not found"
    ITERATION = "iteration"


with open("tests/fixtures/pb_response_no_data.json", "r") as file:
    data = json.load(file)
    pb_response_no_results = PBResponse(data)

with open("tests/fixtures/pb_response.json", "r") as file:
    data = json.load(file)
    pb_response = PBResponse(data)


def generate_mock_get(response_type: ResponseType | None = None) \
        -> tuple[Callable[[str, any], PBResponse], Buffer]:
    buffer = Buffer()

    def mock_get(url: str = "", **kwargs) -> PBResponse:
        query = kwargs.get("params", {}).get("q")
        buffer.urls.append(url)
        buffer.queries.append(query)
        buffer.calls += 1

        match response_type:
            case ResponseType.EMPTY:
                return pb_response_no_results
            case ResponseType.NOT_FOUND:
                return PBResponse(status_code=404)
            case ResponseType.ITERATION:
                if buffer.calls > 5:
                    return pb_response_no_results
                return pb_response
            case _:
                return pb_response

    return mock_get, buffer


@pytest.fixture
def mock_response(monkeypatch: pytest.MonkeyPatch):
    mock_get, buffer = generate_mock_get()
    monkeypatch.setattr(requests, "get", mock_get)
    return buffer


@pytest.fixture
def mock_response_iteration(monkeypatch: pytest.MonkeyPatch):
    mock_get, buffer = generate_mock_get(ResponseType.ITERATION)
    monkeypatch.setattr(requests, "get", mock_get)
    return buffer


@pytest.fixture
def mock_response_empty(monkeypatch: pytest.MonkeyPatch):
    mock_get, buffer = generate_mock_get(ResponseType.EMPTY)
    monkeypatch.setattr(requests, "get", mock_get)
    return buffer


@pytest.fixture
def mock_response_404(monkeypatch: pytest.MonkeyPatch):
    mock_get, buffer = generate_mock_get(ResponseType.NOT_FOUND)
    monkeypatch.setattr(requests, "get", mock_get)
    return buffer


@pytest.fixture
def mock_timeout(monkeypatch: pytest.MonkeyPatch):
    def throw_timeout(*args, **kwargs):
        raise requests.exceptions.ReadTimeout
    monkeypatch.setattr(requests, "get", throw_timeout)
