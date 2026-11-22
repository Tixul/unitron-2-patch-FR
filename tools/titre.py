# -*- coding: utf-8 -*-
"""Convert the French title PNG and inject it into Unitron 2's SCR2 asset.

The title resource is a 20x19 tilemap followed by a 143-tile LZSS stream and
16 K2GE palettes.  Tile zero stays transparent, so the untouched SCR1 mecha
continues to show through the black pixels of the source PNG.
"""

from __future__ import annotations

import argparse
import struct
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


MAP_OFFSET = 0x17FB44
MAP_WIDTH = 20
MAP_HEIGHT = 19
MAP_BYTES = MAP_WIDTH * MAP_HEIGHT * 2
STREAM_OFFSET = 0x17FE5C
STREAM_END = 0x18048F
STREAM_CAPACITY = STREAM_END - STREAM_OFFSET
PALETTE_OFFSET = 0x18048F
PALETTE_BYTES = 16 * 4 * 2
TILE_COUNT = 143
SCR2_TILE_COUNT = 128
LZSS_WINDOW_SIZE = 0x400
LZSS_WINDOW_MASK = LZSS_WINDOW_SIZE - 1
LZSS_WRITE_START = 0x3EE

SHELL_MAGIC = b"NGPCST01"
SHELL_MEMORY_BYTES = 0xC000
SCR2_MAP_RAM = 0x9800
SCR2_PALETTE_RAM = 0x8300
CHAR_RAM = 0xA000
TITLE_TILE_BASE = 0x150

TRANSPARENT = (0, 0, 0)


@dataclass(frozen=True)
class EncodedTitle:
    tilemap: bytes
    tiles: bytes
    compressed: bytes
    palettes: bytes
    pattern_count: int
    palette_count: int


def _encode_tile(values: tuple[int, ...]) -> bytes:
    """Pack 64 K2GE color indices using the chip's split-byte row order."""
    raw = bytearray()
    for y in range(8):
        row = values[y * 8:(y + 1) * 8]
        odd = sum(row[x] << (6 - x * 2) for x in range(4))
        even = sum(row[x] << (6 - (x - 4) * 2) for x in range(4, 8))
        raw += bytes((even, odd))
    return bytes(raw)


