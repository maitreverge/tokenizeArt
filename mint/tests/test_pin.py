"""Tests for the IPFS pinning script (the network is always faked)."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import requests

import pin_to_ipfs
from pin_to_ipfs import PinError, pin_file, write_record


class FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self) -> Any:
        return self._payload


@pytest.fixture
def png(tmp_path: Path) -> Path:
    path = tmp_path / "windmill42.png"
    path.write_bytes(b"\x89PNG fake image")
    return path


def fake_post(
    monkeypatch: pytest.MonkeyPatch, response: Any, calls: list[Any]
) -> None:
    def post(url: str, **kwargs: Any) -> Any:
        calls.append((url, kwargs))
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(requests, "post", post)


def test_pin_returns_cid(monkeypatch: pytest.MonkeyPatch, png: Path) -> None:
    calls: list[Any] = []
    ok = FakeResponse(200, {"data": {"cid": "bafyfake", "name": "x"}})
    fake_post(monkeypatch, ok, calls)
    assert pin_file(png, "jwt123") == "bafyfake"
    url, kwargs = calls[0]
    assert url == "https://uploads.pinata.cloud/v3/files"
    assert kwargs["data"]["network"] == "public"
    assert "file" in kwargs["files"]


def test_pin_sends_bearer_jwt(
    monkeypatch: pytest.MonkeyPatch, png: Path
) -> None:
    calls: list[Any] = []
    ok = FakeResponse(200, {"data": {"cid": "bafyfake"}})
    fake_post(monkeypatch, ok, calls)
    pin_file(png, "  jwt123 \n")
    assert calls[0][1]["headers"]["Authorization"] == "Bearer jwt123"


@pytest.mark.parametrize("status", [401, 403])
def test_pin_unauthorized(
    monkeypatch: pytest.MonkeyPatch, png: Path, status: int
) -> None:
    fake_post(monkeypatch, FakeResponse(status, {"error": "no"}), [])
    with pytest.raises(PinError, match="PINATA_JWT"):
        pin_file(png, "bad")


def test_pin_server_error(monkeypatch: pytest.MonkeyPatch, png: Path) -> None:
    fake_post(monkeypatch, FakeResponse(500, {"error": "boom"}), [])
    with pytest.raises(PinError, match="500"):
        pin_file(png, "jwt")


def test_pin_network_error(monkeypatch: pytest.MonkeyPatch, png: Path) -> None:
    fake_post(monkeypatch, requests.ConnectionError("offline"), [])
    with pytest.raises(PinError):
        pin_file(png, "jwt")


def test_pin_response_without_cid(
    monkeypatch: pytest.MonkeyPatch, png: Path
) -> None:
    fake_post(monkeypatch, FakeResponse(200, {"data": {}}), [])
    with pytest.raises(PinError, match="CID"):
        pin_file(png, "jwt")


def test_pin_empty_jwt(monkeypatch: pytest.MonkeyPatch, png: Path) -> None:
    calls: list[Any] = []
    fake_post(monkeypatch, FakeResponse(200, {}), calls)
    with pytest.raises(PinError, match="PINATA_JWT"):
        pin_file(png, "  ")
    assert calls == []


def test_pin_missing_file(tmp_path: Path) -> None:
    with pytest.raises(PinError, match="not found"):
        pin_file(tmp_path / "nope.png", "jwt")


def test_record_contents(png: Path, tmp_path: Path) -> None:
    out = tmp_path / "ipfs.json"
    record = write_record("bafyfake", png, out)
    assert json.loads(out.read_text()) == record
    assert record["cid"] == "bafyfake"
    assert record["imageURI"] == "ipfs://bafyfake"
    assert record["gatewayURL"] == "https://gateway.pinata.cloud/ipfs/bafyfake"
    assert record["sha256"] == hashlib.sha256(png.read_bytes()).hexdigest()
    assert record["file"] == "mint/art/windmill42.png"


def test_record_uses_dedicated_gateway(png: Path, tmp_path: Path) -> None:
    record = write_record(
        "bafyfake",
        png,
        tmp_path / "ipfs.json",
        gateway="https://my-gw.mypinata.cloud/",
    )
    assert record["gatewayURL"] == (
        "https://my-gw.mypinata.cloud/ipfs/bafyfake"
    )


def test_main_without_jwt_fails_cleanly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(pin_to_ipfs, "load_dotenv", lambda *a, **k: None)
    monkeypatch.delenv("PINATA_JWT", raising=False)
    assert pin_to_ipfs.main() == 1
    output = capsys.readouterr().out
    assert "✗" in output and "Traceback" not in output


def test_main_error_with_brackets_does_not_crash(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(pin_to_ipfs, "load_dotenv", lambda *a, **k: None)

    def broken(*args: Any, **kwargs: Any) -> str:
        raise PinError("Pinata upload failed (500): [/oops] {bad}")

    monkeypatch.setattr(pin_to_ipfs, "pin_file", broken)
    assert pin_to_ipfs.main() == 1
    assert "[/oops]" in capsys.readouterr().out
