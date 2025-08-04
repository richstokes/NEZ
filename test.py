"""
Test script for NES emulator components
"""

from nes import NES
import os


def test_cpu_basic():
    """Test basic CPU functionality"""
    print("Testing CPU...")
    nes = NES()

    # Test LDA immediate
    nes.memory.ram[0] = 0xA9  # LDA #$42
    nes.memory.ram[1] = 0x42
    nes.cpu.PC = 0

    nes.cpu.step()
    assert nes.cpu.A == 0x42, f"Expected A=0x42, got A=0x{nes.cpu.A:02X}"
    assert nes.cpu.Z == 0, "Zero flag should not be set"
    assert nes.cpu.N == 0, "Negative flag should not be set"

    print("✓ CPU basic test passed")


def test_ppu_basic():
    """Test basic PPU functionality"""
    print("Testing PPU...")
    nes = NES()

    # Test PPU register writes
    nes.ppu.write_register(0x2000, 0x80)  # Enable NMI
    assert nes.ppu.ctrl == 0x80

    nes.ppu.write_register(0x2001, 0x1E)  # Enable rendering
    assert nes.ppu.mask == 0x1E

    print("✓ PPU basic test passed")


def test_memory():
    """Test memory system"""
    print("Testing Memory...")
    nes = NES()

    # Test RAM writes and reads
    nes.memory.write(0x0200, 0xAB)
    assert nes.memory.read(0x0200) == 0xAB

    # Test RAM mirroring
    nes.memory.write(0x0800, 0xCD)
    assert nes.memory.read(0x0000) == 0xCD  # Should be mirrored

    print("✓ Memory test passed")


def test_cartridge_loading():
    """Test cartridge loading"""
    print("Testing Cartridge loading...")

    if os.path.exists("mario.nes"):
        nes = NES()
        success = nes.load_cartridge("mario.nes")
        assert success, "Failed to load mario.nes"
        print("✓ Cartridge loading test passed")
    else:
        print("⚠ mario.nes not found, skipping cartridge test")


def run_tests():
    """Run all tests"""
    print("Running NES emulator tests...\n")

    try:
        test_cpu_basic()
        test_ppu_basic()
        test_memory()
        test_cartridge_loading()

        print("\n✓ All tests passed!")
        return True

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        return False


if __name__ == "__main__":
    run_tests()
