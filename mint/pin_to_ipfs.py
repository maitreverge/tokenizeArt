#! /usr/bin/env python3
"""
Pin the Windmill42 artwork on IPFS through Pinata.

Uploads mint/art/windmill42.png to the public IPFS network, then writes
mint/ipfs.json with its CID. The CID is public data (not a secret): it is
committed, and deployment/deploy.py reads it to give the contract its
image URI. Only this script needs the PINATA_JWT key.

Usage (in the container):  python mint/pin_to_ipfs.py
"""

import hashlib
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.markup import escape

REPO_ROOT = Path(__file__).resolve().parents[1]
PNG_PATH = REPO_ROOT / "mint/art/windmill42.png"
RECORD_PATH = REPO_ROOT / "mint/ipfs.json"

PINATA_UPLOAD_URL = "https://uploads.pinata.cloud/v3/files"
DEFAULT_GATEWAY = "gateway.pinata.cloud"

console = Console()


class PinError(Exception):
    """The file could not be pinned on IPFS."""


def pin_file(path: Path, jwt: str, timeout: float = 60) -> str:
    """
    Upload `path` to Pinata's public IPFS network.

    Returns:
        str: the IPFS CID of the file.

    Raises:
        PinError: missing JWT or file, network error, refused upload, or a
        response without a CID.
    """
    jwt = jwt.strip()
    if not jwt:
        raise PinError("PINATA_JWT is empty: add your Pinata JWT to .env.")
    if not path.is_file():
        raise PinError(f"File not found: {path}")
    try:
        with path.open("rb") as image:
            response = requests.post(
                PINATA_UPLOAD_URL,
                headers={"Authorization": f"Bearer {jwt}"},
                files={"file": (path.name, image, "image/png")},
                data={"network": "public", "name": path.name},
                timeout=timeout,
            )
    except requests.RequestException as error:
        raise PinError(f"Could not reach Pinata: {error}") from error

    if response.status_code in (401, 403):
        raise PinError(
            f"Pinata refused the upload ({response.status_code}): "
            "check PINATA_JWT in .env."
        )
    if not 200 <= response.status_code < 300:
        raise PinError(
            f"Pinata upload failed ({response.status_code}): "
            f"{response.text[:200]}"
        )
    try:
        cid = response.json()["data"]["cid"]
    except (ValueError, KeyError, TypeError) as error:
        raise PinError("Pinata answered without a CID.") from error
    if not isinstance(cid, str) or not cid:
        raise PinError("Pinata answered without a CID.")
    return cid


def gateway_base(gateway: str) -> str:
    """'my-gw.mypinata.cloud' or 'https://my-gw.../' -> 'https://my-gw...'."""
    domain = gateway.strip().removeprefix("https://").removeprefix("http://")
    return "https://" + domain.strip("/")


def write_record(
    cid: str, png_path: Path, out: Path, gateway: str = DEFAULT_GATEWAY
) -> dict[str, str]:
    """
    Save the pinning result to `out` (mint/ipfs.json) and return it.

    The sha256 lets deploy.py check the pinned file is the current one.
    """
    record = {
        "file": "mint/art/windmill42.png",
        "sha256": hashlib.sha256(png_path.read_bytes()).hexdigest(),
        "cid": cid,
        "imageURI": f"ipfs://{cid}",
        "gatewayURL": f"{gateway_base(gateway)}/ipfs/{cid}",
    }
    out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def main() -> int:
    """Pin the artwork and write mint/ipfs.json. Returns the exit code."""
    try:
        load_dotenv(REPO_ROOT / ".env")
        console.print("[bold cyan]Pinning the Windmill42 artwork on IPFS[/]")
        console.print(f"  file: {PNG_PATH.relative_to(REPO_ROOT)}")
        cid = pin_file(PNG_PATH, os.getenv("PINATA_JWT", ""))
        gateway = os.getenv("PINATA_GATEWAY", "").strip() or DEFAULT_GATEWAY
        record = write_record(cid, PNG_PATH, RECORD_PATH, gateway)
    except PinError as error:
        console.print(f"[bold red]✗ {escape(str(error))}[/]")
        return 1
    except KeyboardInterrupt:
        console.print("[yellow]Interrupted.[/]")
        return 130
    except Exception as error:  # never show a traceback to the user
        console.print(f"[bold red]✗ Unexpected error: {escape(str(error))}[/]")
        return 1
    console.print(f"[bold green]✓ Pinned![/] CID: [cyan]{cid}[/]")
    console.print(f"  image URI : {record['imageURI']}")
    console.print(f"  open it   : {record['gatewayURL']}")
    console.print(f"  saved to  : {RECORD_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
