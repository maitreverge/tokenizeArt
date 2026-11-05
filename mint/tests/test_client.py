"""Tests for the mint client library, on the local test chain."""

import base64
from pathlib import Path
from typing import Any

import pytest
from eth_account.signers.local import LocalAccount
from web3 import Web3
from web3.contract import Contract

from conftest import TEST_IMAGE_URI, TEST_IMAGE_URL
from metadata import decode_token_uri
from nft_client import (
    ClientError,
    ContractInfo,
    Windmill42Client,
)
from svg_pixels import svg_to_grid
from terminal_image import grid_to_text, png_to_grid

REPO_ROOT = Path(__file__).resolve().parents[2]
SVG_GRID = svg_to_grid(
    (REPO_ROOT / "mint/art/windmill42.svg").read_text(encoding="utf-8")
)
NOT_OWNER = "Only the contract owner can mint."


@pytest.fixture
def client(
    w3: Web3,
    windmill_local: Contract,
    funded_account: LocalAccount,
    compiled: Any,
) -> Windmill42Client:
    """A client signing with the contract owner's key."""
    return Windmill42Client(
        w3, windmill_local.address, compiled.abi, funded_account
    )


# --- metadata / image helpers ---------------------------------------------
def test_decode_token_uri_roundtrip() -> None:
    uri = "data:application/json;base64," + base64.b64encode(
        b'{"a": 1}'
    ).decode("ascii")
    assert decode_token_uri(uri) == {"a": 1}


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "ipfs://x",
        "data:application/json;base64,!!!",
        "data:application/json;base64,bm90IGpzb24=",  # "not json"
        "data:application/json;base64,WzFd",  # "[1]": not an object
    ],
)
def test_decode_token_uri_rejects(bad: str) -> None:
    with pytest.raises(ValueError):
        decode_token_uri(bad)


def test_grid_to_text_shape() -> None:
    lines = grid_to_text(SVG_GRID).plain.split("\n")
    assert len(lines) == 32
    assert all(len(line) == 64 for line in lines)


def test_png_to_grid_matches_svg() -> None:
    png = (REPO_ROOT / "mint/art/windmill42.png").read_bytes()
    assert png_to_grid(png) == SVG_GRID


def test_png_to_grid_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        png_to_grid(b"<html>gateway error</html>")


# --- client: reads ---------------------------------------------------------
def test_client_info(
    client: Windmill42Client, funded_account: LocalAccount
) -> None:
    info = client.info()
    assert info == ContractInfo(
        address=info.address,
        name="Windmill42",
        symbol="WM42",
        owner=funded_account.address,
        total_minted=0,
        max_supply=42,
        image_uri=TEST_IMAGE_URI,
        image_url=TEST_IMAGE_URL,
    )


def test_client_balance(client: Windmill42Client) -> None:
    assert 0 < client.eth_balance() < 100


def test_client_image_grid_is_onchain_art(client: Windmill42Client) -> None:
    assert client.image_grid() == SVG_GRID


# --- client: mint / owner / metadata ---------------------------------------
def test_client_mint_and_owner(
    client: Windmill42Client, funded_account: LocalAccount
) -> None:
    result = client.mint()
    assert result.token_id == 1
    assert result.tx_hash.startswith("0x") and len(result.tx_hash) == 66
    assert client.owner_of(1) == funded_account.address
    assert client.info().total_minted == 1


def test_client_mint_to_other_address(
    client: Windmill42Client, w3: Web3
) -> None:
    friend = list(w3.eth.accounts)[3]
    assert client.mint(friend).token_id == 1
    assert client.owner_of(1) == friend


def test_client_metadata(client: Windmill42Client) -> None:
    client.mint()
    metadata = client.metadata(1)
    assert metadata["name"] == "Windmill42 #1"
    assert metadata["artist"] == "flverge"
    assert metadata["image"] == TEST_IMAGE_URL
    assert client.token_uri(1).startswith("data:application/json;base64,")


