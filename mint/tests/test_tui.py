"""Tests for the mint TUI command handling (no real terminal needed)."""

import json
from pathlib import Path
from typing import Any

import pytest
import requests
from eth_account.signers.local import LocalAccount
from rich.console import Console
from web3 import Web3
from web3.contract import Contract

import mint_tui
from conftest import TEST_IMAGE_URL
from mint_tui import (
    ABI_PATH,
    Session,
    build_layout,
    dispatch,
    parse_token_id,
    resolve_contract,
)
from nft_client import ClientError, ContractInfo, Windmill42Client

REPO_ROOT = Path(__file__).resolve().parents[2]
BIG = (140, 50)  # a comfortable terminal: columns x rows


@pytest.fixture
def session(
    w3: Web3,
    windmill_local: Contract,
    funded_account: LocalAccount,
    compiled: Any,
) -> Session:
    client = Windmill42Client(
        w3, windmill_local.address, compiled.abi, funded_account
    )
    # the local chain only simulates calls from funded addresses
    return Session(client=client, stranger=list(w3.eth.accounts)[1])


def test_abi_file_matches_compiled_contract(compiled: Any) -> None:
    assert json.loads(ABI_PATH.read_text(encoding="utf-8")) == compiled.abi


@pytest.mark.parametrize(
    "raw", ["", "abc", "-3", "0", "43", "99999999999999999999", "1.5", "4 2"]
)
def test_parse_token_id_rejects(raw: str) -> None:
    with pytest.raises(ValueError, match="between 1 and 42"):
        parse_token_id(raw)


def test_parse_token_id_accepts() -> None:
    assert parse_token_id(" 42 ") == 42 and parse_token_id("1") == 1


@pytest.mark.parametrize(
    "command",
    [
        "uri",
        "uri abc",
        "uri -3",
        "uri 0",
        "uri 43",
        "uri 99999999999999999999",
        "owner",
        "owner 1 2",
        "send 1",
        "send x y",
        "send 1 nope",
        "view 0",
        "mint 0x12",
        "mint a b",
    ],
)
def test_dispatch_rejects_bad_token_ids(
    session: Session, command: str
) -> None:
    status = dispatch(command, session, BIG)
    assert "✓" not in status
    assert "Unexpected error" not in status  # a handled, explained refusal
    expected = ("between 1 and 42", "Usage:", "Not a valid Ethereum address")
    assert any(text in status for text in expected), status


def test_dispatch_mint_then_owner(
    session: Session, funded_account: LocalAccount
) -> None:
    status = dispatch("mint", session, BIG)
    assert "#1" in status
    assert session.last_tx.startswith("0x")
    assert session.info is not None and session.info.total_minted == 1
    status = dispatch("owner 1", session, BIG)
    assert funded_account.address in status and "that's you" in status


def test_dispatch_mint_to_address(session: Session, w3: Web3) -> None:
    friend = list(w3.eth.accounts)[5]
    assert "#1" in dispatch(f"mint {friend}", session, BIG)
    status = dispatch("owner 1", session, BIG)
    assert friend in status and "that's you" not in status


def test_dispatch_uri_shows_artist_and_name(session: Session) -> None:
    dispatch("mint", session, BIG)
    dispatch("uri 1", session, BIG)
    assert session.details is not None
    text = session.details.plain
    assert "flverge" in text and "Windmill42 #1" in text
    assert "Spring Meadow" in text and "1/42" in text


def test_dispatch_uri_unknown_token(session: Session) -> None:
    assert "does not exist" in dispatch("uri 3", session, BIG)


def test_dispatch_view_draws_onchain_image(session: Session) -> None:
    status = dispatch("view", session, BIG)
    assert "on-chain" in status.lower()
    assert session.image is not None
    assert len(session.image.plain.split("\n")) == 32


def test_dispatch_view_unknown_token(session: Session) -> None:
    assert "does not exist" in dispatch("view 2", session, BIG)
    assert session.image is None


def test_view_terminal_too_small(session: Session) -> None:
    status = dispatch("view", session, (60, 20))
    assert "Terminal too small" in status
    assert session.image is None


