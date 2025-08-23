#!/usr/bin/env python3

import sys
sys.path.append('.')

from nes import NES

def analyze_rom_instructions():
    """Disassemble the ROM at the problematic addresses"""
    
    nes = NES()
    if not nes.load_rom('mario.nes'):
        print("Failed to load Mario ROM")
        return
    
    # Get the cartridge ROM data
    prg_rom = nes.memory.cartridge.prg_rom
    print(f"PRG ROM size: {len(prg_rom)} bytes")
    
    # Mario ROM addresses 0x8000-0x8020 correspond to PRG ROM offset 0x0000-0x0020
    # Since NES CPU address 0x8000 maps to PRG ROM offset 0x0
    
    start_addr = 0x8000
    rom_offset = start_addr - 0x8000  # Convert CPU address to ROM offset
    
    print(f"\nDisassembling ROM from CPU address 0x{start_addr:04X} (ROM offset 0x{rom_offset:04X}):")
    print("=" * 60)
    
    # Disassemble instructions around the problematic area
    for addr in range(0x8000, 0x8020):
        rom_offset = addr - 0x8000
        if rom_offset < len(prg_rom):
            opcode = prg_rom[rom_offset]
            print(f"0x{addr:04X}: 0x{opcode:02X}", end="")
            
            # Add simple opcode interpretation
            if opcode == 0xAD:  # LDA absolute
                if rom_offset + 2 < len(prg_rom):
                    low = prg_rom[rom_offset + 1]
                    high = prg_rom[rom_offset + 2]
                    target = low | (high << 8)
                    print(f" {low:02X} {high:02X}  LDA ${target:04X}")
                    if target == 0x2002:
                        print("                    ; Reading PPUSTATUS!")
                else:
                    print("  ??  ??  LDA (incomplete)")
            elif opcode == 0x10:  # BPL
                if rom_offset + 1 < len(prg_rom):
                    offset = prg_rom[rom_offset + 1]
                    # Sign extend the offset
                    if offset & 0x80:
                        offset = offset - 256
                    target = addr + 2 + offset
                    print(f" {prg_rom[rom_offset + 1]:02X}     BPL ${target:04X}")
                    print(f"                    ; Branch if positive (N=0)")
                else:
                    print("  ??     BPL (incomplete)")
            elif opcode == 0x30:  # BMI
                if rom_offset + 1 < len(prg_rom):
                    offset = prg_rom[rom_offset + 1]
                    if offset & 0x80:
                        offset = offset - 256
                    target = addr + 2 + offset
                    print(f" {prg_rom[rom_offset + 1]:02X}     BMI ${target:04X}")
                    print(f"                    ; Branch if negative (N=1)")
                else:
                    print("  ??     BMI (incomplete)")
            elif opcode == 0xA9:  # LDA immediate
                if rom_offset + 1 < len(prg_rom):
                    value = prg_rom[rom_offset + 1]
                    print(f" {value:02X}     LDA #${value:02X}")
                else:
                    print("  ??     LDA (incomplete)")
            elif opcode == 0x8D:  # STA absolute
                if rom_offset + 2 < len(prg_rom):
                    low = prg_rom[rom_offset + 1]
                    high = prg_rom[rom_offset + 2]
                    target = low | (high << 8)
                    print(f" {low:02X} {high:02X}  STA ${target:04X}")
                else:
                    print("  ??  ??  STA (incomplete)")
            elif opcode == 0x78:  # SEI
                print("        SEI")
            elif opcode == 0x4C:  # JMP absolute
                if rom_offset + 2 < len(prg_rom):
                    low = prg_rom[rom_offset + 1]
                    high = prg_rom[rom_offset + 2]
                    target = low | (high << 8)
                    print(f" {low:02X} {high:02X}  JMP ${target:04X}")
                else:
                    print("  ??  ??  JMP (incomplete)")
            else:
                print(f"        Unknown opcode")
        else:
            print(f"0x{addr:04X}: OUT OF RANGE")
    
    print("\n" + "=" * 60)
    print("Analysis:")
    print("Looking for the specific loop pattern at 0x800F-0x8012...")
    
    # Check what's at 0x800F specifically
    addr_800f = 0x800F
    rom_offset_800f = addr_800f - 0x8000
    if rom_offset_800f < len(prg_rom):
        opcode_800f = prg_rom[rom_offset_800f]
        print(f"\n0x800F: Opcode 0x{opcode_800f:02X}")
        if opcode_800f == 0xAD:
            low = prg_rom[rom_offset_800f + 1]
            high = prg_rom[rom_offset_800f + 2]
            target = low | (high << 8)
            print(f"  LDA ${target:04X} - This reads from address 0x{target:04X}")
        
        # What's at 0x8012?
        addr_8012 = 0x8012
        rom_offset_8012 = addr_8012 - 0x8000
        if rom_offset_8012 < len(prg_rom):
            opcode_8012 = prg_rom[rom_offset_8012]
            print(f"\n0x8012: Opcode 0x{opcode_8012:02X}")
            if opcode_8012 == 0x10:  # BPL
                offset = prg_rom[rom_offset_8012 + 1]
                if offset & 0x80:
                    offset = offset - 256
                target = addr_8012 + 2 + offset
                print(f"  BPL ${target:04X} (offset: {offset:+d}) - Branch if N flag is clear")
                print(f"  If N=0, jumps to 0x{target:04X}")
                print(f"  If N=1, continues to next instruction")
            elif opcode_8012 == 0x30:  # BMI
                offset = prg_rom[rom_offset_8012 + 1]
                if offset & 0x80:
                    offset = offset - 256
                target = addr_8012 + 2 + offset
                print(f"  BMI ${target:04X} (offset: {offset:+d}) - Branch if N flag is set")
                print(f"  If N=1, jumps to 0x{target:04X}")
                print(f"  If N=0, continues to next instruction")

if __name__ == "__main__":
    analyze_rom_instructions()
