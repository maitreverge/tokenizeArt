"""The container provides every tool the project needs."""

from pathlib import Path

import solcx
from eth_account.signers.local import LocalAccount
from web3 import Web3

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_solc_is_installed() -> None:
    installed = [str(v) for v in solcx.get_installed_solc_versions()]
    assert "0.8.35" in installed


def test_openzeppelin_is_installed() -> None:
    erc721 = (
        REPO_ROOT
        / "deployment/node_modules/@openzeppelin/contracts"
        / "token/ERC721/ERC721.sol"
    )
    assert erc721.is_file()


def test_tester_chain_works(w3: Web3, funded_account: LocalAccount) -> None:
    balance = w3.eth.get_balance(funded_account.address)
    assert balance == Web3.to_wei(100, "ether")
