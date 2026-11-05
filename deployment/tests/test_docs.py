"""Checks that the README and documentation match the project."""

import re
import subprocess
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS = REPO_ROOT / "documentation"
REFERENCE = DOCS / "7_contract_reference.md"
README = REPO_ROOT / "README.md"


def tracked_files() -> list[str]:
    """Files committed (or staged) in git."""
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.splitlines()


def documented_names() -> set[str]:
    """Names of the "### `name`" headings of the contract reference."""
    text = REFERENCE.read_text(encoding="utf-8")
    return set(re.findall(r"^### `(\w+)`", text, flags=re.MULTILINE))


def test_every_documented_function_exists(compiled: Any) -> None:
    documented = documented_names()
    in_abi = {
        entry["name"]
        for entry in compiled.abi
        if entry["type"] in ("function", "error", "event")
    }
    assert documented, "no ### `name` headings found"
    assert documented <= in_abi, f"not in the ABI: {documented - in_abi}"
    must_document = {
        entry["name"]
        for entry in compiled.abi
        if entry["type"] in ("function", "error")
    }
    missing = must_document - documented
    assert not missing, f"undocumented: {sorted(missing)}"


def test_readme_mentions_network_and_choices() -> None:
    text = README.read_text(encoding="utf-8")
    for word in ("Sepolia", "ERC-721", "Solidity", "Python", "IPFS"):
        assert word in text, word


def test_docs_exist_and_are_linked_from_readme() -> None:
    readme = README.read_text(encoding="utf-8")
    docs = sorted(DOCS.glob("[1-9]_*.md"))
    assert len(docs) == 9
    for doc in docs:
        assert doc.read_text(encoding="utf-8").strip()
        assert f"documentation/{doc.name}" in readme, doc.name


def test_required_folders_not_empty() -> None:
    files = tracked_files()
    for folder in ("code", "deployment", "mint", "documentation"):
        assert any(f.startswith(f"{folder}/") for f in files), folder
    assert "README.md" in files


def test_no_video_files() -> None:
    videos = (".mp4", ".mov", ".webm", ".avi", ".mkv")
    assert [f for f in tracked_files() if f.lower().endswith(videos)] == []
