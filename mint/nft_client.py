"""
Talk to a deployed Windmill42 contract with web3.py.

Used by the mint TUI. Every public method raises only ClientError, whose
message is a short sentence ready to show to the user.
"""

import ast
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import requests
from eth_account import Account
from eth_account.signers.local import LocalAccount
from eth_typing import ChecksumAddress
from web3 import Web3
from web3.exceptions import BadFunctionCallOutput
from web3.logs import DISCARD

from metadata import decode_token_uri
from svg_pixels import svg_to_grid

# Custom errors of the contract (and OpenZeppelin) -> message for humans.
FRIENDLY_ERRORS = {
    "OwnableUnauthorizedAccount": "Only the contract owner can mint.",
    "MaxSupplyReached": "All 42 Windmill42 tokens are already minted.",
    "ERC721NonexistentToken": "This token does not exist (yet).",
    "ERC721IncorrectOwner": "Your wallet does not own this token.",
    "ERC721InsufficientApproval": "Your wallet does not own this token.",
    "ERC721InvalidReceiver": "This address cannot receive NFTs.",
    "OwnableInvalidOwner": "This address cannot become the owner.",
}
NO_FUNDS = "Not enough Sepolia ETH to pay for gas."
UNREACHABLE = "Could not reach the Sepolia node: check SEPOLIA_RPC_URL."
NO_CONTRACT = (
    "No Windmill42 contract at this address on this network: "
    "check CONTRACT_ADDRESS."
)


class ClientError(Exception):
    """A failure explained in one sentence for the user."""


@dataclass(frozen=True)
class ContractInfo:
    """Public state of the collection."""

    address: str
    name: str
    symbol: str
    owner: str
    total_minted: int
    max_supply: int
    image_uri: str  # "ipfs://<CID>"
    image_url: str  # https link to the same file, shown by wallets


@dataclass(frozen=True)
class TxResult:
    """A mined transaction (token_id is set for mints)."""

    tx_hash: str
    token_id: int | None


def revert_data(error: BaseException) -> str:
    """
    Hex revert data of a failed call, without "0x".

    A real node gives it as `error.data` ("0x..."); the local test chain
    puts it in the message as a bytes literal ("execution reverted: b'..'").
    """
    data = getattr(error, "data", None)
    if isinstance(data, str):
        return data.removeprefix("0x").lower()
    for arg in error.args:
        text = str(arg)
        literal = re.search(r"b(['\"]).*\1", text)
        if literal:
            try:
                value = ast.literal_eval(literal.group(0))
            except (ValueError, SyntaxError):
                value = None
            if isinstance(value, bytes):
                return value.hex()
        hex_data = re.search(r"0x([0-9a-fA-F]{8,})", text)
        if hex_data:
            return hex_data.group(1).lower()
    return ""


def decode_revert(error: BaseException, abi: list[dict[str, Any]]) -> str:
    """Name of the Solidity custom error behind `error`, or ""."""
    data = revert_data(error)
    for entry in abi:
        if entry.get("type") != "error":
            continue
        types = ",".join(i["type"] for i in entry.get("inputs", []))
        selector = Web3.keccak(text=f"{entry['name']}({types})")[:4].hex()
        if data and data.startswith(selector.removeprefix("0x")):
            return str(entry["name"])
    return ""


def friendly_error(error: BaseException, abi: list[dict[str, Any]]) -> str:
    """One sentence explaining `error` to the user."""
    name = decode_revert(error, abi)
    if name:
        return FRIENDLY_ERRORS.get(name, f"The contract refused: {name}.")
    text = str(error).lower()
    if "insufficient funds" in text or "cannot afford" in text:
        return NO_FUNDS
    if (
        isinstance(error, BadFunctionCallOutput)
        or "is contract deployed" in text
    ):
        return NO_CONTRACT
    if isinstance(error, (requests.RequestException, OSError)):
        return UNREACHABLE
    if "connection" in text or "max retries" in text:
        return UNREACHABLE
    return f"Unexpected error: {str(error)[:160]}"


def to_address(value: str) -> ChecksumAddress:
    """Validate and checksum an address typed by the user."""
    value = value.strip()
    if not Web3.is_address(value):
        raise ClientError(f"Not a valid Ethereum address: {value!r}")
    return Web3.to_checksum_address(value)


