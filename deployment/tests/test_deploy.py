"""
Tests for the deployment script, on the local test chain.

The user's real .env is never loaded here: main() is always called with
load_dotenv replaced by a no-op and the variables removed.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import requests
from eth_account.signers.local import LocalAccount
from web3 import Web3

import deploy
from deploy import (
    DeployError,
    DeploymentResult,
    Settings,
    connect,
    deploy_contract,
    load_settings,
    save_contract_address,
    write_artifacts,
)

GOOD_KEY = "0x" + "ab" * 32
ENV_VARS = (
    "SEPOLIA_RPC_URL",
    "PRIVATE_KEY",
    "PINATA_JWT",
    "PINATA_GATEWAY",
    "CONTRACT_ADDRESS",
)
PUBLIC_GATEWAY = "https://gateway.pinata.cloud/ipfs/"


def make_files(tmp_path: Path, stale: bool = False) -> tuple[Path, Path]:
    """A fake PNG and a matching (or stale) mint/ipfs.json."""
    png = tmp_path / "windmill42.png"
    png.write_bytes(b"\x89PNG fake")
    digest = hashlib.sha256(b"other" if stale else png.read_bytes())
    record = tmp_path / "ipfs.json"
    record.write_text(
        json.dumps(
            {
                "file": "mint/art/windmill42.png",
                "sha256": digest.hexdigest(),
                "cid": "bafyfake",
                "imageURI": "ipfs://bafyfake",
                "gatewayURL": "https://ipfs.io/ipfs/bafyfake",
            }
        )
    )
    return record, png


def good_env() -> dict[str, str]:
    return {
        "SEPOLIA_RPC_URL": "https://rpc.example",
        "PRIVATE_KEY": GOOD_KEY,
    }


def test_settings_ok(tmp_path: Path) -> None:
    record, png = make_files(tmp_path)
    settings = load_settings(good_env(), record, png)
    assert settings == Settings(
        rpc_url="https://rpc.example",
        private_key=GOOD_KEY,
        image_cid="bafyfake",
        image_gateway=PUBLIC_GATEWAY,
    )
    assert settings.image_uri == "ipfs://bafyfake"
    assert settings.image_gateway_url == PUBLIC_GATEWAY + "bafyfake"


@pytest.mark.parametrize(
    "gateway",
    [
        "my-gw.mypinata.cloud",
        "https://my-gw.mypinata.cloud/",
        "  my-gw.mypinata.cloud/ipfs/ ",
    ],
)
def test_settings_use_pinata_gateway(tmp_path: Path, gateway: str) -> None:
    record, png = make_files(tmp_path)
    env = {**good_env(), "PINATA_GATEWAY": gateway}
    settings = load_settings(env, record, png)
    assert settings.image_gateway == "https://my-gw.mypinata.cloud/ipfs/"


@pytest.mark.parametrize("gateway", ["not a host", "https://", "a/b", "x?y"])
def test_settings_reject_bad_gateway(tmp_path: Path, gateway: str) -> None:
    record, png = make_files(tmp_path)
    env = {**good_env(), "PINATA_GATEWAY": gateway}
    with pytest.raises(DeployError, match="PINATA_GATEWAY"):
        load_settings(env, record, png)


@pytest.mark.parametrize(
    "key", ["", "abc", "0x" + "g" * 64, "1" * 63, "1" * 65]
)
def test_settings_reject_bad_private_key(tmp_path: Path, key: str) -> None:
    record, png = make_files(tmp_path)
    with pytest.raises(DeployError, match="PRIVATE_KEY"):
        load_settings({**good_env(), "PRIVATE_KEY": key}, record, png)


def test_settings_accept_key_without_0x_and_with_spaces(
    tmp_path: Path,
) -> None:
    record, png = make_files(tmp_path)
    env = {**good_env(), "PRIVATE_KEY": "  " + "ab" * 32 + " \n"}
    assert load_settings(env, record, png).private_key == GOOD_KEY


@pytest.mark.parametrize("url", ["", "ftp://x", "rpc.example"])
def test_settings_reject_bad_rpc_url(tmp_path: Path, url: str) -> None:
    record, png = make_files(tmp_path)
    with pytest.raises(DeployError, match="SEPOLIA_RPC_URL"):
        load_settings({**good_env(), "SEPOLIA_RPC_URL": url}, record, png)


def test_settings_reject_missing_ipfs_record(tmp_path: Path) -> None:
    _, png = make_files(tmp_path)
    with pytest.raises(DeployError, match="pin_to_ipfs.py"):
        load_settings(good_env(), tmp_path / "missing.json", png)


def test_settings_reject_stale_ipfs_record(tmp_path: Path) -> None:
    record, png = make_files(tmp_path, stale=True)
    with pytest.raises(DeployError, match="re-run"):
        load_settings(good_env(), record, png)


def test_connect_unreachable_rpc() -> None:
    with pytest.raises(DeployError, match="reach"):
        connect("http://127.0.0.1:9")


def test_deploy_on_tester_chain(
    w3: Web3, funded_account: LocalAccount, compiled: Any
) -> None:
    result = deploy_contract(
        w3, funded_account, compiled, "bafyfake", PUBLIC_GATEWAY
    )
    address = Web3.to_checksum_address(result.address)
    assert w3.eth.get_code(address) != b""
    contract = w3.eth.contract(address=address, abi=compiled.abi)
    assert contract.functions.owner().call() == funded_account.address
    assert contract.functions.imageURI().call() == "ipfs://bafyfake"
    assert contract.functions.imageURL().call() == (
        PUBLIC_GATEWAY + "bafyfake"
    )
    assert result.deployer == funded_account.address
    assert result.gas_used > 0 and result.block_number > 0
    assert result.tx_hash.startswith("0x")


def test_deploy_insufficient_funds(
    w3: Web3, unfunded_account: LocalAccount, compiled: Any
) -> None:
    with pytest.raises(DeployError, match="Not enough Sepolia ETH"):
        deploy_contract(
            w3, unfunded_account, compiled, "bafyfake", PUBLIC_GATEWAY
        )


def test_write_artifacts(tmp_path: Path, compiled: Any) -> None:
    result = DeploymentResult(
        address="0x" + "12" * 20,
        tx_hash="0x" + "34" * 32,
        block_number=7,
        gas_used=2_500_000,
        deployer="0x" + "56" * 20,
        chain_id=11155111,
    )
    settings = Settings(
        rpc_url="https://secret-rpc.example/v3/KEY",
        private_key=GOOD_KEY,
        image_cid="bafyfake",
        image_gateway=PUBLIC_GATEWAY,
    )
    artifact = tmp_path / "artifacts/Windmill42.json"
    website = tmp_path / "website/config.json"
    write_artifacts(result, compiled, settings, artifact, website)

    saved = json.loads(artifact.read_text())
    assert saved["contract"] == "Windmill42"
    assert saved["network"] == "sepolia"
    assert saved["chainId"] == 11155111
    assert saved["address"] == result.address
    assert saved["txHash"] == result.tx_hash
    assert saved["blockNumber"] == 7
    assert saved["deployer"] == result.deployer
    assert saved["imageURI"] == "ipfs://bafyfake"
    assert saved["abi"] == compiled.abi
    config = json.loads(website.read_text())
    assert config == {
        "address": result.address,
        "chainId": 11155111,
        "abi": compiled.abi,
        "imageGatewayURL": PUBLIC_GATEWAY + "bafyfake",
    }
    # secrets never end up in committed files
    for text in (artifact.read_text(), website.read_text()):
        assert GOOD_KEY.removeprefix("0x") not in text
        assert "secret-rpc" not in text


def test_save_contract_address(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("PRIVATE_KEY=abc\nCONTRACT_ADDRESS=\n")
    save_contract_address(env_file, "0x" + "12" * 20)
    text = env_file.read_text()
    assert "CONTRACT_ADDRESS=0x" + "12" * 20 in text
    assert "PRIVATE_KEY=abc" in text


def test_main_returns_1_without_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(deploy, "load_dotenv", lambda *a, **k: None)
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    assert deploy.main(["--yes"]) == 1
    output = capsys.readouterr().out
    assert "✗" in output
    assert "Traceback" not in output


@pytest.mark.parametrize(
    "wei, text",
    [
        (10**18, "1.000000 ETH"),
        (1_500_000_000_000_000, "0.001500 ETH"),
        (1_176_092_544, "0.0000000012 ETH"),  # real Sepolia deployment fee
        (0, "0 ETH"),
    ],
)
def test_format_eth_keeps_tiny_amounts_visible(wei: int, text: str) -> None:
    assert deploy.format_eth(wei) == text


# --- the image link must answer before deploying ---------------------------
class FakeImageResponse:
    """Stand-in for requests' response to a gateway download."""

    def __init__(self, status_code: int, content: bytes) -> None:
        self.status_code = status_code
        self.content = content


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"x" * 20


