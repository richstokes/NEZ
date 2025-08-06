#!/usr/bin/env python3
"""
Detailed test to debug controller reading issue
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

# Test memory module directly to avoid SDL2 dependency
from memory import Memory

def test_controller_reading():
    """Test controller reading in detail"""
    print("Testing controller reading...")
    
    memory = Memory()
    
    # Mock PPU for testing
    class MockPPU:
        def read_register(self, addr):
            return 0
        def write_register(self, addr, value):
            pass
    
    memory.set_ppu(MockPPU())
    
    print("\n=== Testing Controller Reading ===")
    
    # Set Start button pressed
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
    
    # Set controller state directly
    memory.controller1 = 0x08  # Start button
    
    # Check memory state
    print(f"Controller1 byte: 0x{memory.controller1:02X} (should be 0x08 for Start)")
    print(f"Controller1 shift: 0x{memory.controller1_shift:02X}")
    print(f"Controller1 index: {memory.controller1_index}")
    print(f"Strobe: {memory.strobe}")
    
    # Simulate what the game does to read controller
    print("\n=== Simulating Game Controller Read ===")
    
    # Write 1 then 0 to $4016 (strobe)
    print("Writing 1 to $4016 (strobe high)")
    memory.write(0x4016, 1)
    print(f"  Strobe: {memory.strobe}")
    print(f"  Controller1 shift: 0x{memory.controller1_shift:02X}")
    print(f"  Controller1 index: {memory.controller1_index}")
    
    print("Writing 0 to $4016 (strobe low)")
    memory.write(0x4016, 0)
    print(f"  Strobe: {memory.strobe}")
    print(f"  Controller1 shift: 0x{memory.controller1_shift:02X}")
    print(f"  Controller1 index: {memory.controller1_index}")
    
    # Read 8 times from $4016
    print("\nReading 8 times from $4016:")
    buttons = ["A", "B", "Select", "Start", "Up", "Down", "Left", "Right"]
    for i in range(8):
        value = memory.read(0x4016)
        bit = value & 1
        print(f"  Read {i} ({buttons[i]}): {bit} (raw value: 0x{value:02X})")
    
    # Try reading a 9th time (should return 1)
    value = memory.read(0x4016)
    bit = value & 1
    print(f"  Read 8 (beyond buttons): {bit} (should be 1)")
    
    print("\n=== Testing Different Button Combinations ===")
    
    # Test A button
    print("\nTesting A button:")
    memory.controller1 = 0x01  # A button
    memory.write(0x4016, 1)
    memory.write(0x4016, 0)
    for i in range(8):
        value = memory.read(0x4016)
        bit = value & 1
        if bit:
            print(f"  {buttons[i]} is pressed")
    
    # Test Right + A
    print("\nTesting Right + A:")
    memory.controller1 = 0x81  # Right (0x80) + A (0x01)
    memory.write(0x4016, 1)
    memory.write(0x4016, 0)
    for i in range(8):
        value = memory.read(0x4016)
        bit = value & 1
        if bit:
            print(f"  {buttons[i]} is pressed")
    
    print("\n=== Complete Test ===")

if __name__ == "__main__":
    test_controller_reading()
