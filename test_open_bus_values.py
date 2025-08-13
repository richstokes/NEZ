#!/usr/bin/env python3
"""
Test different open bus values to understand expected behavior
"""

import sys

sys.path.append(".")

from cpu import CPU
from memory import Memory


def test_different_open_bus_values():
    """Test execution with different open bus values"""
    values_to_test = [
        (0x40, "RTI - Return from Interrupt"),
        (0xEA, "NOP - No Operation"),
        (0x60, "RTS - Return from Subroutine"),
        (0x00, "BRK - Force Break"),
        (0x4C, "JMP - Jump"),
    ]

    for value, description in values_to_test:
        print(f"\nTesting open bus value 0x{value:02X} ({description}):")

        memory = Memory()
        cpu = CPU(memory)

        # Initialize CPU state
        cpu.PC = 0x8000
        cpu.S = 0xFD

        # Set the open bus to this value
        memory.bus = value

        # Test reading from APU I/O space
        read_value = memory.read(0x4000)
        print(f"  APU read returns: 0x{read_value:02X}")

        # If we executed this opcode, what would happen?
        if value == 0xEA:  # NOP
            print("  NOP would increment PC and continue execution")
        elif value == 0x40:  # RTI
            print("  RTI would pop PC and status from stack")
        elif value == 0x60:  # RTS
            print("  RTS would pop PC from stack and increment")
        elif value == 0x00:  # BRK
            print("  BRK would trigger interrupt")
        elif value == 0x4C:  # JMP
            print("  JMP would need 2 more bytes for target address")


if __name__ == "__main__":
    test_different_open_bus_values()