def test_dispatch_ipfs_matches_onchain(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    png = (REPO_ROOT / "mint/art/windmill42.png").read_bytes()
    urls: list[str] = []

    def fake_fetch(url: str) -> bytes:
        urls.append(url)
        return png

    monkeypatch.setattr(mint_tui, "fetch_ipfs_png", fake_fetch)
    status = dispatch("ipfs", session, BIG)
    assert "matches the on-chain image" in status
    # the image is downloaded from the link the contract gives wallets
    assert urls == [TEST_IMAGE_URL]
    assert session.image is not None


def test_dispatch_ipfs_gateway_down(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(url: str) -> bytes:
        raise ClientError("Could not download the image from IPFS.")

    monkeypatch.setattr(mint_tui, "fetch_ipfs_png", broken)
    assert "Could not download" in dispatch("ipfs", session, BIG)


def test_dispatch_hack(session: Session) -> None:
    status = dispatch("hack", session, BIG)
    assert "Only the contract owner can mint." in status
    assert session.info is not None and session.info.total_minted == 0


def test_dispatch_send(session: Session, w3: Web3) -> None:
    dispatch("mint", session, BIG)
    friend = list(w3.eth.accounts)[4]
    status = dispatch(f"send 1 {friend}", session, BIG)
    assert friend in status
    assert "that's you" not in dispatch("owner 1", session, BIG)


def test_dispatch_unknown_command(session: Session) -> None:
    assert "Unknown command" in dispatch("dance", session, BIG)


def test_dispatch_empty_command(session: Session) -> None:
    assert dispatch("   ", session, BIG) == ""


def test_dispatch_survives_rpc_failure(compiled: Any) -> None:
    offline = Web3(Web3.HTTPProvider("http://127.0.0.1:9"))
    client = Windmill42Client(offline, "0x" + "12" * 20, compiled.abi)
    session = Session(client=client)
    for command in ("owner 1", "uri 1", "view", "refresh"):
        status = dispatch(command, session, BIG)
        assert "Could not reach the Sepolia node" in status, command
    assert "read-only" in dispatch("mint", session, BIG)


def test_read_only_session_cannot_mint(
    w3: Web3, windmill_local: Contract, compiled: Any
) -> None:
    reader = Windmill42Client(w3, windmill_local.address, compiled.abi)
    assert "read-only" in dispatch("mint", Session(client=reader), BIG)


def test_resolve_contract_prefers_env(tmp_path: Path) -> None:
    artifact = tmp_path / "Windmill42.json"
    artifact.write_text(json.dumps({"address": "0x" + "11" * 20}))
    env = {"CONTRACT_ADDRESS": " 0x" + "22" * 20 + " "}
    address, abi = resolve_contract(env, artifact, ABI_PATH)
    assert address == "0x" + "22" * 20
    assert any(entry.get("name") == "mint" for entry in abi)


def test_resolve_contract_falls_back_to_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "Windmill42.json"
    artifact.write_text(json.dumps({"address": "0x" + "11" * 20}))
    address, _ = resolve_contract({}, artifact, ABI_PATH)
    assert address == "0x" + "11" * 20


def test_resolve_contract_missing_everything(tmp_path: Path) -> None:
    with pytest.raises(ClientError, match="deploy.py"):
        resolve_contract({}, tmp_path / "missing.json", ABI_PATH)


def test_build_layout_renders(session: Session) -> None:
    dispatch("mint", session, BIG)
    dispatch("view", session, BIG)
    console = Console(width=BIG[0], height=BIG[1], record=True)
    console.print(build_layout(session, "owner 1", "✓ done", BIG))
    screen = console.export_text()
    assert "Windmill42" in screen and "1/42" in screen
    assert "owner 1" in screen


@pytest.mark.parametrize(
    "url", ["http://127.0.0.1:8080/x.png", "file:///etc/passwd", "ipfs://x"]
)
def test_fetch_ipfs_png_requires_https(url: str) -> None:
    with pytest.raises(ClientError, match="https"):
        mint_tui.fetch_ipfs_png(url)


class FakeResponse:
    """Stands in for requests' streamed response."""

    status_code = 200

    def __init__(self, size: int) -> None:
        self.size = size

    def iter_content(self, chunk_size: int) -> Any:
        sent = 0
        while sent < self.size:
            yield b"x" * min(chunk_size, self.size - sent)
            sent += chunk_size

    def close(self) -> None:
        pass


def test_fetch_ipfs_png_caps_download_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    big = FakeResponse(mint_tui.MAX_IMAGE_BYTES + 1)
    monkeypatch.setattr(requests, "get", lambda *a, **k: big)
    with pytest.raises(ClientError, match="too large"):
        mint_tui.fetch_ipfs_png("https://gateway.test/ipfs/big")


def test_fetch_ipfs_png_returns_small_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    small = FakeResponse(1000)
    monkeypatch.setattr(requests, "get", lambda *a, **k: small)
    assert mint_tui.fetch_ipfs_png("https://gateway.test/ipfs/s") == (
        b"x" * 1000
    )


# --- mint never reports a mined mint as a failure --------------------------
def test_mint_success_survives_failed_refresh(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(_: Session) -> None:
        raise ClientError("Could not reach the Sepolia node.")

    monkeypatch.setattr(mint_tui, "refresh_info", broken)
    status = dispatch("mint", session, BIG)
    assert "Minted Windmill42 #1" in status
    assert "could not refresh" in status
    assert session.last_tx.startswith("0x")


def test_info_panel_escapes_contract_strings(session: Session) -> None:
    # A contract (CONTRACT_ADDRESS can be any address) controls these
    # strings: Rich markup inside them must be shown, not interpreted.
    session.info = ContractInfo(
        address="0x" + "12" * 20,
        name="[/bold]Evil[",
        symbol="[red]X",
        owner="[/]",
        total_minted=1,
        max_supply=42,
        image_uri="ipfs://[/x]",
        image_url="https://gw.test/ipfs/x",
    )
    console = Console(width=BIG[0], height=BIG[1], record=True)
    console.print(build_layout(session, "", "", BIG))
    screen = console.export_text()
    assert "[/bold]Evil[" in screen and "ipfs://[/x]" in screen
