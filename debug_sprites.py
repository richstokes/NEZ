#!/usr/bin/env python3
"""
Debug script to specifically test sprite handling
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nes import NES


def debug_sprites():
    """Debug sprite handling in the emulator"""
    print("Creating NES instance...")
    nes = NES()

    print("Loading ROM...")
    if not nes.load_cartridge("mario.nes"):
        print("Failed to load ROM!")
        return

    print("Resetting NES...")
    nes.reset()

    print("Running until sprites should be loaded...")

    # Run for more frames to let the game initialize
    for i in range(100):
        screen = nes.step_frame()

        # Check if we have meaningful data
        if i % 20 == 0:
            print(f"Frame {i+1}:")
            print(f"  PPU mask: 0x{nes.ppu.mask:02X}")
            print(f"  PPU ctrl: 0x{nes.ppu.ctrl:02X}")
            print(f"  OAM first few bytes: {nes.ppu.oam[:16]}")
            print(
                f"  OAM sprite 0: Y={nes.ppu.oam[0]:02X}, Tile={nes.ppu.oam[1]:02X}, Attr={nes.ppu.oam[2]:02X}, X={nes.ppu.oam[3]:02X}"
            )
            print(f"  OAM cache length: {nes.ppu.oam_cache_len}")
            if nes.ppu.oam_cache_len > 0:
                print(f"  OAM cache: {nes.ppu.oam_cache[:nes.ppu.oam_cache_len]}")

            # Check if rendering is enabled
            if nes.ppu.mask & (nes.ppu.SHOW_BG | nes.ppu.SHOW_SPRITE):
                print(
                    f"  Rendering enabled! BG={nes.ppu.mask & nes.ppu.SHOW_BG != 0}, Sprites={nes.ppu.mask & nes.ppu.SHOW_SPRITE != 0}"
                )

                # Look for non-zero pixels in different regions
                total_pixels = len(screen)
                zero_pixels = sum(1 for p in screen if p == 0)
                print(
                    f"  Screen: {total_pixels} total pixels, {zero_pixels} zero pixels, {total_pixels - zero_pixels} non-zero pixels"
                )

                # Sample a few different regions
                top_left = screen[0:16]
                middle = screen[30 * 256 : 30 * 256 + 16]
                print(f"  Top-left pixels: {[hex(p) for p in top_left]}")
                print(f"  Middle pixels: {[hex(p) for p in middle]}")


if __name__ == "__main__":
    debug_sprites()