class Windmill42Client:
    """Read and write a Windmill42 contract."""

    def __init__(
        self,
        w3: Web3,
        address: str,
        abi: list[dict[str, Any]],
        account: LocalAccount | None = None,
    ) -> None:
        self.w3 = w3
        self.abi = abi
        self.account = account  # None: read-only mode
        self.contract = w3.eth.contract(address=to_address(address), abi=abi)

    # --- helpers -----------------------------------------------------------
    def _call(self, function: Any) -> Any:
        """Run a read-only contract call."""
        try:
            return function.call()
        except Exception as error:
            raise ClientError(friendly_error(error, self.abi)) from error

    def _require_account(self) -> LocalAccount:
        if self.account is None:
            raise ClientError("No PRIVATE_KEY configured: read-only mode.")
        return self.account

    def _send(self, function: Any) -> tuple[str, Any]:
        """
        Build, sign locally and send a transaction; wait for its block.
        Returns (tx hash, receipt).
        """
        account = self._require_account()
        try:
            transaction = function.build_transaction(
                {
                    "from": account.address,
                    "nonce": self.w3.eth.get_transaction_count(
                        account.address
                    ),
                    "chainId": self.w3.eth.chain_id,
                }
            )
            signed = account.sign_transaction(transaction)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(
                tx_hash, timeout=300
            )
        except ClientError:
            raise
        except Exception as error:
            raise ClientError(friendly_error(error, self.abi)) from error
        if receipt["status"] != 1:
            raise ClientError("The transaction was reverted.")
        return "0x" + bytes(tx_hash).hex().removeprefix("0x"), receipt

    # --- reads -------------------------------------------------------------
    def info(self) -> ContractInfo:
        """Name, symbol, owner, supply and image URI of the collection."""
        f = self.contract.functions
        return ContractInfo(
            address=str(self.contract.address),
            name=self._call(f.name()),
            symbol=self._call(f.symbol()),
            owner=self._call(f.owner()),
            total_minted=self._call(f.totalMinted()),
            max_supply=self._call(f.MAX_SUPPLY()),
            image_uri=self._call(f.imageURI()),
            image_url=self._call(f.imageURL()),
        )

    def eth_balance(self) -> Decimal:
        """SepoliaETH balance of the configured wallet."""
        account = self._require_account()
        try:
            wei = self.w3.eth.get_balance(account.address)
        except Exception as error:
            raise ClientError(friendly_error(error, self.abi)) from error
        return Decimal(wei) / Decimal(10**18)

    def owner_of(self, token_id: int) -> str:
        """Current owner of a token (the ERC-721 ownerOf function)."""
        return str(self._call(self.contract.functions.ownerOf(token_id)))

    def token_uri(self, token_id: int) -> str:
        """Raw tokenURI: base64 JSON metadata built on-chain."""
        return str(self._call(self.contract.functions.tokenURI(token_id)))

    def metadata(self, token_id: int) -> dict[str, Any]:
        """Decoded metadata of a token."""
        try:
            return decode_token_uri(self.token_uri(token_id))
        except ValueError as error:
            raise ClientError(str(error)) from error

    def svg_image(self) -> str:
        """The artwork as rebuilt on-chain by svgImage()."""
        return str(self._call(self.contract.functions.svgImage()))

    def image_grid(self) -> list[list[str]]:
        """The on-chain artwork as 64 rows of 64 '#rrggbb' colours."""
        try:
            return svg_to_grid(self.svg_image())
        except ValueError as error:
            raise ClientError(f"On-chain image unreadable: {error}") from error

    # --- writes ------------------------------------------------------------
    def mint(self, to: str | None = None) -> TxResult:
        """Mint the next token to `to` (default: own wallet). Owner only."""
        account = self._require_account()
        receiver = to_address(to) if to is not None else account.address
        tx_hash, receipt = self._send(self.contract.functions.mint(receiver))
        events = self.contract.events.Transfer().process_receipt(
            receipt, errors=DISCARD
        )
        token_id = next((int(e["args"]["tokenId"]) for e in events), None)
        return TxResult(tx_hash, token_id)

    def transfer(self, token_id: int, to: str) -> TxResult:
        """Send a token owned by the configured wallet to `to`."""
        account = self._require_account()
        receiver = to_address(to)
        function = self.contract.functions.safeTransferFrom(
            account.address, receiver, token_id
        )
        tx_hash, _ = self._send(function)
        return TxResult(tx_hash, token_id)

    def transfer_ownership(self, new_owner: str) -> TxResult:
        """Hand the contract (minting rights) to another address."""
        function = self.contract.functions.transferOwnership(
            to_address(new_owner)
        )
        tx_hash, _ = self._send(function)
        return TxResult(tx_hash, None)

    # --- security demo -----------------------------------------------------
    def simulate_non_owner_mint(self, stranger: str | None = None) -> str:
        """
        Ask the node what would happen if a stranger called mint().
        Nothing is sent and no gas is spent (eth_call simulation).

        Args:
            stranger: address to simulate from; default is a brand-new
                random address (real nodes simulate calls from empty
                wallets; the local test chain needs a funded one).

        Returns:
            str: the contract's answer, e.g. "Only the contract owner can
            mint." (or a warning if the call was NOT rejected).
        """
        stranger = (
            to_address(stranger) if stranger else Account.create().address
        )
        try:
            self.contract.functions.mint(stranger).call({"from": stranger})
        except Exception as error:
            name = decode_revert(error, self.abi)
            if name:
                return FRIENDLY_ERRORS.get(name, name)
            raise ClientError(friendly_error(error, self.abi)) from error
        return "Warning: the mint was NOT rejected!"
