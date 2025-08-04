#!/usr/bin/env python3
"""
Debug script to test sprite pattern data access
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nes import NES


def debug_sprite_patterns():
    """Debug sprite pattern data access"""
    print("Creating NES instance...")
    nes = NES()

    print("Loading ROM...")
    if not nes.load_cartridge("mario.nes"):
        print("Failed to load ROM!")
        return

    print("Resetting NES...")
    nes.reset()

    print("Running until Mario sprite is loaded...")

    # Run until we have Mario sprite data
    for i in range(50):
        screen = nes.step_frame()
        if nes.ppu.oam[0] == 24:  # Mario's Y position
            break

    # Check Mario's data
    mario_y = nes.ppu.oam[0]
    mario_tile = nes.ppu.oam[1]
    mario_attr = nes.ppu.oam[2]
    mario_x = nes.ppu.oam[3]

    print(
        f"Mario sprite: Y={mario_y}, Tile={mario_tile}, Attr={mario_attr}, X={mario_x}"
    )

    # Check pattern table data for Mario's tile
    sprite_height = 16 if nes.ppu.ctrl & nes.ppu.LONG_SPRITE else 8
    table = 1 if nes.ppu.ctrl & nes.ppu.SPRITE_TABLE else 0

    print(f"Sprite table: {table}, Height: {sprite_height}")

    # Check pattern data for each row of Mario's sprite
    for y_offset in range(8):
        tile_addr = table * 0x1000 + mario_tile * 16 + y_offset
        pattern_low = nes.ppu.read_vram(tile_addr)
        pattern_high = nes.ppu.read_vram(tile_addr + 8)

        print(
            f"Y offset {y_offset}: addr=0x{tile_addr:04X}, low=0x{pattern_low:02X}, high=0x{pattern_high:02X}"
        )

        # Decode the pattern for this row
        row_pixels = []
        for x_bit in range(8):
            low_bit = (pattern_low >> (7 - x_bit)) & 1
            high_bit = (pattern_high >> (7 - x_bit)) & 1
            pixel = low_bit | (high_bit << 1)
            row_pixels.append(pixel)

        print(f"  Pixels: {row_pixels}")

    # Now test what happens during actual rendering for each scanline
    print("\nTesting actual rendering:")
    for test_scanline in [24, 25, 26, 27, 28, 29, 30, 31]:
        nes.ppu.scanline = test_scanline
        nes.ppu.evaluate_sprites()

        if nes.ppu.oam_cache_len > 0:
            # Calculate Y offset as the sprite renderer would
            y_offset = test_scanline - mario_y

            print(f"Scanline {test_scanline}: y_offset={y_offset}")

            # Check if this is a valid Y offset
            if 0 <= y_offset < sprite_height:
                # Test rendering at Mario's X position
                nes.ppu.cycle = mario_x + 1  # X coordinate (cycle - 1)
                sprite_info = nes.ppu.render_sprites(0)

                if sprite_info:
                    pixel = sprite_info & 0x3
                    print(f"  Found sprite pixel: {pixel}")
                else:
                    print(f"  No sprite pixel found")


if __name__ == "__main__":
    debug_sprite_patterns()
