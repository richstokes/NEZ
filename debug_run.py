#!/usr/bin/env python3

"""
Quick debug script to test the NES emulator functionality
"""

import sys
import time
from nes import NES


def test_basic_execution():
    """Test basic emulator execution"""
    print("Testing basic NES execution...")

    nes = NES()

    # Load ROM
    if not nes.load_cartridge("mario.nes"):
        print("Failed to load ROM")
        return False

    print("ROM loaded successfully")

    # Reset NES
    nes.reset()
    print("NES reset complete")

    # Test a few execution steps
    print("Testing CPU/PPU execution...")
    start_time = time.time()

    for i in range(1000):
        nes.step()

        # Print some debug info every 100 steps
        if i % 100 == 0:
            cpu_state = nes.get_cpu_state()
            ppu_state = nes.get_ppu_state()
            print(
                f"Step {i}: PC=${cpu_state['PC']:04X}, scanline={ppu_state['scanline']}, cycle={ppu_state['cycle']}"
            )

    end_time = time.time()
    print(f"Executed 1000 steps in {end_time - start_time:.3f}s")

    # Test frame execution
    print("Testing frame execution...")
    frame_start = time.time()
    screen = nes.step_frame()
    frame_end = time.time()

    print(f"Frame executed in {frame_end - frame_start:.3f}s")
    print(f"Screen buffer size: {len(screen)}")
    print(f"First few pixels: {screen[:10]}")

    # Test controller input
    print("Testing controller input...")
    nes.set_controller_input(1, {"Start": True, "A": True})

    # Execute a few more steps
    for i in range(10):
        nes.step()

    print("Controller input test complete")

    return True


if __name__ == "__main__":
    success = test_basic_execution()
    sys.exit(0 if success else 1)