def fake_get(response: Any) -> Any:
    def get(*args: Any, **kwargs: Any) -> Any:
        if isinstance(response, Exception):
            raise response
        return response

    return get


def test_check_image_link_accepts_png(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        requests, "get", fake_get(FakeImageResponse(200, PNG_BYTES))
    )
    deploy.check_image_link("https://gw.test/ipfs/bafyfake")


@pytest.mark.parametrize(
    "response",
    [
        FakeImageResponse(404, b"timed out searching for a file"),
        FakeImageResponse(200, b"<html>gateway error</html>"),
        requests.ConnectionError("no route"),
        requests.Timeout("too slow"),
    ],
)
def test_check_image_link_rejects_broken_gateway(
    monkeypatch: pytest.MonkeyPatch, response: Any
) -> None:
    monkeypatch.setattr(requests, "get", fake_get(response))
    with pytest.raises(DeployError, match="PINATA_GATEWAY"):
        deploy.check_image_link("https://gw.test/ipfs/bafyfake")


def test_main_stops_before_deploying_when_image_link_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(deploy, "load_dotenv", lambda *a, **k: None)
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SEPOLIA_RPC_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("PRIVATE_KEY", GOOD_KEY)
    monkeypatch.setattr(
        requests, "get", fake_get(FakeImageResponse(404, b"not found"))
    )
    called: list[str] = []
    monkeypatch.setattr(deploy, "connect", lambda *a: called.append("x"))
    assert deploy.main(["--yes"]) == 1
    output = capsys.readouterr().out
    assert "PINATA_GATEWAY" in output and "Traceback" not in output
    assert called == []  # stopped before even connecting
