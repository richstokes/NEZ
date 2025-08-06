#!/usr/bin/env python3
"""
Let Mario run longer to see if title screen completes and responds to input
"""

from nes import NES
import time


def let_mario_run_longer():
    """Let Mario run for a longer time to see title screen completion"""
    nes = NES()

    # Load Mario ROM
    if not nes.load_cartridge("mario.nes"):
        print("Failed to load ROM")
        return

    nes.reset()

    # Set Start button pressed from the beginning
    controller_state = {
        "A": False,
        "B": False,
        "Select": False,
        "Start": True,
        "Up": False,
        "Down": False,
        "Left": False,
        "Right": False,
    }
    nes.set_controller_input(1, controller_state)

    print("Running Mario for 180 frames (~3 seconds) to let title screen load...")
    print("Start button is held down the entire time")

    significant_events = []

    for frame in range(180):
        old_mask = nes.ppu.mask
        old_ctrl = nes.ppu.ctrl

        nes.step_frame()

        # Look for significant changes
        if nes.ppu.mask != old_mask:
            significant_events.append(
                f"Frame {frame}: PPU mask changed {old_mask:02X} -> {nes.ppu.mask:02X}"
            )

        if nes.ppu.ctrl != old_ctrl:
            significant_events.append(
                f"Frame {frame}: PPU ctrl changed {old_ctrl:02X} -> {nes.ppu.ctrl:02X}"
            )

        # Print progress every 30 frames (0.5 seconds)
        if frame % 30 == 29:
            print(
                f"Frame {frame + 1}: mask=0x{nes.ppu.mask:02X}, ctrl=0x{nes.ppu.ctrl:02X}"
            )

        # Check if rendering gets enabled
        if nes.ppu.mask & 0x18 and frame > 30:  # Background or sprite rendering enabled
            significant_events.append(
                f"Frame {frame}: Rendering enabled! mask=0x{nes.ppu.mask:02X}"
            )
            break

    print("\nSignificant events:")
    for event in significant_events:
        print(f"  {event}")

    if not significant_events:
        print(
            "❌ No significant changes detected - Mario might be stuck in initialization"
        )
    else:
        print("✅ Mario seems to be progressing")

    print(f"\nFinal state after {frame + 1} frames:")
    print(f"  PPU mask: 0x{nes.ppu.mask:02X}")
    print(f"  PPU ctrl: 0x{nes.ppu.ctrl:02X}")
    print(f"  CPU cycles: {nes.cpu_cycles}")


if __name__ == "__main__":
    let_mario_run_longer()
