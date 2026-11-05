"""
Draw the 64x64 artwork in a terminal.

Each character cell shows two pixels stacked vertically: the "▀" glyph is
painted with the top pixel as foreground colour and the bottom pixel as
background colour, so 64x64 pixels fit in 64 columns x 32 rows.
"""

from io import BytesIO

from PIL import Image, UnidentifiedImageError
from rich.text import Text

Grid = list[list[str]]


def grid_to_text(grid: Grid) -> Text:
    """Rich Text of the image: one "▀" per pair of vertical pixels."""
    text = Text()
    for y in range(0, len(grid), 2):
        if y:
            text.append("\n")
        top_row = grid[y]
        bottom_row = grid[y + 1] if y + 1 < len(grid) else top_row
        for top, bottom in zip(top_row, bottom_row):
            text.append("▀", style=f"{top} on {bottom}")
    return text


def png_to_grid(png: bytes, size: int = 64) -> Grid:
    """
    Read an upscaled pixel-art PNG back into `size` x `size` colours,
    sampling the centre of each block.

    Raises:
        ValueError: if the bytes are not a readable image.
    """
    try:
        with Image.open(BytesIO(png)) as image:
            rgb = image.convert("RGB")
    except (UnidentifiedImageError, OSError) as error:
        raise ValueError("The downloaded file is not an image.") from error
    block_w, block_h = rgb.width / size, rgb.height / size
    grid: Grid = []
    for y in range(size):
        row = []
        for x in range(size):
            pixel = rgb.getpixel(
                (int((x + 0.5) * block_w), int((y + 0.5) * block_h))
            )
            assert isinstance(pixel, tuple)
            row.append("#{:02x}{:02x}{:02x}".format(*pixel[:3]))
        grid.append(row)
    return grid