def _palette_word(rgb: tuple[int, int, int]) -> int:
    if any(not 0 <= component <= 255 or component % 17 for component in rgb):
        raise ValueError(f"couleur non representable sur NGPC: {rgb}")
    r, g, b = (component // 17 for component in rgb)
    return r | (g << 4) | (b << 8)


def _match_length(window: bytearray, write_pos: int, source: int,
                  data: bytes, data_pos: int) -> int:
    """Measure an LZSS match, including legal overlapping copies."""
    pending: dict[int, int] = {}
    length = 0
    while length < 18 and data_pos + length < len(data):
        source_pos = (source + length) & LZSS_WINDOW_MASK
        value = pending.get(source_pos, window[source_pos])
        if value != data[data_pos + length]:
            break
        pending[(write_pos + length) & LZSS_WINDOW_MASK] = value
        length += 1
    return length


def compress_lzss(data: bytes) -> bytes:
    """Encode the game's 1 KiB-window LZSS format.

    Flags are consumed least-significant bit first.  A set bit is a literal;
    a clear bit is a 12-bit absolute window position plus a 4-bit length-3.
    Although references carry 12 offset bits, the game masks them to a 1 KiB
    dictionary.  The zero-filled window begins with its cursor at 0x3EE.
    """
    window = bytearray(LZSS_WINDOW_SIZE)
    write_pos = LZSS_WRITE_START
    data_pos = 0
    encoded = bytearray()

    while data_pos < len(data):
        flag_pos = len(encoded)
        encoded.append(0)
        flags = 0
        for bit in range(8):
            if data_pos >= len(data):
                break
            best_source = 0
            best_length = 0
            first = data[data_pos]
            for source, value in enumerate(window):
                if value != first:
                    continue
                length = _match_length(window, write_pos, source, data, data_pos)
                if length > best_length:
                    best_source, best_length = source, length
                    if length == 18:
                        break
            if best_length >= 3:
                encoded += bytes((
                    best_source & 0xFF,
                    ((best_source >> 4) & 0xF0) | (best_length - 3),
                ))
                for value in data[data_pos:data_pos + best_length]:
                    window[write_pos] = value
                    write_pos = (write_pos + 1) & LZSS_WINDOW_MASK
                data_pos += best_length
            else:
                flags |= 1 << bit
                value = data[data_pos]
                encoded.append(value)
                window[write_pos] = value
                write_pos = (write_pos + 1) & LZSS_WINDOW_MASK
                data_pos += 1
        encoded[flag_pos] = flags
    return bytes(encoded)


def decompress_lzss(data: bytes, output_size: int) -> bytes:
    """Reference decoder used to prove the encoder before touching the ROM."""
    window = bytearray(LZSS_WINDOW_SIZE)
    write_pos = LZSS_WRITE_START
    source_pos = 0
    output = bytearray()
    while len(output) < output_size:
        flags = data[source_pos]
        source_pos += 1
        for bit in range(8):
            if flags & (1 << bit):
                value = data[source_pos]
                source_pos += 1
                output.append(value)
                window[write_pos] = value
                write_pos = (write_pos + 1) & LZSS_WINDOW_MASK
            else:
                lo, hi = data[source_pos:source_pos + 2]
                source_pos += 2
                match_pos = (lo | ((hi & 0xF0) << 4)) & LZSS_WINDOW_MASK
                length = (hi & 0x0F) + 3
                for offset in range(length):
                    value = window[(match_pos + offset) & LZSS_WINDOW_MASK]
                    output.append(value)
                    window[write_pos] = value
                    write_pos = (write_pos + 1) & LZSS_WINDOW_MASK
                    if len(output) == output_size:
                        break
            if len(output) == output_size:
                break
    return bytes(output)


def encode_title(png_path: Path) -> EncodedTitle:
    image = Image.open(png_path).convert("RGB")
    if image.size != (MAP_WIDTH * 8, MAP_HEIGHT * 8):
        raise ValueError(f"PNG attendu en 160x152, recu {image.size[0]}x{image.size[1]}")

    patterns: list[bytes] = []
    palette_sets: list[tuple[tuple[int, int, int], ...]] = []
    entries: list[int] = []

    for tile_y in range(MAP_HEIGHT):
        for tile_x in range(MAP_WIDTH):
            pixels = tuple(image.crop((
                tile_x * 8, tile_y * 8, tile_x * 8 + 8, tile_y * 8 + 8,
            )).getdata())
            visible = tuple(sorted(set(pixels) - {TRANSPARENT}))
            if not visible:
                entries.append(0)
                continue
            if len(visible) > 3:
                counts = Counter(pixels)
                raise ValueError(
                    f"tuile ({tile_x},{tile_y}): {len(visible)} couleurs visibles: "
                    f"{dict(counts)}"
                )
            if visible not in palette_sets:
                palette_sets.append(visible)
            palette_id = palette_sets.index(visible)
            indices = tuple(0 if color == TRANSPARENT else visible.index(color) + 1
                            for color in pixels)
            pattern = _encode_tile(indices)
            if pattern not in patterns:
                patterns.append(pattern)
            tile_id = patterns.index(pattern) + 1
            entries.append(tile_id | (palette_id << 9))

    if len(patterns) > SCR2_TILE_COUNT:
        raise ValueError(f"{len(patterns)} motifs SCR2 pour {SCR2_TILE_COUNT} emplacements")
    if len(palette_sets) > 16:
        raise ValueError(f"{len(palette_sets)} palettes pour 16 emplacements")

    tilemap = b"".join(struct.pack("<H", entry) for entry in entries)
    # Relative tile IDs 0x81..0x8F belong to the title's sprite strip
    # ("PRESS A BUTTON"), not SCR2.  The ROM patcher preserves those final
    # 15 patterns from the original stream.  This payload owns only 1..0x80.
    tiles = b"".join(patterns) + bytes((SCR2_TILE_COUNT - len(patterns)) * 16)
    compressed = compress_lzss(tiles)
    if decompress_lzss(compressed, len(tiles)) != tiles:
        raise AssertionError("le flux LZSS ne se redecompresse pas a l'identique")
    if len(compressed) > STREAM_CAPACITY:
        raise ValueError(
            f"flux compresse trop grand: {len(compressed)} > {STREAM_CAPACITY} octets"
        )

    palettes = bytearray(PALETTE_BYTES)
    for palette_id, colors in enumerate(palette_sets):
        for color_id, color in enumerate(colors, 1):
            struct.pack_into("<H", palettes, (palette_id * 4 + color_id) * 2,
                             _palette_word(color))

    return EncodedTitle(
        tilemap=tilemap,
        tiles=tiles,
        compressed=compressed,
        palettes=bytes(palettes),
        pattern_count=len(patterns),
        palette_count=len(palette_sets),
    )


def patch_rom_bytes(rom: bytearray, title: EncodedTitle) -> tuple[int, int]:
    if len(rom) < PALETTE_OFFSET + PALETTE_BYTES:
        raise ValueError("ROM trop courte pour contenir l'asset titre")
    original_tiles = decompress_lzss(
        bytes(rom[STREAM_OFFSET:STREAM_END]), TILE_COUNT * 16,
    )
    sprite_tiles = original_tiles[SCR2_TILE_COUNT * 16:]
    combined_tiles = title.tiles + sprite_tiles
    compressed = compress_lzss(combined_tiles)
    if decompress_lzss(compressed, len(combined_tiles)) != combined_tiles:
        raise AssertionError("le flux final ne se redecompresse pas a l'identique")
    if len(compressed) > STREAM_CAPACITY:
        raise ValueError(
            f"flux final trop grand: {len(compressed)} > {STREAM_CAPACITY} octets"
        )

    rom[MAP_OFFSET:MAP_OFFSET + MAP_BYTES] = title.tilemap
    rom[STREAM_OFFSET:STREAM_END] = compressed.ljust(STREAM_CAPACITY, b"\x00")
    rom[PALETTE_OFFSET:PALETTE_OFFSET + PALETTE_BYTES] = title.palettes
    return len(compressed), len(sprite_tiles) // 16


def patch_savestate_bytes(blob: bytearray, title: EncodedTitle) -> None:
    if not blob.startswith(SHELL_MAGIC):
        raise ValueError("savestate NGPCST01 attendue")
    memory_start = len(blob) - SHELL_MEMORY_BYTES
    if memory_start <= len(SHELL_MAGIC):
        raise ValueError("savestate tronquee")

    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            source_entry = struct.unpack_from("<H", title.tilemap, (y * MAP_WIDTH + x) * 2)[0]
            tile_id = source_entry & 0x1FF
            runtime_entry = source_entry
            if tile_id:
                runtime_entry = (source_entry & ~0x1FF) | (TITLE_TILE_BASE + tile_id)
            struct.pack_into("<H", blob, memory_start + SCR2_MAP_RAM + (y * 32 + x) * 2,
                             runtime_entry)

    blob[memory_start + SCR2_PALETTE_RAM:
         memory_start + SCR2_PALETTE_RAM + PALETTE_BYTES] = title.palettes
    tile_start = memory_start + CHAR_RAM + (TITLE_TILE_BASE + 1) * 16
    # Stop before relative tile 0x81: the remaining patterns feed the title
    # sprites and must stay exactly as captured in the savestate.
    blob[tile_start:tile_start + len(title.tiles)] = title.tiles


def main() -> None:
    here = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--png", type=Path, default=here / "refs" / "graphx_fr" /
                        "Kikouseki_Unitron_(J)_s4_scr2.png")
    parser.add_argument("--rom-in", type=Path)
    parser.add_argument("--rom-out", type=Path)
    parser.add_argument("--state-in", type=Path)
    parser.add_argument("--state-out", type=Path)
    args = parser.parse_args()

    title = encode_title(args.png)
    print(f"titre SCR2: {title.pattern_count}/{SCR2_TILE_COUNT} motifs, "
          f"{title.palette_count}/16 palettes, "
          f"LZSS {len(title.compressed)}/{STREAM_CAPACITY} octets")

    if bool(args.rom_in) != bool(args.rom_out):
        parser.error("--rom-in et --rom-out doivent etre fournis ensemble")
    if bool(args.state_in) != bool(args.state_out):
        parser.error("--state-in et --state-out doivent etre fournis ensemble")
    if args.rom_in:
        rom = bytearray(args.rom_in.read_bytes())
        final_size, preserved = patch_rom_bytes(rom, title)
        args.rom_out.parent.mkdir(parents=True, exist_ok=True)
        args.rom_out.write_bytes(rom)
        print(f"ROM ecrite: {args.rom_out} (LZSS final {final_size}/{STREAM_CAPACITY}, "
              f"{preserved} tuiles sprites preservees)")
    if args.state_in:
        state = bytearray(args.state_in.read_bytes())
        patch_savestate_bytes(state, title)
        args.state_out.parent.mkdir(parents=True, exist_ok=True)
        args.state_out.write_bytes(state)
        print(f"savestate ecrite: {args.state_out}")


if __name__ == "__main__":
    main()
