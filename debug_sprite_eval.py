#!/usr/bin/env python3
"""
Debug script to specifically test sprite evaluation timing
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nes import NES


def debug_sprite_evaluation():
    """Debug sprite evaluation timing"""
    print("Creating NES instance...")
    nes = NES()

    print("Loading ROM...")
    if not nes.load_cartridge("mario.nes"):
        print("Failed to load ROM!")
        return

    print("Resetting NES...")
    nes.reset()

    print("Running until sprites should be loaded...")

    # Run until we have sprite data
    for i in range(50):
        screen = nes.step_frame()

        # Check if we have sprite data
        if nes.ppu.oam[0] != 0:  # Sprite 0 Y position is not 0
            print(f"Found sprite data at frame {i+1}")
            break

    # Now manually test sprite evaluation for a few scanlines
    sprite_y = nes.ppu.oam[0]  # Sprite 0 Y position
    sprite_height = 16 if nes.ppu.ctrl & nes.ppu.LONG_SPRITE else 8

    print(f"Sprite 0: Y={sprite_y}, Height={sprite_height}")

    # Test sprite evaluation for scanlines around the sprite
    for test_scanline in range(
        max(0, sprite_y - 5), min(240, sprite_y + sprite_height + 5)
    ):
        # Simulate what evaluate_sprites would do
        next_scanline = test_scanline + 1
        diff = next_scanline - sprite_y
        should_be_visible = 0 <= diff < sprite_height

        print(
            f"Scanline {test_scanline}: next_scanline={next_scanline}, diff={diff}, visible={should_be_visible}"
        )

        if should_be_visible:
            print(f"  Sprite 0 should be visible on scanline {test_scanline}!")

    # Now let's check if our evaluation is being called
    print("\nTesting actual sprite evaluation...")

    # Manually set scanline and call evaluate_sprites
    for test_scanline in [sprite_y - 2, sprite_y - 1, sprite_y, sprite_y + 1]:
        nes.ppu.scanline = test_scanline
        old_cache_len = nes.ppu.oam_cache_len
        nes.ppu.evaluate_sprites()

        print(
            f"Scanline {test_scanline}: cache_len={nes.ppu.oam_cache_len}, cache={nes.ppu.oam_cache[:nes.ppu.oam_cache_len]}"
        )


if __name__ == "__main__":
    debug_sprite_evaluation()
