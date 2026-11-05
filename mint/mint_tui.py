#! /usr/bin/env python3
"""
Windmill42 mint TUI - mint, inspect and show the NFT from a terminal.

Connects to Sepolia with the settings of the root .env file:
  SEPOLIA_RPC_URL   node to talk to
  PRIVATE_KEY       wallet used to mint / transfer (optional: read-only)
  CONTRACT_ADDRESS  Windmill42 contract (else the latest deployment)

Usage (in the container):  python mint/mint_tui.py
"""

import json
import os
import re
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Mapping

import readchar
import requests
from dotenv import load_dotenv, set_key
from eth_account import Account
from eth_account.signers.local import LocalAccount
from pyperclip import copy as clipboard_copy
from rich import box
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from web3 import Web3

from nft_client import (
    ClientError,
    ContractInfo,
    Windmill42Client,
    to_address,
)
from terminal_image import grid_to_text, png_to_grid

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = REPO_ROOT / ".env"
ABI_PATH = REPO_ROOT / "mint/Windmill42.abi.json"
ARTIFACT_PATH = REPO_ROOT / "deployment/artifacts/Windmill42.json"

DEFAULT_RPC = "https://ethereum-sepolia-rpc.publicnode.com"
ETHERSCAN = "https://sepolia.etherscan.io"
# Largest image the `ipfs` command downloads.
MAX_IMAGE_BYTES = 2 * 1024 * 1024
# The image panel needs 66x34 cells next to the info panel.
MIN_IMAGE_SIZE = (110, 36)
TOKEN_ID_ERROR = "Token ID must be a whole number between 1 and 42."

console = Console()


@dataclass
class Session:
    """Everything the TUI shows, updated by the commands."""

    client: Windmill42Client
    info: ContractInfo | None = None
    balance: Decimal | None = None
    last_tx: str = ""
    image: Text | None = None
    image_title: str = ""
    details: Text | None = None
    # Address used by the `hack` demo (None: a random empty wallet)
    stranger: str | None = None


# --------------------------------------------------------------------------
# Input helpers
# --------------------------------------------------------------------------
def parse_token_id(raw: str) -> int:
    """'7' -> 7. Raises ValueError unless it is a whole number 1..42."""
    raw = raw.strip()
    if not re.fullmatch(r"\d{1,3}", raw) or not 1 <= int(raw) <= 42:
        raise ValueError(TOKEN_ID_ERROR)
    return int(raw)


def expect_args(args: list[str], allowed: tuple[int, ...], usage: str) -> None:
    """Raise ValueError("Usage: ...") if the argument count is wrong."""
    if len(args) not in allowed:
        raise ValueError(f"Usage: {usage}")


def load_abi(abi_path: Path) -> list[dict[str, Any]]:
    """The contract ABI committed next to this script."""
    try:
        abi: list[dict[str, Any]] = json.loads(abi_path.read_text("utf-8"))
    except (OSError, ValueError) as error:
        raise ClientError(f"Cannot read the ABI file {abi_path}.") from error
    return abi


def resolve_contract(
    env: Mapping[str, str], artifact_path: Path, abi_path: Path = ABI_PATH
) -> tuple[str, list[dict[str, Any]]]:
    """
    Which contract to use: CONTRACT_ADDRESS from .env, else the address of
    the latest deployment (deployment/artifacts/Windmill42.json).
    """
    abi = load_abi(abi_path)
    address = env.get("CONTRACT_ADDRESS", "").strip()
    if not address and artifact_path.is_file():
        try:
            data = json.loads(artifact_path.read_text("utf-8"))
            address = str(data.get("address", "")).strip()
        except ValueError:
            address = ""
    if not address:
        raise ClientError(
            "No contract address: run `python deployment/deploy.py` or set "
            "CONTRACT_ADDRESS in .env."
        )
    return address, abi


