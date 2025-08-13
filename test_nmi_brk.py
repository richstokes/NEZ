#!/usr/bin/env python3
"""
Test NMI and BRK timing to debug cpu_interrupts test failure
"""

import sys

sys.path.append(".")

from cpu import CPU
from memory import Memory


def test_brk_timing():
    """Test BRK instruction timing and flag handling"""
    memory = Memory()
    cpu = CPU(memory)

    # Set up interrupt vectors
    memory.write(0xFFFE, 0x00)  # IRQ vector low
    memory.write(0xFFFF, 0x80)  # IRQ vector high
    memory.write(0xFFFA, 0x00)  # NMI vector low
    memory.write(0xFFFB, 0x82)  # NMI vector high

    # Also set up memory at those addresses for debugging
    memory.write(0x8000, 0x00)  # BRK target
    memory.write(0x8200, 0x00)  # NMI target

    print(f"IRQ vector: 0x{memory.read(0xFFFF):02X}{memory.read(0xFFFE):02X}")
    print(f"NMI vector: 0x{memory.read(0xFFFB):02X}{memory.read(0xFFFA):02X}")

    # Debug: Test direct memory reading
    low = memory.read(0xFFFE)
    high = memory.read(0xFFFF)
    computed_vector = (high << 8) | low
    print(
        f"Computed IRQ vector: low=0x{low:02X}, high=0x{high:02X}, vector=0x{computed_vector:04X}"
    )

    # Place BRK instruction at 0x8000
    memory.write(0x8000, 0x00)  # BRK opcode

    cpu.PC = 0x8000
    cpu.S = 0xFF
    cpu.I = 0  # Interrupts enabled

    print(f"Before BRK: PC=0x{cpu.PC:04X}, S=0x{cpu.S:02X}, I={cpu.I}")
    print(f"Memory at 0xFFFE: 0x{memory.read(0xFFFE):02X}")
    print(f"Memory at 0xFFFF: 0x{memory.read(0xFFFF):02X}")

    # Execute BRK
    cpu.execute_brk(None, "implied")

    print(f"After BRK: PC=0x{cpu.PC:04X}, S=0x{cpu.S:02X}, I={cpu.I}")

    # Check stack contents
    stack_status = memory.read(0x100 + cpu.S + 1)
    stack_pc_low = memory.read(0x100 + cpu.S + 2)
    stack_pc_high = memory.read(0x100 + cpu.S + 3)

    print(
        f"Stack: Status=0x{stack_status:02X}, PC=0x{stack_pc_high:02X}{stack_pc_low:02X}"
    )
    print(f"B flag in pushed status: {(stack_status & 0x10) != 0}")
    print(f"I flag in pushed status: {(stack_status & 0x04) != 0}")


def test_nmi_timing():
    """Test NMI timing"""
    memory = Memory()
    cpu = CPU(memory)

    # Set up NMI vector
    memory.write(0xFFFA, 0x00)  # NMI vector low
    memory.write(0xFFFB, 0x82)  # NMI vector high

    print(f"NMI vector: 0x{memory.read(0xFFFB):02X}{memory.read(0xFFFA):02X}")

    cpu.PC = 0x8000
    cpu.S = 0xFF
    cpu.I = 1  # Interrupts disabled (shouldn't matter for NMI)

    print(f"Before NMI: PC=0x{cpu.PC:04X}, S=0x{cpu.S:02X}, I={cpu.I}")

    # Trigger NMI
    cpu.trigger_interrupt("NMI")

    print(f"NMI triggered: interrupt_pending={cpu.interrupt_pending}")

    # Run one instruction cycle to handle the interrupt
    if cpu.interrupt_pending and cpu.interrupt_state == 0:
        cpu._handle_interrupt()
        cpu.interrupt_pending = None

    print(f"After NMI: PC=0x{cpu.PC:04X}, S=0x{cpu.S:02X}, I={cpu.I}")

    # Check stack contents
    stack_status = memory.read(0x100 + cpu.S + 1)
    stack_pc_low = memory.read(0x100 + cpu.S + 2)
    stack_pc_high = memory.read(0x100 + cpu.S + 3)

    print(
        f"Stack: Status=0x{stack_status:02X}, PC=0x{stack_pc_high:02X}{stack_pc_low:02X}"
    )
    print(f"B flag in pushed status: {(stack_status & 0x10) != 0}")
    print(f"I flag in pushed status: {(stack_status & 0x04) != 0}")


if __name__ == "__main__":
    print("=== Testing BRK timing ===")
    test_brk_timing()
    print("\n=== Testing NMI timing ===")
    test_nmi_timing()