def test_client_unknown_token(client: Windmill42Client) -> None:
    with pytest.raises(ClientError, match="does not exist"):
        client.owner_of(5)
    with pytest.raises(ClientError, match="does not exist"):
        client.metadata(5)


def test_client_cap_reached(client: Windmill42Client) -> None:
    for _ in range(42):
        client.mint()
    with pytest.raises(ClientError, match="All 42"):
        client.mint()


# --- client: security demo -------------------------------------------------
def test_simulate_non_owner_mint(client: Windmill42Client, w3: Web3) -> None:
    # the local test chain only simulates calls from funded addresses
    assert (
        client.simulate_non_owner_mint(list(w3.eth.accounts)[1]) == NOT_OWNER
    )
    assert client.info().total_minted == 0


def test_non_owner_client_cannot_mint(
    w3: Web3, windmill_local: Contract, compiled: Any
) -> None:
    stranger = w3.eth.account.create()
    w3.eth.send_transaction(
        {
            "from": list(w3.eth.accounts)[0],
            "to": stranger.address,
            "value": Web3.to_wei(1, "ether"),
        }
    )
    other = Windmill42Client(
        w3, windmill_local.address, compiled.abi, stranger
    )
    with pytest.raises(ClientError, match=NOT_OWNER):
        other.mint()


def test_client_transfer(client: Windmill42Client, w3: Web3) -> None:
    client.mint()
    friend = list(w3.eth.accounts)[3]
    result = client.transfer(1, friend)
    assert result.tx_hash.startswith("0x")
    assert client.owner_of(1) == friend


def test_client_transfer_token_not_owned(
    client: Windmill42Client, w3: Web3
) -> None:
    client.mint(list(w3.eth.accounts)[3])
    with pytest.raises(ClientError, match="does not own"):
        client.transfer(1, list(w3.eth.accounts)[4])


# --- client: bad input and failures ----------------------------------------
@pytest.mark.parametrize("address", ["0x123", "hello", ""])
def test_client_bad_address(client: Windmill42Client, address: str) -> None:
    with pytest.raises(ClientError, match="Not a valid Ethereum address"):
        client.mint(address)


def test_mint_insufficient_funds(
    w3: Web3,
    windmill_local: Contract,
    funded_account: LocalAccount,
    unfunded_account: LocalAccount,
    compiled: Any,
) -> None:
    owner = Windmill42Client(
        w3, windmill_local.address, compiled.abi, funded_account
    )
    owner.transfer_ownership(unfunded_account.address)
    broke = Windmill42Client(
        w3, windmill_local.address, compiled.abi, unfunded_account
    )
    with pytest.raises(ClientError, match="Not enough Sepolia ETH"):
        broke.mint()


def test_client_unreachable_rpc(compiled: Any) -> None:
    offline = Web3(Web3.HTTPProvider("http://127.0.0.1:9"))
    client = Windmill42Client(offline, "0x" + "12" * 20, compiled.abi)
    with pytest.raises(ClientError, match="Could not reach"):
        client.info()


def test_client_rejects_bad_contract_address(compiled: Any, w3: Web3) -> None:
    with pytest.raises(ClientError, match="Not a valid Ethereum address"):
        Windmill42Client(w3, "nope", compiled.abi)


def test_read_only_client_cannot_mint(
    w3: Web3, windmill_local: Contract, compiled: Any
) -> None:
    reader = Windmill42Client(w3, windmill_local.address, compiled.abi)
    assert reader.info().max_supply == 42
    with pytest.raises(ClientError, match="read-only"):
        reader.mint()


def test_client_no_contract_at_address(w3: Web3, compiled: Any) -> None:
    wallet = list(w3.eth.accounts)[2]  # a plain wallet, no contract code
    client = Windmill42Client(w3, wallet, compiled.abi)
    with pytest.raises(ClientError, match="No Windmill42 contract"):
        client.info()
