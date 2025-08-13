#!/usr/bin/env python3
"""
Test CLI latency behavior in isolation
"""

import sys

sys.path.append(".")

from cpu import CPU
from memory import Memory


def test_cli_latency():
    """Test that CLI instruction has one-instruction delay"""
    memory = Memory()
    cpu = CPU(memory)

    # Set up test by directly calling the CPU instruction methods
    cpu.PC = 0x8000
    cpu.I = 1  # Start with interrupts disabled
    cpu.interrupt_inhibit = 1

    print(f"Initial state: I={cpu.I}, interrupt_inhibit={cpu.interrupt_inhibit}")

    # Execute CLI instruction directly
    cpu.execute_cli(None, "implied")
    print(
        f"After CLI: I={cpu.I}, interrupt_inhibit={cpu.interrupt_inhibit}, interrupt_delay_pending={cpu.interrupt_delay_pending}"
    )

    # Simulate the delay application (what happens at start of next instruction)
    if cpu.interrupt_delay_pending:
        cpu.I = cpu.interrupt_delay_value
        cpu.interrupt_inhibit = cpu.interrupt_delay_value
        cpu.interrupt_delay_pending = False
    print(
        f"After delay application: I={cpu.I}, interrupt_inhibit={cpu.interrupt_inhibit}"
    )

    # Now trigger an IRQ and see if it's processed
    cpu.trigger_interrupt("IRQ")
    print(f"IRQ triggered: interrupt_pending={cpu.interrupt_pending}")

    # Check if IRQ would be processed (interrupt_inhibit should be 0 now)
    if cpu.interrupt_pending == "IRQ" and cpu.interrupt_inhibit == 0:
        print("✓ IRQ would be processed - CLI latency working correctly")
        return True
    else:
        print(
            f"✗ IRQ would NOT be processed - interrupt_inhibit={cpu.interrupt_inhibit}, I={cpu.I}"
        )
        return False


if __name__ == "__main__":
    test_cli_latency()
