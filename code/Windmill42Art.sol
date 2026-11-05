// SPDX-License-Identifier: MIT
pragma solidity ^0.8.35;

import "./Windmill42ArtData.sol";

/**
 * @title Windmill42Art
 * @author flverge
 * @notice Rebuilds the Windmill42 artwork as an SVG image, entirely
 *         on-chain, from the pixel data stored in Windmill42ArtData.
 * @dev The SVG has one <path> per colour; every horizontal run of
 *      pixels becomes a 1-pixel-high rectangle "M{x} {y}h{n}v1h-{n}z".
 *      The text is written into one pre-allocated buffer (linear cost):
 *      concatenating strings in a loop would copy the whole text again
 *      at every step and quickly exceed the gas limit of a node.
 */
library Windmill42Art {
    bytes16 private constant HEX_DIGITS = "0123456789abcdef";

    /// @notice The full SVG image, ready to embed in JSON (single quotes).
    function svg() internal pure returns (string memory) {
        bytes memory palette = Windmill42ArtData.PALETTE;
        bytes memory runs = Windmill42ArtData.RUNS;
        uint256 colorCount = palette.length / 3;
        uint256 runCount = runs.length / 4;

        // Upper bound of the SVG length: header/footer, one <path> wrapper
        // per colour (< 32 bytes) and at most 16 bytes per run
        // ("M63 63h64v1h-64z").
        bytes memory buffer = new bytes(256 + colorCount * 32 + runCount * 16);
        uint256 cursor = 0;

        cursor = _write(buffer, cursor, "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 ");
        cursor = _writeNumber(buffer, cursor, Windmill42ArtData.SIZE);
        cursor = _write(buffer, cursor, " ");
        cursor = _writeNumber(buffer, cursor, Windmill42ArtData.SIZE);
        cursor = _write(buffer, cursor, "' shape-rendering='crispEdges'>");

        uint256 currentColor = type(uint256).max; // "no path open yet"
        for (uint256 i = 0; i < runs.length; i += 4) {
            uint256 color = uint8(runs[i]);
            if (color != currentColor) {
                if (currentColor != type(uint256).max) {
                    cursor = _write(buffer, cursor, "'/>");
                }
                cursor = _write(buffer, cursor, "<path fill='#");
                cursor = _writeColor(buffer, cursor, palette, color);
                cursor = _write(buffer, cursor, "' d='");
                currentColor = color;
            }
            cursor = _writeRun(
                buffer,
                cursor,
                uint8(runs[i + 1]), // x
                uint8(runs[i + 2]), // y
                uint8(runs[i + 3]) // length
            );
        }
        cursor = _write(buffer, cursor, "'/></svg>");

        // Shrink the buffer to the number of bytes actually written.
        assembly ("memory-safe") {
            mstore(buffer, cursor)
        }
        return string(buffer);
    }

    /// @dev Writes one run as "M{x} {y}h{length}v1h-{length}z".
    function _writeRun(
        bytes memory buffer,
        uint256 cursor,
        uint256 x,
        uint256 y,
        uint256 length
    ) private pure returns (uint256) {
        cursor = _write(buffer, cursor, "M");
        cursor = _writeNumber(buffer, cursor, x);
        cursor = _write(buffer, cursor, " ");
        cursor = _writeNumber(buffer, cursor, y);
        cursor = _write(buffer, cursor, "h");
        cursor = _writeNumber(buffer, cursor, length);
        cursor = _write(buffer, cursor, "v1h-");
        cursor = _writeNumber(buffer, cursor, length);
        return _write(buffer, cursor, "z");
    }

    /// @dev Copies `text` into `buffer` at `cursor`; returns the new cursor.
    function _write(bytes memory buffer, uint256 cursor, string memory text)
        private
        pure
        returns (uint256)
    {
        bytes memory source = bytes(text);
        for (uint256 i = 0; i < source.length; i++) {
            buffer[cursor++] = source[i];
        }
        return cursor;
    }

    /// @dev Writes a number from 0 to 99 in decimal, without padding.
    function _writeNumber(bytes memory buffer, uint256 cursor, uint256 value)
        private
        pure
        returns (uint256)
    {
        if (value >= 10) {
            buffer[cursor++] = bytes1(uint8(48 + value / 10));
        }
        buffer[cursor++] = bytes1(uint8(48 + (value % 10)));
        return cursor;
    }

    /// @dev Writes palette colour `index` as 6 lowercase hex digits.
    function _writeColor(
        bytes memory buffer,
        uint256 cursor,
        bytes memory palette,
        uint256 index
    ) private pure returns (uint256) {
        for (uint256 i = 0; i < 3; i++) {
            uint8 channel = uint8(palette[index * 3 + i]);
            buffer[cursor++] = HEX_DIGITS[channel >> 4];
            buffer[cursor++] = HEX_DIGITS[channel & 0x0f];
        }
        return cursor;
    }
}
