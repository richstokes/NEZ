#!/usr/bin/env python3
"""
Examine what's actually in ROM memory at key addresses
"""

import sys

sys.path.append(".")

from nes import NES


def examine_rom_memory():
    """Load the test ROM and examine key memory locations"""
    # Create NES and load the test ROM
    nes = NES()
    try:
        nes.load_rom("../nes-test-roms/cpu_exec_space/test_cpu_exec_space_apu.nes")
        print("ROM loaded successfully")
    except:
        print("Could not load ROM - examining without ROM")
        return

    # Check what's at address 0x0022 (the JMP instruction)
    print(f"\nMemory at 0x0022: 0x{nes.memory.read(0x0022):02X}")
    print(f"Memory at 0x0023: 0x{nes.memory.read(0x0023):02X}")
    print(f"Memory at 0x0024: 0x{nes.memory.read(0x0024):02X}")

    # This should be a JMP instruction to 0x4000
    opcode = nes.memory.read(0x0022)
    low = nes.memory.read(0x0023)
    high = nes.memory.read(0x0024)
    target = (high << 8) | low

    print(f"Instruction at 0x0022: JMP 0x{target:04X} (opcode=0x{opcode:02X})")

    # Check what's in APU I/O space initially
    print("\nAPU I/O space contents:")
    for addr in range(0x4000, 0x4018):
        value = nes.memory.read(addr)
        print(f"  0x{addr:04X}: 0x{value:02X}")

    # Check the open bus value
    print(f"\nCurrent open bus value: 0x{nes.memory.bus:02X}")

    # See what happens when we read from different areas
    print(f"\nReading from ROM (0x8000): 0x{nes.memory.read(0x8000):02X}")
    print(f"Open bus after ROM read: 0x{nes.memory.bus:02X}")

    print(f"\nReading from APU (0x4000) again: 0x{nes.memory.read(0x4000):02X}")
    print(f"Open bus after APU read: 0x{nes.memory.bus:02X}")


if __name__ == "__main__":
    examine_rom_memory()
