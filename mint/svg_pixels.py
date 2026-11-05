"""
Turn the Windmill42 SVG (as returned by the contract's svgImage()) back
into a grid of pixel colours.

The SVG has one <path> per colour, and each pixel run is a 1-pixel-high
rectangle written "M{x} {y}h{length}v1h-{length}z".
"""

import re

HEADER = re.compile(
    r"<svg xmlns='http://www\.w3\.org/2000/svg' viewBox='0 0 (\d+) (\d+)' "
    r"shape-rendering='crispEdges'>"
)
PATH = re.compile(
    r"<path fill='(#[0-9a-f]{6})' d='((?:M\d+ \d+h\d+v1h-\d+z)+)'/>"
)
RUN = re.compile(r"M(\d+) (\d+)h(\d+)v1h-(\d+)z")


def svg_to_grid(svg: str, size: int = 64) -> list[list[str]]:
    """
    Parse the SVG into `size` rows of `size` '#rrggbb' colours.

    Raises:
        ValueError: if the SVG is not in the expected format, or if a pixel
        is outside the canvas, painted twice, or never painted.
    """
    header = HEADER.match(svg)
    if not header or header.groups() != (str(size), str(size)):
        raise ValueError("Not a Windmill42 SVG (unexpected header).")
    body = svg[header.end() :]
    if not body.endswith("</svg>"):
        raise ValueError("Not a Windmill42 SVG (missing </svg>).")
    body = body[: -len("</svg>")]

    grid: list[list[str | None]] = [[None] * size for _ in range(size)]
    position = 0
    for path in PATH.finditer(body):
        if path.start() != position:
            raise ValueError("Unexpected content between SVG paths.")
        position = path.end()
        color = path.group(1)
        for run in RUN.finditer(path.group(2)):
            x, y, length, back = (int(value) for value in run.groups())
            if length != back or length == 0:
                raise ValueError("Malformed pixel run in the SVG.")
            if y >= size or x + length > size:
                raise ValueError("Pixel run outside the canvas.")
            for xx in range(x, x + length):
                if grid[y][xx] is not None:
                    raise ValueError("A pixel is painted twice.")
                grid[y][xx] = color
    if position != len(body):
        raise ValueError("Unexpected content in the SVG.")

    result: list[list[str]] = []
    for row in grid:
        if any(cell is None for cell in row):
            raise ValueError("Some pixels are missing from the SVG.")
        result.append([cell for cell in row if cell is not None])
    return result
