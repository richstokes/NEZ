#!/usr/bin/env python3
"""
Test basic memory functionality
"""

import sys

sys.path.append(".")

from memory import Memory


def test_basic_memory():
    memory = Memory()

    # Test normal RAM area
    memory.write(0x0000, 0x42)
    print(f"RAM test: wrote 0x42 to 0x0000, read back: 0x{memory.read(0x0000):02X}")

    # Test interrupt vector area
    memory.write(0xFFFE, 0x34)
    memory.write(0xFFFF, 0x12)

    print(f"Vector test: wrote 0x34/0x12 to 0xFFFE/0xFFFF")
    print(f"Read back 0xFFFE: 0x{memory.read(0xFFFE):02X}")
    print(f"Read back 0xFFFF: 0x{memory.read(0xFFFF):02X}")

    # Check bus value
    print(f"Bus value: 0x{memory.bus:02X}")


if __name__ == "__main__":
    test_basic_memory()
