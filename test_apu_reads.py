#!/usr/bin/env python3
"""
Test what values are returned from APU I/O reads
"""

import sys

sys.path.append(".")

from memory import Memory


def test_apu_reads():
    """Test what values are returned from APU I/O reads"""
    memory = Memory()

    print("Testing APU I/O reads...")

    # Set open bus to a known value by doing a read
    memory.bus = 0x12
    print(f"Set open bus to: 0x{memory.bus:02X}")

    # Test reads from write-only APU registers
    for addr in [
        0x4000,
        0x4001,
        0x4002,
        0x4003,
        0x4004,
        0x4005,
        0x4006,
        0x4007,
        0x4008,
        0x4009,
        0x400A,
        0x400B,
        0x400C,
        0x400D,
        0x400E,
        0x400F,
        0x4010,
        0x4011,
        0x4012,
        0x4013,
        0x4017,
    ]:
        value = memory.read(addr)
        print(f"Read from 0x{addr:04X}: 0x{value:02X}")

    # Test reads from unallocated space
    for addr in [0x4018, 0x4019, 0x401A, 0x401F, 0x4020, 0x40FF]:
        value = memory.read(addr)
        print(f"Read from 0x{addr:04X}: 0x{value:02X}")


if __name__ == "__main__":
    test_apu_reads()
