#!/usr/bin/env python3
"""
Debug script to test sprite evaluation for the specific Mario sprite
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nes import NES


def debug_mario_sprite():
    """Debug the specific Mario sprite"""
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

        # Check if sprite 0 is Mario (Y=24)
        if nes.ppu.oam[0] == 24:  # Mario's Y position
            print(f"Found Mario sprite at frame {i+1}")
            break

    # Check Mario's data
    mario_y = nes.ppu.oam[0]
    mario_tile = nes.ppu.oam[1]
    mario_attr = nes.ppu.oam[2]
    mario_x = nes.ppu.oam[3]

    print(
        f"Mario sprite: Y={mario_y}, Tile={mario_tile}, Attr={mario_attr}, X={mario_x}"
    )

    # Test sprite evaluation for scanlines where Mario should appear
    sprite_height = 16 if nes.ppu.ctrl & nes.ppu.LONG_SPRITE else 8

    print(f"Sprite height: {sprite_height}")

    # Test evaluation for scanlines 23, 24, 25 (Mario should be visible on 24-31)
    for test_scanline in [23, 24, 25, 26, 30, 31, 32]:
        nes.ppu.scanline = test_scanline
        nes.ppu.evaluate_sprites()

        found_mario = False
        if nes.ppu.oam_cache_len > 0:
            # Check if sprite 0 (Mario) is in the cache
            if 0 in nes.ppu.oam_cache[: nes.ppu.oam_cache_len]:
                found_mario = True

        print(
            f"Scanline {test_scanline}: cache_len={nes.ppu.oam_cache_len}, found_mario={found_mario}"
        )

        if found_mario:
            # Test sprite rendering for a pixel where Mario should be
            mario_start_x = mario_x
            mario_end_x = mario_x + 8

            print(f"  Mario should be visible at X={mario_start_x}-{mario_end_x}")

            # Simulate rendering a pixel in Mario's area
            nes.ppu.cycle = mario_start_x + 2  # A pixel in Mario's sprite
            sprite_info = nes.ppu.render_sprites(0)  # No background pixel

            print(f"  Sprite render result for X={nes.ppu.cycle-1}: {sprite_info}")
            if sprite_info:
                pixel = sprite_info & 0x3
                palette = (sprite_info >> 2) & 0x3
                priority = (sprite_info >> 5) & 1
                sprite_zero = (sprite_info >> 6) & 1
                print(
                    f"    Pixel={pixel}, Palette={palette}, Priority={priority}, SpriteZero={sprite_zero}"
                )


if __name__ == "__main__":
    debug_mario_sprite()
