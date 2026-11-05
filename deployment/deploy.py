#! /usr/bin/env python3
"""
Deploy the Windmill42 NFT contract to the Ethereum Sepolia testnet.

Steps, printed one by one:
  1. load and check the configuration (.env + mint/ipfs.json)
  2. connect to Sepolia and show the deployer wallet
  3. check the Solidity compiler
  4. compile code/Windmill42.sol
  5. estimate the cost and ask for confirmation
  6. send the deployment transaction and wait for it to be mined
  7. save the address + ABI for the mint TUI and the website

Usage (in the container):  python deployment/deploy.py [--yes]
"""

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

import requests
from dotenv import load_dotenv, set_key
from eth_account import Account
from eth_account.signers.local import LocalAccount
from rich.console import Console
from rich.markup import escape
from web3 import Web3

from compiler import (
    SOLC_VERSION,
    CompileError,
    CompiledContract,
    compile_windmill42,
    ensure_solc,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = REPO_ROOT / ".env"
IPFS_RECORD_PATH = REPO_ROOT / "mint/ipfs.json"
PNG_PATH = REPO_ROOT / "mint/art/windmill42.png"
ARTIFACT_PATH = REPO_ROOT / "deployment/artifacts/Windmill42.json"
WEBSITE_CONFIG_PATH = REPO_ROOT / "mint/website/config.json"

SEPOLIA_CHAIN_ID = 11155111
# Pinata's public IPFS gateway, used when PINATA_GATEWAY is empty.
DEFAULT_GATEWAY = "gateway.pinata.cloud"
ETHERSCAN = "https://sepolia.etherscan.io"
TOTAL_STEPS = 7

console = Console()


class DeployError(Exception):
    """A problem the user can fix; shown as a single clear message."""


@dataclass(frozen=True)
class Settings:
    """Validated configuration for one deployment."""

    rpc_url: str
    private_key: str  # always "0x" + 64 hex characters
    image_cid: str  # IPFS CID of the pinned artwork
    image_gateway: str  # "https://<host>/ipfs/", shown to wallets

    @property
    def image_uri(self) -> str:
        """The artwork's IPFS address: "ipfs://<CID>"."""
        return f"ipfs://{self.image_cid}"

    @property
    def image_gateway_url(self) -> str:
        """https link to the artwork, as wallets will load it."""
        return self.image_gateway + self.image_cid


@dataclass(frozen=True)
class DeploymentResult:
    """What happened on-chain."""

    address: str
    tx_hash: str
    block_number: int
    gas_used: int
    deployer: str
    chain_id: int


def gateway_prefix(value: str) -> str:
    """
    PINATA_GATEWAY value -> "https://<host>/ipfs/".

    Accepts "my-gw.mypinata.cloud", with or without "https://" and
    "/ipfs/". Empty means Pinata's public gateway.

    Raises:
        DeployError: the value is not a domain name.
    """
    host = value.strip() or DEFAULT_GATEWAY
    host = host.removeprefix("https://").removeprefix("http://").strip("/")
    host = host.removesuffix("/ipfs").strip("/")
    if not re.fullmatch(r"[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+(:\d+)?", host):
        raise DeployError(
            "PINATA_GATEWAY must be a gateway domain, "
            "e.g. my-gateway.mypinata.cloud (or empty)."
        )
    return f"https://{host}/ipfs/"


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def check_image_link(url: str, timeout: float = 45) -> None:
    """
    Download the image once through its gateway link, as wallets will.

    Raises:
        DeployError: the gateway does not answer or does not serve a PNG
        (the deployed tokens would show no image).
    """
    hint = (
        "set PINATA_GATEWAY in .env to your Pinata dedicated gateway, "
        "or retry later."
    )
    try:
        response = requests.get(url, timeout=timeout)
    except requests.RequestException as error:
        raise DeployError(
            f"The image link did not answer ({url}): {hint}"
        ) from error
    if response.status_code != 200 or not response.content.startswith(
        PNG_SIGNATURE
    ):
        raise DeployError(
            f"The image link does not serve the artwork "
            f"(HTTP {response.status_code}, {url}): {hint}"
        )


def load_settings(
    env: Mapping[str, str], ipfs_record_path: Path, png_path: Path
) -> Settings:
    """
    Read and check the configuration.

    Raises:
        DeployError: with a hint on how to fix each problem.
    """
    rpc_url = env.get("SEPOLIA_RPC_URL", "").strip()
    if not rpc_url.startswith(("http://", "https://")):
        raise DeployError(
            "SEPOLIA_RPC_URL must be an http(s) URL "
            "(see .env.example for a free public one)."
        )
    key = env.get("PRIVATE_KEY", "").strip().removeprefix("0x")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", key):
        raise DeployError(
            "PRIVATE_KEY in .env must be 64 hexadecimal characters "
            "(MetaMask > Account details > Show private key)."
        )
    if not ipfs_record_path.is_file():
        raise DeployError(
            "mint/ipfs.json not found: pin the artwork first with "
            "`python mint/pin_to_ipfs.py`."
        )
    try:
        record = json.loads(ipfs_record_path.read_text(encoding="utf-8"))
        pinned_sha = str(record["sha256"])
        image_uri = str(record["imageURI"])
    except (ValueError, KeyError, TypeError) as error:
        raise DeployError(
            "mint/ipfs.json is invalid: re-run `python mint/pin_to_ipfs.py`."
        ) from error
    current_sha = hashlib.sha256(png_path.read_bytes()).hexdigest()
    if pinned_sha != current_sha:
        raise DeployError(
            "The artwork changed since it was pinned: re-run "
            "`python mint/pin_to_ipfs.py`."
        )
    cid = image_uri.removeprefix("ipfs://")
    if not image_uri.startswith("ipfs://") or not cid.isalnum():
        raise DeployError(
            "mint/ipfs.json: imageURI must be ipfs://<CID>; re-run "
            "`python mint/pin_to_ipfs.py`."
        )
    gateway = gateway_prefix(env.get("PINATA_GATEWAY", ""))
    return Settings(rpc_url, "0x" + key.lower(), cid, gateway)


def connect(rpc_url: str, expected_chain_id: int = SEPOLIA_CHAIN_ID) -> Web3:
    """Connect to the RPC node and make sure it is the expected chain."""
    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 20}))
    try:
        chain_id = w3.eth.chain_id
    except Exception as error:
        raise DeployError(
            "Could not reach the Sepolia node: check SEPOLIA_RPC_URL and "
            "your internet connection."
        ) from error
    if chain_id != expected_chain_id:
        raise DeployError(
            f"The RPC node is on chain {chain_id}, not Sepolia "
            f"({expected_chain_id}): check SEPOLIA_RPC_URL."
        )
    return w3


