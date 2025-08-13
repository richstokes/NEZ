#!/usr/bin/env python3
"""
Test APU frame IRQ timing with CLI instruction
"""

import sys

sys.path.append(".")

from cpu import CPU
from memory import Memory
from apu import APU
from nes import NES


def test_apu_frame_irq_cli_timing():
    """Test APU frame IRQ timing with CLI instruction"""

    # Create a minimal NES system
    nes = NES()
    nes.load_rom("../nes-test-roms/cpu_interrupts_v2/cpu_interrupts.nes")

    cpu = nes.cpu
    apu = nes.apu

    # Reset APU to known state
    apu.write_register(0x4017, 0x00)  # 4-step mode, IRQ enabled

    print(
        f"APU frame sequencer: mode={apu.frame_sequencer.mode}, irq_inhibit={apu.frame_sequencer.irq_inhibit}"
    )

    # Manually trigger the frame sequencer to generate an IRQ after many cycles
    # Simulate enough APU cycles to trigger frame IRQ
    for i in range(30000):
        apu.frame_sequencer.clock(apu)
        if apu.frame_sequencer.irq_flag:
            print(f"Frame IRQ flagged at cycle {i}")
            break

    # Check if IRQ was triggered on CPU
    print(f"CPU interrupt_pending: {cpu.interrupt_pending}")
    print(f"CPU I flag: {cpu.I}")
    print(f"CPU interrupt_inhibit: {cpu.interrupt_inhibit}")

    if cpu.interrupt_pending == "IRQ":
        print("✓ APU frame IRQ was triggered on CPU")

        # Now test CLI + IRQ timing
        cpu.I = 1  # Disable interrupts
        cpu.interrupt_inhibit = 1
        cpu.interrupt_pending = None  # Clear pending

        # Execute CLI
        cpu.execute_cli(None, "implied")
        print(
            f"After CLI: I={cpu.I}, interrupt_inhibit={cpu.interrupt_inhibit}, delay_pending={cpu.interrupt_delay_pending}"
        )

        # Trigger APU IRQ during CLI delay period
        cpu.trigger_interrupt("IRQ")
        print(
            f"IRQ triggered during CLI delay: interrupt_pending={cpu.interrupt_pending}"
        )

        # Apply CLI delay (what happens at start of next instruction)
        if cpu.interrupt_delay_pending:
            cpu.interrupt_inhibit = cpu.I
            cpu.interrupt_delay_pending = False

        print(
            f"After CLI delay applied: I={cpu.I}, interrupt_inhibit={cpu.interrupt_inhibit}"
        )

        # Check if IRQ would now be processed
        if cpu.interrupt_pending == "IRQ" and cpu.interrupt_inhibit == 0:
            print("✓ IRQ would be processed after CLI delay")
            return True
        else:
            print("✗ IRQ would NOT be processed")
            return False
    else:
        print("✗ APU frame IRQ was NOT triggered")
        return False


if __name__ == "__main__":
    test_apu_frame_irq_cli_timing()
