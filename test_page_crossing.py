#!/usr/bin/env python3
"""
Test page crossing behavior for CPU timing test compliance
"""

from cpu import CPU
from memory import Memory


def test_page_crossing():
    """Test page crossing penalties for specific instructions"""
    print("Testing page crossing behavior for CPU timing compliance...")

    # Create CPU and memory
    memory = Memory()
    cpu = CPU(memory)

    # Test LDA absolute,X without page crossing
    # Set up: LDA $00FD,X with X=2 (should access $00FF - no page crossing)
    memory.write(0x0000, 0xBD)  # LDA absolute,X
    memory.write(0x0001, 0xFD)  # Low byte
    memory.write(0x0002, 0x00)  # High byte
    memory.write(0x00FF, 0x42)  # Data to load
    cpu.PC = 0x0000
    cpu.X = 2

    cycles = cpu.run_instruction()
    print(f"LDA $00FD,X with X=2 (no page crossing): {cycles} cycles (expected: 4)")

    # Test LDA absolute,X with page crossing
    # Set up: LDA $00FD,X with X=3 (should access $0100 - page crossing)
    memory.write(0x0003, 0xBD)  # LDA absolute,X
    memory.write(0x0004, 0xFD)  # Low byte
    memory.write(0x0005, 0x00)  # High byte
    memory.write(0x0100, 0x43)  # Data to load
    cpu.PC = 0x0003
    cpu.X = 3

    cycles = cpu.run_instruction()
    print(f"LDA $00FD,X with X=3 (page crossing): {cycles} cycles (expected: 5)")

    # Test unofficial NOP absolute,X without page crossing
    memory.write(0x0006, 0x1C)  # NOP absolute,X
    memory.write(0x0007, 0xFD)  # Low byte
    memory.write(0x0008, 0x00)  # High byte
    cpu.PC = 0x0006
    cpu.X = 2

    cycles = cpu.run_instruction()
    print(f"NOP $00FD,X with X=2 (no page crossing): {cycles} cycles (expected: 4)")

    # Test unofficial NOP absolute,X with page crossing
    memory.write(0x0009, 0x1C)  # NOP absolute,X
    memory.write(0x000A, 0xFD)  # Low byte
    memory.write(0x000B, 0x00)  # High byte
    cpu.PC = 0x0009
    cpu.X = 3

    cycles = cpu.run_instruction()
    print(f"NOP $00FD,X with X=3 (page crossing): {cycles} cycles (expected: 5)")

    # Test LAX absolute,Y without page crossing
    memory.write(0x000C, 0xBF)  # LAX absolute,Y
    memory.write(0x000D, 0xFD)  # Low byte
    memory.write(0x000E, 0x00)  # High byte
    memory.write(0x00FF, 0x44)  # Data to load
    cpu.PC = 0x000C
    cpu.Y = 2

    cycles = cpu.run_instruction()
    print(f"LAX $00FD,Y with Y=2 (no page crossing): {cycles} cycles (expected: 4)")

    # Test LAX absolute,Y with page crossing
    memory.write(0x000F, 0xBF)  # LAX absolute,Y
    memory.write(0x0010, 0xFD)  # Low byte
    memory.write(0x0011, 0x00)  # High byte
    memory.write(0x0100, 0x45)  # Data to load
    cpu.PC = 0x000F
    cpu.Y = 3

    cycles = cpu.run_instruction()
    print(f"LAX $00FD,Y with Y=3 (page crossing): {cycles} cycles (expected: 5)")


if __name__ == "__main__":
    test_page_crossing()
