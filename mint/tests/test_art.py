"""
The Windmill42 artwork files agree with each other.

The artwork exists in three committed forms:
- mint/art/windmill42.png      1024x1024 PNG pinned on IPFS
- mint/art/windmill42.svg      the exact SVG the contract rebuilds on-chain
- code/Windmill42ArtData.sol   palette + run-length pixels stored on-chain
These tests prove all three are the same 64x64 image.
"""

import re
from pathlib import Path

import pytest
from PIL import Image

from svg_pixels import svg_to_grid

REPO_ROOT = Path(__file__).resolve().parents[2]
PNG_PATH = REPO_ROOT / "mint/art/windmill42.png"
SVG_PATH = REPO_ROOT / "mint/art/windmill42.svg"
DATA_PATH = REPO_ROOT / "code/Windmill42ArtData.sol"

SVG_HEADER = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64' "
    "shape-rendering='crispEdges'>"
)


def png_grid() -> list[list[str]]:
    """Colour at the centre of each 16x16 block of the PNG."""
    with Image.open(PNG_PATH) as image:
        rgb = image.convert("RGB")
        grid = []
        for y in range(64):
            row = []
            for x in range(64):
                pixel = rgb.getpixel((x * 16 + 8, y * 16 + 8))
                assert isinstance(pixel, tuple)
                row.append("#{:02x}{:02x}{:02x}".format(*pixel[:3]))
            grid.append(row)
        return grid


def data_palette_and_runs() -> tuple[list[str], list[tuple[int, ...]]]:
    """Decode PALETTE and RUNS from the Solidity data file."""
    source = DATA_PATH.read_text(encoding="utf-8")
    palette_match = re.search(r'PALETTE = hex"([0-9a-f]*)"', source)
    runs_match = re.search(r'RUNS = hex"([0-9a-f]*)"', source)
    assert palette_match and runs_match
    palette_bytes = bytes.fromhex(palette_match.group(1))
    runs_bytes = bytes.fromhex(runs_match.group(1))
    palette = [
        "#" + palette_bytes[i : i + 3].hex()
        for i in range(0, len(palette_bytes), 3)
    ]
    runs = [tuple(runs_bytes[i : i + 4]) for i in range(0, len(runs_bytes), 4)]
    return palette, runs


def runs_to_svg(palette: list[str], runs: list[tuple[int, ...]]) -> str:
    """Rebuild the SVG from the on-chain data, the way the contract does."""
    parts = [SVG_HEADER]
    current = None
    for color, x, y, length in runs:
        if color != current:
            if current is not None:
                parts.append("'/>")
            parts.append(f"<path fill='{palette[color]}' d='")
            current = color
        parts.append(f"M{x} {y}h{length}v1h-{length}z")
    parts.append("'/></svg>")
    return "".join(parts)


def test_png_is_1024_sharp_pixel_art() -> None:
    with Image.open(PNG_PATH) as image:
        rgb = image.convert("RGB")
        assert rgb.size == (1024, 1024)
        # every 16x16 block is a single colour (no blur)
        for y in range(0, 1024, 16):
            for x in range(0, 1024, 16):
                assert rgb.getpixel((x, y)) == rgb.getpixel((x + 15, y + 15))


def test_png_has_at_most_16_colours() -> None:
    assert len({c for row in png_grid() for c in row}) <= 16


def test_svg_format() -> None:
    svg = SVG_PATH.read_text(encoding="utf-8")
    assert svg.startswith(SVG_HEADER)
    assert svg.endswith("'/></svg>")
    assert '"' not in svg  # embeds in JSON without escaping


def test_svg_and_png_are_the_same_image() -> None:
    assert svg_to_grid(SVG_PATH.read_text(encoding="utf-8")) == png_grid()


def test_onchain_data_rebuilds_the_exact_svg() -> None:
    palette, runs = data_palette_and_runs()
    assert len(palette) <= 16
    assert runs_to_svg(palette, runs) == SVG_PATH.read_text(encoding="utf-8")


def test_onchain_runs_sorted_and_within_budget() -> None:
    _, runs = data_palette_and_runs()
    keys = [(c, y, x) for c, x, y, _ in runs]
    assert keys == sorted(keys)
    assert len(runs) <= 2000


def test_data_file_header() -> None:
    source = DATA_PATH.read_text(encoding="utf-8")
    assert source.startswith("// SPDX-License-Identifier: MIT\n")
    assert "pragma solidity ^0.8.35;" in source
    assert "library Windmill42ArtData" in source
    assert "uint256 internal constant SIZE = 64;" in source


def test_42_is_drawn_in_white_clouds() -> None:
    # the cloud "42" covers this area: plenty of white pixels in it
    grid = png_grid()
    white = sum(
        grid[y][x] == "#ffffff" for y in range(5, 25) for x in range(5, 41)
    )
    assert white >= 300


def test_svg_to_grid_small_example() -> None:
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 2 2' "
        "shape-rendering='crispEdges'>"
        "<path fill='#000000' d='M0 0h2v1h-2z'/>"
        "<path fill='#ffffff' d='M0 1h2v1h-2z'/></svg>"
    )
    assert svg_to_grid(svg, size=2) == [
        ["#000000", "#000000"],
        ["#ffffff", "#ffffff"],
    ]


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "<svg></svg>",
        SVG_HEADER + "<path fill='#000000' d='M0 0h64v1h-64z'/></svg>",
        SVG_HEADER + "<path fill='#000000' d='M60 0h9v1h-9z'/></svg>",
        "not an svg at all",
    ],
)
def test_svg_to_grid_rejects_garbage(bad: str) -> None:
    with pytest.raises(ValueError):
        svg_to_grid(bad)