def to_eth(wei: int) -> Decimal:
    """Wei -> ETH, for display."""
    return Decimal(wei) / Decimal(10**18)


def format_eth(wei: int) -> str:
    """
    Wei -> readable ETH. Testnet fees can be tiny (1e-9 ETH), so small
    amounts keep two significant digits instead of rounding to 0.
    """
    if wei == 0:
        return "0 ETH"
    eth = to_eth(wei)
    if eth >= Decimal("0.000001"):
        return f"{eth:.6f} ETH"
    decimals = -eth.adjusted() + 1
    return f"{eth:.{decimals}f} ETH"


def estimate_cost_wei(
    w3: Web3,
    account: LocalAccount,
    compiled: CompiledContract,
    image_cid: str,
    image_gateway: str,
) -> int:
    """Upper estimate of the deployment fee: gas needed x gas price."""
    factory = w3.eth.contract(abi=compiled.abi, bytecode=compiled.bytecode)
    try:
        gas = factory.constructor(image_cid, image_gateway).estimate_gas(
            {"from": account.address}
        )
        return int(gas * w3.eth.gas_price)
    except Exception as error:
        # Some nodes refuse to even estimate for an empty wallet.
        if is_funds_error(error):
            raise DeployError(
                "Not enough Sepolia ETH to pay for gas "
                f"(balance of {account.address}: "
                f"{format_eth(w3.eth.get_balance(account.address))})."
            ) from error
        raise DeployError(f"Could not estimate the cost: {error}") from error


def is_funds_error(error: BaseException) -> bool:
    """True when a node error means the wallet cannot pay for gas."""
    text = str(error).lower()
    return "insufficient funds" in text or "cannot afford" in text


def deploy_contract(
    w3: Web3,
    account: LocalAccount,
    compiled: CompiledContract,
    image_cid: str,
    image_gateway: str,
) -> DeploymentResult:
    """
    Deploy Windmill42: build the transaction, sign it locally with the
    private key (the node never sees the key), send it, wait for the block.
    """
    cost = estimate_cost_wei(w3, account, compiled, image_cid, image_gateway)
    balance = w3.eth.get_balance(account.address)
    if balance < cost:
        raise DeployError(
            f"Not enough Sepolia ETH: need ~{format_eth(cost)}, "
            f"have {format_eth(balance)} (use a Sepolia faucet)."
        )
    factory = w3.eth.contract(abi=compiled.abi, bytecode=compiled.bytecode)
    try:
        constructor = factory.constructor(image_cid, image_gateway)
        transaction = constructor.build_transaction(
            {
                "from": account.address,
                "nonce": w3.eth.get_transaction_count(account.address),
                "chainId": w3.eth.chain_id,
            }
        )
        signed = account.sign_transaction(transaction)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
    except Exception as error:
        if is_funds_error(error):
            raise DeployError(
                "Not enough Sepolia ETH to pay for gas."
            ) from error
        raise DeployError(f"Deployment failed: {error}") from error
    if receipt["status"] != 1 or not receipt["contractAddress"]:
        raise DeployError("The deployment transaction was reverted.")
    return DeploymentResult(
        address=str(receipt["contractAddress"]),
        tx_hash="0x" + bytes(tx_hash).hex().removeprefix("0x"),
        block_number=int(receipt["blockNumber"]),
        gas_used=int(receipt["gasUsed"]),
        deployer=account.address,
        chain_id=int(w3.eth.chain_id),
    )


