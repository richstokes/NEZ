#!/usr/bin/env python3
"""
Test CLI latency behavior for CPU interrupt compliance
"""

from cpu import CPU
from memory import Memory


def test_cli_latency():
    """Test CLI one-instruction delay behavior"""
    print("Testing CLI latency behavior...")

    # Create CPU and memory
    memory = Memory()
    cpu = CPU(memory)

    # Test 1: Set up scenario where IRQ is pending and CLI is executed
    cpu.I = 0  # Start with interrupts enabled
    cpu.interrupt_inhibit = 0
    cpu.trigger_interrupt("IRQ")  # Trigger IRQ while enabled

    # Now manually set I=1 to simulate the scenario where CLI will clear it
    cpu.I = 1
    cpu.interrupt_inhibit = 1

    print(
        f"Initial state: I={cpu.I}, interrupt_inhibit={cpu.interrupt_inhibit}, IRQ pending={cpu.interrupt_pending}"
    )

    # Execute CLI instruction
    memory.write(0x0000, 0x58)  # CLI
    memory.write(0x0001, 0xEA)  # NOP (next instruction)
    cpu.PC = 0x0000

    cycles = cpu.run_instruction()  # Execute CLI
    print(
        f"After CLI: I={cpu.I}, interrupt_inhibit={cpu.interrupt_inhibit}, cycles={cycles}"
    )
    print(
        f"IRQ pending: {cpu.interrupt_pending}, delay_pending: {cpu.interrupt_delay_pending}"
    )

    # The IRQ should still be pending and interrupt_inhibit should still be 1
    assert cpu.interrupt_pending == "IRQ", "IRQ should still be pending after CLI"
    assert cpu.I == 0, "I flag should be cleared by CLI"
    assert (
        cpu.interrupt_inhibit == 1
    ), "interrupt_inhibit should still be 1 (delay not applied yet)"
    assert cpu.interrupt_delay_pending == True, "delay should be pending"

    # Execute next instruction (NOP) - this should apply the delay and handle IRQ
    cycles = cpu.run_instruction()  # Execute NOP
    print(
        f"After NOP: I={cpu.I}, interrupt_inhibit={cpu.interrupt_inhibit}, cycles={cycles}"
    )
    print(
        f"IRQ pending: {cpu.interrupt_pending}, delay_pending: {cpu.interrupt_delay_pending}"
    )

    # Now the delay should be applied
    assert cpu.interrupt_delay_pending == False, "delay should no longer be pending"
    assert cpu.interrupt_inhibit == 0, "interrupt_inhibit should now be 0"

    print("CLI latency test passed!")


def test_sei_latency():
    """Test SEI one-instruction delay behavior"""
    print("\nTesting SEI latency behavior...")

    # Create CPU and memory
    memory = Memory()
    cpu = CPU(memory)

    # Test: SEI should not immediately disable interrupts
    cpu.I = 0  # Start with interrupts enabled
    cpu.interrupt_inhibit = 0

    print(f"Initial state: I={cpu.I}, interrupt_inhibit={cpu.interrupt_inhibit}")

    # Execute SEI instruction
    memory.write(0x0000, 0x78)  # SEI
    memory.write(0x0001, 0xEA)  # NOP (next instruction)
    cpu.PC = 0x0000

    cycles = cpu.run_instruction()  # Execute SEI
    print(
        f"After SEI: I={cpu.I}, interrupt_inhibit={cpu.interrupt_inhibit}, cycles={cycles}"
    )
    print(f"delay_pending: {cpu.interrupt_delay_pending}")

    # The flag should be set but interrupt_inhibit should still be 0 due to delay
    assert cpu.I == 1, "I flag should be set by SEI"
    assert (
        cpu.interrupt_inhibit == 0
    ), "interrupt_inhibit should still be 0 (delay not applied yet)"
    assert cpu.interrupt_delay_pending == True, "delay should be pending"

    # Execute next instruction (NOP) - this should apply the delay
    cycles = cpu.run_instruction()  # Execute NOP
    print(
        f"After NOP: I={cpu.I}, interrupt_inhibit={cpu.interrupt_inhibit}, cycles={cycles}"
    )
    print(f"delay_pending: {cpu.interrupt_delay_pending}")

    # Now the delay should be applied
    assert cpu.interrupt_delay_pending == False, "delay should no longer be pending"
    assert cpu.interrupt_inhibit == 1, "interrupt_inhibit should now be 1"

    print("SEI latency test passed!")


def test_rti_immediate():
    """Test RTI immediate effect (no delay)"""
    print("\nTesting RTI immediate behavior...")

    # Create CPU and memory
    memory = Memory()
    cpu = CPU(memory)

    # Set up stack for RTI
    cpu.S = 0xFD
    cpu.push_stack(0x80)  # High byte of return address
    cpu.push_stack(0x00)  # Low byte of return address
    cpu.push_stack(0x00)  # Status with I=0 (interrupts enabled)

    cpu.I = 1  # Start with interrupts disabled
    cpu.interrupt_inhibit = 1
    cpu.trigger_interrupt("IRQ")  # Pending IRQ

    print(
        f"Initial state: I={cpu.I}, interrupt_inhibit={cpu.interrupt_inhibit}, IRQ pending={cpu.interrupt_pending}"
    )

    # Execute RTI instruction
    memory.write(0x0000, 0x40)  # RTI
    cpu.PC = 0x0000

    cycles = cpu.run_instruction()  # Execute RTI
    print(
        f"After RTI: I={cpu.I}, interrupt_inhibit={cpu.interrupt_inhibit}, cycles={cycles}"
    )
    print(
        f"IRQ pending: {cpu.interrupt_pending}, delay_pending: {cpu.interrupt_delay_pending}"
    )

    # RTI should take effect immediately
    assert cpu.I == 0, "I flag should be cleared by RTI"
    assert (
        cpu.interrupt_inhibit == 0
    ), "interrupt_inhibit should immediately match I flag"
    assert cpu.interrupt_delay_pending == False, "no delay should be pending for RTI"

    print("RTI immediate test passed!")


if __name__ == "__main__":
    test_cli_latency()
    test_sei_latency()
    test_rti_immediate()
    print("\nAll interrupt latency tests passed!")
