#!/usr/bin/env python3
"""
Test actual execution from APU I/O space to understand the issue
"""

import sys

sys.path.append(".")

from cpu import CPU
from memory import Memory


def test_apu_execution():
    """Test what happens when CPU executes from APU I/O space"""
    memory = Memory()
    cpu = CPU(memory)

    # Initialize CPU
    cpu.PC = 0x8000
    cpu.S = 0xFD  # Stack pointer

    # Set up a realistic open bus value
    # First, do a read that would set the open bus to something other than 0x40
    memory.write(0x8000, 0x60)  # RTS instruction
    memory.bus = memory.read(0x8000)  # This should set bus to 0x60
    print(f"Open bus set to: 0x{memory.bus:02X}")

    # Now test reading from APU I/O space
    for addr in [0x4000, 0x4001, 0x4002, 0x4003]:
        value = memory.read(addr)
        print(f"Read from 0x{addr:04X}: 0x{value:02X}")

    # Test what happens if CPU executes from APU space
    # Set PC to APU space
    cpu.PC = 0x4000

    # Try to execute an instruction
    try:
        opcode = memory.read(cpu.PC)
        print(f"Opcode at 0x{cpu.PC:04X}: 0x{opcode:02X}")

        if opcode == 0x60:  # RTS
            print("Would execute RTS (Return from Subroutine)")
            # RTS pops PC from stack and increments it
            if cpu.S < 0xFF:
                low = memory.read(0x0100 + cpu.S + 1)
                high = memory.read(0x0100 + cpu.S + 2)
                target = ((high << 8) | low) + 1
                print(f"RTS would return to: 0x{target:04X}")
            else:
                print("Stack empty, RTS behavior undefined")
        elif opcode == 0x40:  # RTI
            print("Would execute RTI (Return from Interrupt)")
        else:
            print(f"Would execute unknown opcode: 0x{opcode:02X}")

    except Exception as e:
        print(f"Error during execution: {e}")


if __name__ == "__main__":
    test_apu_execution()
