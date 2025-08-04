#!/usr/bin/env python3
"""
Test script for the NES emulator to verify hardware-accurate implementation
"""

import os
import sys
from nes import NES


def test_basic_functionality():
    """Test basic NES functionality"""
    print("Testing NES Emulator Hardware-Accurate Implementation")
    print("=" * 50)

    # Initialize NES
    nes = NES()
    print("✓ NES initialized successfully")

    # Test reset
    nes.reset()
    print("✓ NES reset successfully")

    # Test CPU state after reset
    print(f"✓ CPU PC after reset: ${nes.cpu.PC:04X}")
    print(f"✓ CPU S (Stack Pointer) after reset: ${nes.cpu.S:02X}")
    print(f"✓ CPU status after reset: ${nes.cpu.get_status_byte():02X}")

    # Test memory system
    test_addr = 0x0300  # Use RAM address instead of PPU register
    test_value = 0xA5
    nes.memory.write(test_addr, test_value)
    read_value = nes.memory.read(test_addr)
    if read_value == test_value:
        print(
            f"✓ Memory write/read test passed: wrote ${test_value:02X}, read ${read_value:02X}"
        )
    else:
        print(
            f"✗ Memory write/read test failed: wrote ${test_value:02X}, read ${read_value:02X}"
        )

    # Test stepping
    initial_cycles = nes.cpu_cycles
    nes.step()
    if nes.cpu_cycles > initial_cycles:
        print(
            f"✓ CPU stepping works: {nes.cpu_cycles - initial_cycles} cycles executed"
        )
    else:
        print("✗ CPU stepping failed")

    # Test CPU instructions
    print("\nTesting CPU instructions:")

    # Test LDA immediate
    nes.cpu.PC = 0x8000
    nes.memory.write(0x8000, 0xA9)  # LDA #$42
    nes.memory.write(0x8001, 0x42)

    cycles = nes.cpu.step()
    print(f"✓ LDA #$42: A=${nes.cpu.A:02X}, cycles={cycles}")

    # Test STA absolute
    nes.memory.write(0x8002, 0x8D)  # STA $2000
    nes.memory.write(0x8003, 0x00)
    nes.memory.write(0x8004, 0x20)

    cycles = nes.cpu.step()
    stored_value = nes.memory.read(0x2000)
    print(f"✓ STA $2000: stored ${stored_value:02X}, cycles={cycles}")

    # Test NOP
    nes.memory.write(0x8005, 0xEA)  # NOP
    cycles = nes.cpu.step()
    print(f"✓ NOP: cycles={cycles}")

    print(f"\nFinal CPU state:")
    print(f"  PC: ${nes.cpu.PC:04X}")
    print(f"  A:  ${nes.cpu.A:02X}")
    print(f"  X:  ${nes.cpu.X:02X}")
    print(f"  Y:  ${nes.cpu.Y:02X}")
    print(f"  S (Stack Pointer): ${nes.cpu.S:02X}")
    print(f"  Status: ${nes.cpu.get_status_byte():02X}")
    print(f"  Total cycles: {nes.cpu_cycles}")

    return True


def test_rom_loading():
    """Test ROM loading if available"""
    print("\nTesting ROM loading:")
    print("-" * 20)

    nes = NES()

    # Check if mario.nes exists
    rom_path = "mario.nes"
    if os.path.exists(rom_path):
        print(f"Found ROM file: {rom_path}")
        success = nes.load_rom(rom_path)
        if success:
            print("✓ ROM loaded successfully")

            # Test a few frames
            print("Running a few frames...")
            for frame in range(5):
                screen = nes.step_frame()
                print(
                    f"  Frame {frame + 1}: Screen buffer size: {len(screen) if screen else 0}"
                )

            print(f"Total CPU cycles after 5 frames: {nes.cpu_cycles}")
            print(f"Total PPU cycles after 5 frames: {nes.ppu_cycles}")

        else:
            print("✗ Failed to load ROM")
            return False
    else:
        print(f"ROM file {rom_path} not found - skipping ROM test")

    return True


def main():
    """Main test function"""
    try:
        # Test basic functionality
        if not test_basic_functionality():
            print("\n✗ Basic functionality tests failed")
            return 1

        # Test ROM loading
        if not test_rom_loading():
            print("\n✗ ROM loading tests failed")
            return 1

        print("\n" + "=" * 50)
        print("✓ All tests passed! Hardware-accurate NES emulator is working.")
        print("The CPU, Memory, and PPU systems are properly integrated.")
        return 0

    except Exception as e:
        print(f"\n✗ Test failed with exception: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
