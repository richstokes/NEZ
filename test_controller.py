#!/usr/bin/env python3
"""
Quick test to check if controller input is working
"""

from nes import NES
from utils import debug_print


def test_controller():
    """Test controller input is processed correctly"""
    nes = NES()

    # Load Mario ROM
    if not nes.load_cartridge("mario.nes"):
        print("Failed to load ROM")
        return

    nes.reset()

    # Run a few frames to get Mario ready
    for frame in range(5):
        nes.step_frame()
        print(f"Frame {frame}: CPU cycles={nes.cpu_cycles}")

    # Test controller input
    print("\nTesting controller input...")

    # Set Start button
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

    # Check if controller state is set in memory
    print(f"Controller1 state: 0x{nes.memory.controller1:02X}")
    print(f"Controller1 shift: 0x{nes.memory.controller1_shift:02X}")

    # Simulate strobe write
    nes.memory.write(0x4016, 1)  # Strobe high
    nes.memory.write(0x4016, 0)  # Strobe low

    # Read controller bits
    print(f"After strobe - Controller1 state: 0x{nes.memory.controller1:02X}")
    print(f"Controller1 shift: 0x{nes.memory.controller1_shift:02X}")

    # Read 8 controller bits
    controller_reads = []
    for i in range(8):
        bit = nes.memory.read(0x4016)
        controller_reads.append(bit & 1)
        print(f"Controller read {i}: {bit & 1}")

    print(f"Controller bits read: {controller_reads}")
    print(f"Expected: [0, 0, 0, 1, 0, 0, 0, 0] (Start button)")


if __name__ == "__main__":
    test_controller()