def write_json(path: Path, data: Any) -> None:
    """Write pretty JSON, creating the folder if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def write_artifacts(
    result: DeploymentResult,
    compiled: CompiledContract,
    settings: Settings,
    artifact_path: Path,
    website_config_path: Path,
) -> None:
    """
    Save the latest deployment for the mint TUI and the website.
    Only public data: no key and no RPC URL (it may contain an API key).
    The permanent deployment record (deployment/permanent.json) is never
    touched by this script.
    """
    write_json(
        artifact_path,
        {
            "contract": "Windmill42",
            "network": "sepolia",
            "chainId": result.chain_id,
            "address": result.address,
            "txHash": result.tx_hash,
            "blockNumber": result.block_number,
            "deployer": result.deployer,
            "imageURI": settings.image_uri,
            "abi": compiled.abi,
        },
    )
    write_json(
        website_config_path,
        {
            "address": result.address,
            "chainId": result.chain_id,
            "abi": compiled.abi,
            "imageGatewayURL": settings.image_gateway_url,
        },
    )


def save_contract_address(env_path: Path, address: str) -> None:
    """Write CONTRACT_ADDRESS=<address> into the .env file."""
    set_key(str(env_path), "CONTRACT_ADDRESS", address, quote_mode="never")


def ask(question: str, default: bool) -> bool:
    """Yes/no question; Enter keeps the default, Ctrl-D answers no."""
    hint = "[Y/n]" if default else "[y/N]"
    try:
        answer = console.input(f"{question} {escape(hint)} ").strip().lower()
    except EOFError:
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def step(number: int, text: str) -> None:
    """Print a step title like "[3/7] Compiling"."""
    console.print(
        f"[bold yellow]{escape(f'[{number}/{TOTAL_STEPS}]')}[/] {text}"
    )


def done(text: str) -> None:
    """Print a success line under a step."""
    console.print(f"      [green]✓[/] {text}")


def run(assume_yes: bool) -> None:
    """The deployment, step by step. Raises DeployError/CompileError."""
    step(1, "Loading configuration")
    load_dotenv(ENV_PATH)
    settings = load_settings(os.environ, IPFS_RECORD_PATH, PNG_PATH)
    account: LocalAccount = Account.from_key(settings.private_key)
    done(f"image: {settings.image_uri}")
    done(f"shown by wallets at: {settings.image_gateway_url}")
    check_image_link(settings.image_gateway_url)
    done("the image link answers")

    step(2, "Connecting to Sepolia")
    w3 = connect(settings.rpc_url)
    balance = w3.eth.get_balance(account.address)
    done(f"deployer: {account.address}")
    done(f"balance : {format_eth(balance)} (Sepolia)")

    step(3, "Checking the Solidity compiler")
    ensure_solc()
    done(f"solc {SOLC_VERSION}")

    step(4, "Compiling code/Windmill42.sol")
    compiled = compile_windmill42()
    size = len(bytes.fromhex(compiled.runtime_bytecode))
    done(f"Windmill42 compiled ({size} bytes on-chain)")

    step(5, "Estimating the deployment cost")
    cost = estimate_cost_wei(
        w3, account, compiled, settings.image_cid, settings.image_gateway
    )
    done(f"~{format_eth(cost)} (Sepolia)")
    if not assume_yes and not ask("Deploy Windmill42 to Sepolia?", False):
        console.print("[yellow]Cancelled: nothing was deployed.[/]")
        return

    step(6, "Deploying (waiting for the transaction to be mined)")
    result = deploy_contract(
        w3, account, compiled, settings.image_cid, settings.image_gateway
    )
    done(f"contract: [bold green]{result.address}[/]")
    done(f"tx hash : {result.tx_hash}")
    done(f"block {result.block_number}, gas used {result.gas_used}")

    step(7, "Saving the address and ABI")
    write_artifacts(
        result, compiled, settings, ARTIFACT_PATH, WEBSITE_CONFIG_PATH
    )
    done(str(ARTIFACT_PATH.relative_to(REPO_ROOT)))
    done(str(WEBSITE_CONFIG_PATH.relative_to(REPO_ROOT)))
    if assume_yes or ask("Save CONTRACT_ADDRESS to .env?", True):
        save_contract_address(ENV_PATH, result.address)
        done("CONTRACT_ADDRESS saved to .env")

    console.print(
        f"\n[bold green]Windmill42 is live on Sepolia![/]\n"
        f"  {ETHERSCAN}/address/{result.address}\n"
        "  Next: mint with `python mint/mint_tui.py`"
    )


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns the process exit code; never a traceback."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument(
        "--yes", action="store_true", help="do not ask for confirmation"
    )
    args = parser.parse_args(argv)
    try:
        run(args.yes)
    except (DeployError, CompileError) as error:
        console.print(f"[bold red]✗ {escape(str(error))}[/]")
        return 1
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/]")
        return 130
    except Exception as error:  # never show a traceback to the user
        console.print(f"[bold red]✗ Unexpected error: {escape(str(error))}[/]")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
