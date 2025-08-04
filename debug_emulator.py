#!/usr/bin/env python3
"""
Debug script to test the emulator's core loop and identify issues
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nes import NES


def debug_emulator():
    """Debug the emulator to find the core issues"""
    print("Creating NES instance...")
    nes = NES()

    print("Loading ROM...")
    if not nes.load_cartridge("mario.nes"):
        print("Failed to load ROM!")
        return

    print("Resetting NES...")
    nes.reset()

    print("Testing step_frame...")
    frame_count = 0

    # Test more frames to see CPU progression
    for i in range(50):
        print(f"Processing frame {i+1}...")

        # Check PPU render flag before
        print(f"  PPU render flag before: {nes.ppu.render}")

        # Step one frame
        screen = nes.step_frame()

        # Check PPU render flag after
        print(f"  PPU render flag after: {nes.ppu.render}")

        # Check screen buffer
        print(f"  Screen buffer size: {len(screen)}")
        if len(screen) > 0:
            print(f"  First few pixels: {screen[:5]}")
            print(f"  Pixel format test: pixel[0] = 0x{screen[0]:08X}")

        # Check PPU state
        print(f"  CPU cycles: {nes.cpu_cycles}")
        print(f"  PPU cycles: {nes.ppu_cycles}")
        print(f"  PPU scanline: {nes.ppu.scanline}, cycle: {nes.ppu.cycle}")
        print(
            f"  PPU mask: 0x{nes.ppu.mask:02X} (SHOW_BG={nes.ppu.mask & nes.ppu.SHOW_BG}, SHOW_SPRITE={nes.ppu.mask & nes.ppu.SHOW_SPRITE})"
        )
        print(f"  PPU ctrl: 0x{nes.ppu.ctrl:02X}")
        print(f"  PPU status: 0x{nes.ppu.status:02X}")
        print(
            f"  CPU PC: 0x{nes.cpu.PC:04X}, A: 0x{nes.cpu.A:02X}, X: 0x{nes.cpu.X:02X}, Y: 0x{nes.cpu.Y:02X}"
        )

        # Test controller input
        print("  Testing controller input...")
        nes.set_controller_input(
            1,
            {
                "Start": True,
                "A": False,
                "B": False,
                "Select": False,
                "Up": False,
                "Down": False,
                "Left": False,
                "Right": False,
            },
        )

        # Run a few more frames to see if controller has any effect
        for j in range(10):
            nes.step()

        print(f"  Controller 1 state: {nes.memory.controller1:02X}")
        print(f"  Controller 1 shift: {nes.memory.controller1_shift:02X}")
        print(f"  Controller strobe: {nes.memory.strobe}")

        # Reset controller
        nes.set_controller_input(
            1,
            {
                "Start": False,
                "A": False,
                "B": False,
                "Select": False,
                "Up": False,
                "Down": False,
                "Left": False,
                "Right": False,
            },
        )

        frame_count += 1
        print(f"  Frame {frame_count} completed")
        print()


if __name__ == "__main__":
    debug_emulator()
