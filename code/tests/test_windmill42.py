"""Tests for the Windmill42 smart contract, on a local test chain."""

import base64
import json
from pathlib import Path
from typing import Any

import pytest
from web3 import Web3
from web3.contract import Contract

from compiler import CompileError, compile_windmill42
from conftest import (
    TEST_GATEWAY,
    TEST_IMAGE_CID,
    TEST_IMAGE_URI,
    TEST_IMAGE_URL,
    revert_name,
)


def test_compiles_and_selects_windmill42(compiled: Any) -> None:
    names = {e.get("name") for e in compiled.abi}
    assert {
        "mint",
        "totalMinted",
        "MAX_SUPPLY",
        "imageURI",
        "imageURL",
    } <= names
    assert "setImageGateway" in names


def test_name_symbol_and_constants(windmill: Contract) -> None:
    f = windmill.functions
    assert f.name().call() == "Windmill42"
    assert f.symbol().call() == "WM42"
    assert f.MAX_SUPPLY().call() == 42
    assert f.ARTIST().call() == "flverge"
    assert f.TITLE().call() == "Spring Meadow"
    assert f.imageCID().call() == TEST_IMAGE_CID
    assert f.imageURI().call() == TEST_IMAGE_URI
    assert f.imageGateway().call() == TEST_GATEWAY
    assert f.imageURL().call() == TEST_IMAGE_URL
    assert f.totalMinted().call() == 0


def test_deployer_is_owner(w3: Web3, windmill: Contract) -> None:
    assert windmill.functions.owner().call() == w3.eth.accounts[0]


def test_owner_mints_ids_from_one(w3: Web3, windmill: Contract) -> None:
    owner, collector, *_ = list(w3.eth.accounts)
    for _ in range(2):
        windmill.functions.mint(collector).transact({"from": owner})
    assert windmill.functions.ownerOf(1).call() == collector
    assert windmill.functions.ownerOf(2).call() == collector
    assert windmill.functions.totalMinted().call() == 2
    assert windmill.functions.balanceOf(collector).call() == 2


def test_non_owner_cannot_mint(
    w3: Web3, windmill: Contract, compiled: Any
) -> None:
    stranger = list(w3.eth.accounts)[1]
    with pytest.raises(Exception) as error:
        windmill.functions.mint(stranger).transact({"from": stranger})
    assert revert_name(error.value, compiled.abi) == (
        "OwnableUnauthorizedAccount"
    )
    assert windmill.functions.totalMinted().call() == 0


def test_supply_is_capped_at_42(
    w3: Web3, windmill: Contract, compiled: Any
) -> None:
    owner = w3.eth.accounts[0]
    for _ in range(42):
        windmill.functions.mint(owner).transact({"from": owner})
    with pytest.raises(Exception) as error:
        windmill.functions.mint(owner).transact({"from": owner})
    assert revert_name(error.value, compiled.abi) == "MaxSupplyReached"
    assert windmill.functions.totalMinted().call() == 42
    assert windmill.functions.ownerOf(42).call() == owner


@pytest.mark.parametrize(
    ("cid", "gateway", "expected"),
    [
        ("", TEST_GATEWAY, "EmptyImageCID"),
        (TEST_IMAGE_CID, "", "EmptyImageGateway"),
    ],
)
def test_constructor_rejects_empty_image_settings(
    w3: Web3, compiled: Any, cid: str, gateway: str, expected: str
) -> None:
    factory = w3.eth.contract(abi=compiled.abi, bytecode=compiled.bytecode)
    with pytest.raises(Exception) as error:
        factory.constructor(cid, gateway).transact(
            {"from": w3.eth.accounts[0]}
        )
    assert revert_name(error.value, compiled.abi) == expected


NEW_GATEWAY = "https://new-gateway.test/ipfs/"


def test_owner_changes_image_gateway(w3: Web3, windmill: Contract) -> None:
    owner = w3.eth.accounts[0]
    windmill.functions.mint(owner).transact({"from": owner})
    tx_hash = windmill.functions.setImageGateway(NEW_GATEWAY).transact(
        {"from": owner}
    )
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    assert windmill.functions.imageURL().call() == NEW_GATEWAY + TEST_IMAGE_CID
    assert windmill.functions.imageURI().call() == TEST_IMAGE_URI
    metadata = decode(windmill.functions.tokenURI(1).call())
    assert metadata["image"] == NEW_GATEWAY + TEST_IMAGE_CID
    # ERC-4906: tells wallets and marketplaces to reload tokens 1..42
    events = windmill.events.BatchMetadataUpdate().process_receipt(receipt)
    assert [dict(e["args"]) for e in events] == [
        {"_fromTokenId": 1, "_toTokenId": 42}
    ]


