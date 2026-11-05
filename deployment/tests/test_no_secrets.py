"""
No secret may ever be committed: the evaluation stops if an API key or
password is found in a file. These tests scan every git-tracked file.
"""

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

PRIVATE_KEY_ASSIGNMENT = re.compile(
    r"PRIVATE_KEY\s*=\s*['\"]?(0x)?[0-9a-fA-F]{64}"
)
JWT = re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}")
RPC_API_KEY = re.compile(
    r"(infura\.io/v3/|alchemy\.com/v2/|quiknode\.pro/)[A-Za-z0-9_-]{10,}"
)


def tracked_text_files() -> list[tuple[str, str]]:
    """Return (path, content) for every tracked file that is text."""
    names = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        text=True,
    ).stdout.split("\0")
    files = []
    for name in filter(None, names):
        path = REPO_ROOT / name
        if not path.is_file():
            continue
        try:
            files.append((name, path.read_text(encoding="utf-8")))
        except UnicodeDecodeError:
            continue  # binary file (images, PDFs)
    return files


def test_no_private_key_values_committed() -> None:
    offenders = [
        f"{name}:{number}"
        for name, text in tracked_text_files()
        for number, line in enumerate(text.splitlines(), 1)
        if PRIVATE_KEY_ASSIGNMENT.search(line)
    ]
    assert offenders == []


def test_no_jwt_committed() -> None:
    offenders = [n for n, text in tracked_text_files() if JWT.search(text)]
    assert offenders == []


def test_no_rpc_api_keys_committed() -> None:
    offenders = [
        n for n, text in tracked_text_files() if RPC_API_KEY.search(text)
    ]
    assert offenders == []


def test_env_is_ignored() -> None:
    result = subprocess.run(
        ["git", "check-ignore", ".env"], cwd=REPO_ROOT, capture_output=True
    )
    assert result.returncode == 0
