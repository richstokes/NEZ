#!/usr/bin/env python3
"""
Test to understand where the open bus value 0x40 is coming from
"""

import sys

sys.path.append(".")

import subprocess
import time

# Start the test ROM in the background
process = subprocess.Popen(
    [
        "python",
        "main.py",
        "../nes-test-roms/cpu_exec_space/test_cpu_exec_space_apu.nes",
    ],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

# Let it run for a few seconds
time.sleep(3)

# Kill it
process.terminate()
process.wait()

# Look for what sets the open bus to 0x40
print("Searching for what sets open bus to 0x40...")

# Check log for any memory reads/writes that could set bus to 0x40
import subprocess

# Search for instructions that would put 0x40 on the bus
result = subprocess.run(
    ["grep", "-n", "0x40", "log.log"], capture_output=True, text=True
)

if result.stdout:
    lines = result.stdout.strip().split("\n")
    print(f"Found {len(lines)} occurrences of 0x40 in log:")
    for i, line in enumerate(lines[:20]):  # Show first 20
        print(f"  {line}")
    if len(lines) > 20:
        print(f"  ... and {len(lines) - 20} more")
else:
    print("No 0x40 found in log")

# Look specifically for RTI instructions which are opcode 0x40
result = subprocess.run(
    ["grep", "-B5", "-A5", "opcode=0x40.*length=1", "log.log"],
    capture_output=True,
    text=True,
)

if result.stdout:
    print("\n=== RTI (0x40) instruction contexts ===")
    lines = result.stdout.strip().split("\n")
    for line in lines[:50]:  # Show first 50 lines
        print(line)
else:
    print("No RTI instructions found")
