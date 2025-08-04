#!/usr/bin/env python3
"""
Simple test script to verify APU functionality
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from nes import NES


def test_apu():
    """Test basic APU functionality"""
    print("Testing APU integration...")

    # Create NES instance
    nes = NES()

    # Test APU register writes
    print("Testing APU register writes...")

    # Enable all channels
    nes.memory.write(0x4015, 0x0F)  # Enable pulse1, pulse2, triangle, noise
    status = nes.memory.read(0x4015)
    print(f"APU Status after enable: 0x{status:02X}")

    # Configure pulse channel 1
    nes.memory.write(0x4000, 0x30)  # 25% duty, constant volume 0
    nes.memory.write(0x4001, 0x00)  # No sweep
    nes.memory.write(0x4002, 0x00)  # Low frequency byte
    nes.memory.write(0x4003, 0x08)  # High frequency byte, length counter

    # Configure triangle channel
    nes.memory.write(0x4008, 0x81)  # Linear counter
    nes.memory.write(0x400A, 0x00)  # Low frequency
    nes.memory.write(0x400B, 0x08)  # High frequency

    # Configure noise channel
    nes.memory.write(0x400C, 0x30)  # Envelope
    nes.memory.write(0x400E, 0x00)  # Period
    nes.memory.write(0x400F, 0x08)  # Length counter

    print("APU register writes completed successfully!")

    # Test a few APU steps
    print("Testing APU step function...")
    for i in range(100):
        nes.apu.step()

    print("APU step function works!")

    # Test audio sample generation
    print("Testing audio sample generation...")
    samples_generated = len(nes.apu.audio_buffer)
    print(f"Audio buffer has {samples_generated} samples")

    print("APU integration test completed successfully!")
    return True


if __name__ == "__main__":
    try:
        test_apu()
        print("✓ All APU tests passed!")
    except Exception as e:
        print(f"✗ APU test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