# --------------------------------------------------------------------------
# Commands: each returns the status line (Rich markup)
# --------------------------------------------------------------------------
def refresh_info(session: Session) -> None:
    """Reload the collection info and the wallet balance."""
    session.info = session.client.info()
    if session.client.account is not None:
        session.balance = session.client.eth_balance()


def wallet_address(session: Session) -> str | None:
    account = session.client.account
    return account.address if account is not None else None


def check_image_size(size: tuple[int, int]) -> None:
    width, height = size
    if width < MIN_IMAGE_SIZE[0] or height < MIN_IMAGE_SIZE[1]:
        raise ValueError(
            "Terminal too small for the image: need "
            f"{MIN_IMAGE_SIZE[0]}x{MIN_IMAGE_SIZE[1]}, have {width}x{height}."
        )


def cmd_mint(session: Session, args: list[str], _: tuple[int, int]) -> str:
    expect_args(args, (0, 1), "mint [address]")
    result = session.client.mint(args[0] if args else None)
    session.last_tx = result.tx_hash
    message = f"[bold green]✓ Minted Windmill42 #{result.token_id}[/]"
    # The mint is mined: a failed read below must not hide that.
    try:
        refresh_info(session)
        if result.token_id is not None:
            message += f" → {session.client.owner_of(result.token_id)}"
    except ClientError as error:
        message += f" [yellow](could not refresh: {escape(str(error))})[/]"
    return message


def cmd_owner(session: Session, args: list[str], _: tuple[int, int]) -> str:
    expect_args(args, (1,), "owner <id>")
    token_id = parse_token_id(args[0])
    owner = session.client.owner_of(token_id)
    you = (
        " [bold green](that's you)[/]"
        if owner == wallet_address(session)
        else ""
    )
    return f"[bold green]✓[/] ownerOf({token_id}) = [cyan]{owner}[/]{you}"


def attribute(metadata: dict[str, Any], trait: str) -> str:
    for item in metadata.get("attributes", []):
        if isinstance(item, dict) and item.get("trait_type") == trait:
            return str(item.get("value", ""))
    return "?"


def cmd_uri(session: Session, args: list[str], _: tuple[int, int]) -> str:
    expect_args(args, (1,), "uri <id>")
    token_id = parse_token_id(args[0])
    metadata = session.client.metadata(token_id)
    image_data = str(metadata.get("image_data", ""))
    rows = [
        ("name", str(metadata.get("name", "?"))),
        ("artist", str(metadata.get("artist", "?"))),
        ("title", attribute(metadata, "Title")),
        ("edition", attribute(metadata, "Edition")),
        ("image", str(metadata.get("image", "?"))),
        ("image_data", f"<svg …> {len(image_data)} characters, on-chain"),
        ("description", str(metadata.get("description", ""))),
    ]
    details = Text()
    details.append(f"tokenURI({token_id})\n\n", style="bold cyan")
    for key, value in rows:
        details.append(f"{key:<12}", style="bold yellow")
        details.append(f"{value}\n", style="white")
    session.details = details
    session.image = None
    return f"[bold green]✓ Metadata of token #{token_id}[/] (built on-chain)"


def cmd_view(session: Session, args: list[str], size: tuple[int, int]) -> str:
    expect_args(args, (0, 1), "view [id]")
    check_image_size(size)
    label = "the artwork"
    if args:
        token_id = parse_token_id(args[0])
        session.client.owner_of(token_id)  # fails if it does not exist
        label = f"token #{token_id}"
    session.image = grid_to_text(session.client.image_grid())
    session.image_title = "On-chain image (svgImage)"
    session.details = None
    return f"[bold green]✓ {label} drawn from the on-chain data[/]"


