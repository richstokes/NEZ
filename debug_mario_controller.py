#!/usr/bin/env python3
"""
Debug Mario controller polling behavior
"""

from nes import NES
from utils import debug_print


def debug_mario_controller():
    """Test if Mario reads controller input"""
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

    print("Start button is pressed from the beginning")
    print(f"Controller state: 0x{nes.memory.controller1:02X}")

    # Hook memory reads to detect controller polling
    original_read = nes.memory.read
    controller_reads = []

    def hooked_read(addr):
        result = original_read(addr)
        if addr == 0x4016:  # Controller 1 read
            controller_reads.append(
                (nes.ppu.frame, nes.ppu.scanline, nes.ppu.cycle, result & 1)
            )
            if len(controller_reads) <= 10:  # Only print first few
                print(f"CONTROLLER READ: Frame {nes.ppu.frame}, bit={result & 1}")
        return result

    nes.memory.read = hooked_read

    # Run for many frames to see if Mario ever reads controller
    print("\nRunning emulation to check for controller reads...")
    for frame in range(20):  # Run 20 frames (about 1/3 second)
        nes.step_frame()
        if len(controller_reads) > 0 and frame == 0:
            print(f"First controller read detected at frame {controller_reads[0][0]}")

        # Every few frames, check if anything changed
        if frame % 5 == 0:
            print(
                f"Frame {frame}: CPU cycles={nes.cpu_cycles}, controller reads={len(controller_reads)}"
            )

    print(f"\nTotal controller reads after 20 frames: {len(controller_reads)}")
    if len(controller_reads) == 0:
        print("❌ Mario never reads the controller!")
        print(
            "This means the game is stuck in initialization and not progressing to the main loop."
        )
    else:
        print("✅ Mario does read the controller")
        print("First few reads:")
        for i, (frame, scanline, cycle, bit) in enumerate(controller_reads[:8]):
            print(
                f"  Read {i}: Frame {frame}, scanline {scanline}, cycle {cycle}, bit {bit}"
            )


if __name__ == "__main__":
    debug_mario_controller()