def test_non_owner_cannot_change_image_gateway(
    w3: Web3, windmill: Contract, compiled: Any
) -> None:
    stranger = list(w3.eth.accounts)[1]
    with pytest.raises(Exception) as error:
        windmill.functions.setImageGateway(NEW_GATEWAY).transact(
            {"from": stranger}
        )
    assert revert_name(error.value, compiled.abi) == (
        "OwnableUnauthorizedAccount"
    )
    assert windmill.functions.imageGateway().call() == TEST_GATEWAY


def test_empty_image_gateway_rejected(
    w3: Web3, windmill: Contract, compiled: Any
) -> None:
    with pytest.raises(Exception) as error:
        windmill.functions.setImageGateway("").transact(
            {"from": w3.eth.accounts[0]}
        )
    assert revert_name(error.value, compiled.abi) == "EmptyImageGateway"


@pytest.mark.parametrize(
    ("interface_id", "supported"),
    [
        ("0x80ac58cd", True),  # ERC-721
        ("0x49064906", True),  # ERC-4906 metadata updates
        ("0xffffffff", False),
    ],
)
def test_supports_interface(
    windmill: Contract, interface_id: str, supported: bool
) -> None:
    result = windmill.functions.supportsInterface(interface_id).call()
    assert result is supported


def test_transfer_changes_owner(w3: Web3, windmill: Contract) -> None:
    owner, _, friend, *_ = list(w3.eth.accounts)
    windmill.functions.mint(owner).transact({"from": owner})
    windmill.functions.transferFrom(owner, friend, 1).transact({"from": owner})
    assert windmill.functions.ownerOf(1).call() == friend


def test_unknown_contract_path_raises_compile_error(tmp_path: Path) -> None:
    with pytest.raises(CompileError):
        compile_windmill42(tmp_path / "missing.sol")


# ---------------------------------------------------------------------------
# On-chain image and on-chain metadata
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
COMMITTED_SVG = (REPO_ROOT / "mint/art/windmill42.svg").read_text(
    encoding="utf-8"
)
JSON_PREFIX = "data:application/json;base64,"


def decode(uri: str) -> dict[str, Any]:
    """Decode an on-chain data: URI into its JSON metadata."""
    assert uri.startswith(JSON_PREFIX)
    result: dict[str, Any] = json.loads(
        base64.b64decode(uri[len(JSON_PREFIX) :])
    )
    return result


def test_svg_matches_committed_svg_byte_for_byte(windmill: Contract) -> None:
    assert windmill.functions.svgImage().call() == COMMITTED_SVG


def test_token_uri_is_onchain_json(w3: Web3, windmill: Contract) -> None:
    owner = w3.eth.accounts[0]
    windmill.functions.mint(owner).transact({"from": owner})
    metadata = decode(windmill.functions.tokenURI(1).call())
    assert metadata["name"] == "Windmill42 #1"
    assert metadata["image"] == TEST_IMAGE_URL
    assert metadata["image_data"] == COMMITTED_SVG
    assert metadata["artist"] == "flverge"
    assert "Spring Meadow" in metadata["description"]
    assert {"trait_type": "Artist", "value": "flverge"} in metadata[
        "attributes"
    ]
    assert {"trait_type": "Title", "value": "Spring Meadow"} in metadata[
        "attributes"
    ]
    assert {"trait_type": "Edition", "value": "1/42"} in metadata["attributes"]


def test_token_uri_name_contains_42(w3: Web3, windmill: Contract) -> None:
    owner = w3.eth.accounts[0]
    for _ in range(7):
        windmill.functions.mint(owner).transact({"from": owner})
    metadata = decode(windmill.functions.tokenURI(7).call())
    assert metadata["name"] == "Windmill42 #7"
    assert "42" in metadata["name"]
    assert {"trait_type": "Edition", "value": "7/42"} in metadata["attributes"]


def test_token_uri_unknown_token_reverts(
    windmill: Contract, compiled: Any
) -> None:
    with pytest.raises(Exception) as error:
        windmill.functions.tokenURI(1).call()
    assert revert_name(error.value, compiled.abi) == "ERC721NonexistentToken"


def test_runtime_bytecode_under_eip170(compiled: Any) -> None:
    assert len(bytes.fromhex(compiled.runtime_bytecode)) < 24_576


def test_view_calls_are_cheap(w3: Web3, windmill: Contract) -> None:
    owner = w3.eth.accounts[0]
    windmill.functions.mint(owner).transact({"from": owner})
    # Each call must succeed within a gas cap well below public RPC limits
    # (measured: svgImage ~4.4M gas, tokenURI ~5.2M gas).
    assert windmill.functions.svgImage().call({"gas": 15_000_000})
    assert windmill.functions.tokenURI(1).call({"gas": 20_000_000})