def fetch_ipfs_png(url: str) -> bytes:
    """
    Download the pinned image through an IPFS gateway.

    The link comes from the contract, so it is checked: https only, and
    at most MAX_IMAGE_BYTES are read (the real file is about 9 KB).
    """
    if not url.startswith("https://"):
        raise ClientError(f"Refusing to download a non-https link: {url}")
    try:
        response = requests.get(url, timeout=20, stream=True)
    except requests.RequestException as error:
        raise ClientError(
            f"Could not download the image from IPFS ({url})."
        ) from error
    try:
        if response.status_code != 200:
            raise ClientError(
                f"Could not download the image from IPFS "
                f"(HTTP {response.status_code})."
            )
        data = b""
        for chunk in response.iter_content(chunk_size=65536):
            data += chunk
            if len(data) > MAX_IMAGE_BYTES:
                raise ClientError("The IPFS image is too large (over 2 MB).")
        return data
    except requests.RequestException as error:
        raise ClientError(
            f"Could not download the image from IPFS ({url})."
        ) from error
    finally:
        response.close()


def cmd_ipfs(session: Session, args: list[str], size: tuple[int, int]) -> str:
    expect_args(args, (0,), "ipfs")
    check_image_size(size)
    info = session.info or session.client.info()
    url = info.image_url  # the same link wallets use
    grid = png_to_grid(fetch_ipfs_png(url))
    same = grid == session.client.image_grid()
    session.image = grid_to_text(grid)
    session.image_title = f"IPFS image ({url})"
    session.details = None
    if same:
        return "[bold green]✓ IPFS image matches the on-chain image[/]"
    return "[bold yellow]⚠ The IPFS image differs from the on-chain image[/]"


def cmd_hack(session: Session, args: list[str], _: tuple[int, int]) -> str:
    expect_args(args, (0,), "hack")
    answer = session.client.simulate_non_owner_mint(session.stranger)
    refresh_info(session)
    return (
        "🔒 A random wallet tried to mint (simulation, no gas) → "
        f"[bold]{escape(answer)}[/]"
    )


def cmd_send(session: Session, args: list[str], _: tuple[int, int]) -> str:
    expect_args(args, (2,), "send <id> <address>")
    token_id = parse_token_id(args[0])
    receiver = to_address(args[1])
    result = session.client.transfer(token_id, receiver)
    session.last_tx = result.tx_hash
    owner = session.client.owner_of(token_id)
    refresh_info(session)
    return f"[bold green]✓ Token #{token_id} sent[/] → new owner {owner}"


def cmd_refresh(session: Session, args: list[str], _: tuple[int, int]) -> str:
    expect_args(args, (0,), "refresh")
    refresh_info(session)
    return "[bold green]✓ Refreshed[/]"


def copy_text(value: str, label: str) -> str:
    """Copy to the clipboard; inside Docker, show it for manual copy."""
    if not value:
        return f"[bold red]✗ No {label} yet[/]"
    try:
        clipboard_copy(value)
        return f"[bold green]✓ {label} copied[/]"
    except Exception:
        return f"[bold yellow]Copy manually:[/] {value}"


def cmd_adr(session: Session, args: list[str], _: tuple[int, int]) -> str:
    expect_args(args, (0,), "adr")
    return copy_text(str(session.client.contract.address), "contract address")


def cmd_tx(session: Session, args: list[str], _: tuple[int, int]) -> str:
    expect_args(args, (0,), "tx")
    return copy_text(session.last_tx, "transaction hash")


Handler = Callable[[Session, list[str], tuple[int, int]], str]
COMMANDS: dict[str, Handler] = {
    "mint": cmd_mint,
    "owner": cmd_owner,
    "uri": cmd_uri,
    "view": cmd_view,
    "ipfs": cmd_ipfs,
    "hack": cmd_hack,
    "send": cmd_send,
    "refresh": cmd_refresh,
    "adr": cmd_adr,
    "tx": cmd_tx,
}
QUIT_WORDS = ("q", "quit", "exit")


