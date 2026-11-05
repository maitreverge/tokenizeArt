"""
Shared pytest fixtures: a local in-memory Ethereum chain (eth-tester)
and test accounts, so tests never touch Sepolia or spend real gas.
"""

from pathlib import Path
from typing import Any, cast

import pytest
from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3 import EthereumTesterProvider, Web3
from web3.contract import Contract

REPO_ROOT = Path(__file__).resolve().parent


@pytest.fixture
def w3() -> Web3:
    """A fresh local test chain for each test."""
    return Web3(EthereumTesterProvider())


@pytest.fixture
def funded_account(w3: Web3) -> LocalAccount:
    """A brand-new local account holding 100 test ETH."""
    account: LocalAccount = Account.create()
    w3.eth.send_transaction(
        {
            "from": w3.eth.accounts[0],
            "to": account.address,
            "value": Web3.to_wei(100, "ether"),
        }
    )
    return account


@pytest.fixture
def unfunded_account() -> LocalAccount:
    """A brand-new local account with no ETH at all."""
    account: LocalAccount = Account.create()
    return account


# ---------------------------------------------------------------------------
# Windmill42 contract fixtures
# ---------------------------------------------------------------------------
TEST_IMAGE_CID = "bafytestwindmill42"
TEST_IMAGE_URI = "ipfs://" + TEST_IMAGE_CID
TEST_GATEWAY = "https://gateway.test/ipfs/"
TEST_IMAGE_URL = TEST_GATEWAY + TEST_IMAGE_CID


def revert_name(error: BaseException, abi: list[dict[str, Any]]) -> str:
    """Name of the Solidity custom error carried by a failed call."""
    from nft_client import decode_revert

    return decode_revert(error, abi)


@pytest.fixture(scope="session")
def compiled() -> Any:
    """The Windmill42 contract, compiled once per test session."""
    from compiler import compile_windmill42

    return compile_windmill42()


@pytest.fixture
def windmill(w3: Web3, compiled: Any) -> Contract:
    """Windmill42 deployed on the test chain by w3.eth.accounts[0]."""
    factory = w3.eth.contract(abi=compiled.abi, bytecode=compiled.bytecode)
    tx_hash = factory.constructor(TEST_IMAGE_CID, TEST_GATEWAY).transact(
        {"from": w3.eth.accounts[0]}
    )
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return cast(
        Contract,
        w3.eth.contract(address=receipt["contractAddress"], abi=compiled.abi),
    )


@pytest.fixture
def windmill_local(
    w3: Web3, funded_account: LocalAccount, compiled: Any
) -> Contract:
    """Windmill42 deployed by deploy.py's code; owner = funded_account."""
    from deploy import deploy_contract

    result = deploy_contract(
        w3, funded_account, compiled, TEST_IMAGE_CID, TEST_GATEWAY
    )
    contract: Contract = w3.eth.contract(
        address=Web3.to_checksum_address(result.address), abi=compiled.abi
    )
    return contract