def dispatch(command: str, session: Session, size: tuple[int, int]) -> str:
    """Run one typed command. Never raises: errors become the status."""
    words = command.split()
    if not words:
        return ""
    handler = COMMANDS.get(words[0].lower())
    if handler is None:
        return f"[red]Unknown command:[/] '{escape(command.strip())}'"
    try:
        return handler(session, words[1:], size)
    except (ClientError, ValueError) as error:
        return f"[bold red]✗ {escape(str(error))}[/]"
    except Exception as error:  # last resort: never crash the TUI
        return f"[bold red]✗ Unexpected error: {escape(str(error)[:160])}[/]"


# --------------------------------------------------------------------------
# Screen
# --------------------------------------------------------------------------
def build_info_table(session: Session) -> Table:
    table = Table(box=box.SIMPLE_HEAVY, show_header=False, expand=True)
    table.add_column(style="bold yellow", no_wrap=True)
    table.add_column(style="white", overflow="fold")
    info = session.info
    address = str(session.client.contract.address)
    table.add_row("📜 Contract", f"[cyan]{address}[/]")
    if info is not None:
        # strings read from the contract are shown as text, never markup
        table.add_row("🏷  Collection", escape(f"{info.name} ({info.symbol})"))
        table.add_row("👑 Owner", escape(info.owner))
        table.add_row(
            "🌱 Minted", f"[bold]{info.total_minted}/{info.max_supply}[/]"
        )
        table.add_row("🖼  Image", escape(info.image_uri))
    else:
        table.add_row("", "[red]collection info unavailable[/]")
    wallet = wallet_address(session)
    table.add_section()
    table.add_row(
        "👤 Wallet", wallet or "[yellow]read-only (no PRIVATE_KEY)[/]"
    )
    if session.balance is not None:
        table.add_row("⛽ Balance", f"{session.balance:.5f} SepoliaETH")
    if session.last_tx:
        table.add_row("🔗 Last tx", f"[green]{session.last_tx}[/]")
    table.add_row("🌐 Explorer", f"{ETHERSCAN}/address/{address}")
    return table


def build_menu(input_buffer: str, status: str) -> Text:
    menu = Text()
    rows = [
        ("mint [address]", "mint a token (to you or to an address)"),
        ("owner <id>", "ownerOf: who owns token <id>"),
        ("uri <id>", "tokenURI: the on-chain metadata"),
        ("view [id]", "draw the on-chain image"),
        ("ipfs", "download the IPFS image and compare"),
        ("hack", "security demo: a stranger tries to mint"),
        ("send <id> <address>", "transfer one of your tokens"),
        ("refresh / adr / tx", "reload, copy address / last tx"),
        ("q", "quit"),
    ]
    for command, description in rows:
        menu.append(f"  {command:<20}", style="bold yellow")
        menu.append(f"{description}\n", style="white")
    if status:
        menu.append("\n  → ", style="dim")
        menu.append_text(Text.from_markup(status))
    menu.append("\n\n  > ", style="bold white")
    menu.append(input_buffer, style="bold yellow")
    menu.append("█", style="blink white")
    return menu


def build_layout(
    session: Session, input_buffer: str, status: str, size: tuple[int, int]
) -> Layout:
    """The screen: info + menu on the left, image or details on the right."""
    layout = Layout()
    right_size = 68 if session.image is not None else None
    layout.split_row(
        Layout(name="left", ratio=1),
        Layout(name="right", size=right_size, ratio=1),
    )
    layout["left"].split_column(
        Layout(name="info", size=14), Layout(name="menu", ratio=1)
    )
    layout["info"].update(
        Panel(
            build_info_table(session),
            title="[bold cyan]Windmill42 · Sepolia[/]",
            border_style="cyan",
        )
    )
    layout["menu"].update(
        Panel(
            build_menu(input_buffer, status),
            title="[bold cyan]Menu[/]",
            border_style="cyan",
        )
    )
    if session.image is not None:
        right: Any = Panel(
            session.image,
            title=f"[bold cyan]{escape(session.image_title)}[/]",
            border_style="cyan",
        )
    elif session.details is not None:
        right = Panel(
            session.details,
            title="[bold cyan]Metadata[/]",
            border_style="cyan",
        )
    else:
        right = Panel(
            Group(
                Text('Windmill42 - "Spring Meadow" by flverge\n', "bold"),
                Text("Try `view` to draw the on-chain image,"),
                Text("`mint` to mint a token, `uri 1` for its metadata."),
            ),
            title="[bold cyan]Welcome[/]",
            border_style="cyan",
        )
    layout["right"].update(right)
    return layout


# --------------------------------------------------------------------------
# Start-up and main loop
# --------------------------------------------------------------------------
def prompt_contract_address() -> str:
    """Ask for the contract address (like tokenizer) and save it to .env."""
    console.print("[bold yellow]⚠ No Windmill42 contract address found.[/]")
    console.print(
        "Deploy with `python deployment/deploy.py`, or paste an address."
    )
    while True:
        raw = console.input("[bold cyan]Contract address: [/]").strip()
        try:
            address = to_address(raw)
        except ClientError as error:
            console.print(f"[red]{escape(str(error))}[/]")
            continue
        set_key(str(ENV_PATH), "CONTRACT_ADDRESS", address, quote_mode="never")
        console.print("[green]✓ Saved to .env[/]")
        return address


def load_account(env: Mapping[str, str]) -> LocalAccount | None:
    """The wallet from PRIVATE_KEY, or None (read-only mode)."""
    key = env.get("PRIVATE_KEY", "").strip().removeprefix("0x")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", key):
        return None
    account: LocalAccount = Account.from_key("0x" + key)
    return account


def start_session(env: Mapping[str, str]) -> Session:
    """Connect and load the collection. Raises ClientError on failure."""
    try:
        address, abi = resolve_contract(env, ARTIFACT_PATH)
    except ClientError:
        address, abi = prompt_contract_address(), load_abi(ABI_PATH)
    rpc_url = env.get("SEPOLIA_RPC_URL", "").strip() or DEFAULT_RPC
    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 30}))
    client = Windmill42Client(w3, address, abi, load_account(env))
    session = Session(client=client)
    console.print("[cyan]Connecting to Sepolia...[/]")
    refresh_info(session)
    return session


def run(session: Session) -> None:
    """The interactive loop (same controls as tokenizer's TUI)."""
    status = ""
    if session.client.account is None:
        status = "[yellow]Read-only mode: set PRIVATE_KEY in .env to mint.[/]"
    buffer = ""
    with Live(console=console, screen=True, auto_refresh=False) as live:
        while True:
            size = (console.size.width, console.size.height)
            live.update(
                build_layout(session, buffer, status, size), refresh=True
            )
            key = readchar.readkey()
            if key in (readchar.key.CTRL_C, readchar.key.CTRL_D):
                return
            if key in (readchar.key.ENTER, "\n", "\r"):
                command, buffer = buffer.strip(), ""
                if command.lower() in QUIT_WORDS:
                    return
                working = (
                    "[yellow]⏳ Working (a transaction takes ~15 s)...[/]"
                )
                live.update(
                    build_layout(session, command, working, size), refresh=True
                )
                status = dispatch(command, session, size)
            elif key in (readchar.key.BACKSPACE, "\x7f"):
                buffer = buffer[:-1]
            elif len(key) == 1 and key.isprintable():
                buffer += key


def main() -> int:
    """Entry point. Returns the exit code; never shows a traceback."""
    try:
        load_dotenv(ENV_PATH)
        session = start_session(os.environ)
        run(session)
    except ClientError as error:
        console.print(f"[bold red]✗ {escape(str(error))}[/]")
        return 1
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Interrupted.[/]")
        return 130
    except Exception as error:  # never show a traceback to the user
        console.print(f"[bold red]✗ Unexpected error: {escape(str(error))}[/]")
        return 1
    console.print("[cyan]Bye![/]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
