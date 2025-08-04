"""
NES 6502 CPU Emulator
Implements the MOS Technology 6502 processor used in the NES
"""


class CPU:
    def __init__(self, memory):
        self.memory = memory

        # Registers
        self.A = 0  # Accumulator
        self.X = 0  # X Register
        self.Y = 0  # Y Register
        self.PC = 0  # Program Counter
        self.S = 0xFD  # Stack Pointer

        # Status flags (P register)
        self.C = 0  # Carry flag
        self.Z = 0  # Zero flag
        self.I = 1  # Interrupt disable
        self.D = 0  # Decimal mode (unused in NES)
        self.B = 0  # Break flag
        self.V = 0  # Overflow flag
        self.N = 0  # Negative flag

        self.cycles = 0
        self.dma_cycles = 0  # Additional cycles from DMA operations

        # Instruction set
        self.instructions = {
            # Load/Store
            0xA9: ("LDA", "immediate", 2, 2),
            0xA5: ("LDA", "zero_page", 2, 3),
            0xB5: ("LDA", "zero_page_x", 2, 4),
            0xAD: ("LDA", "absolute", 3, 4),
            0xBD: ("LDA", "absolute_x", 3, 4),
            0xB9: ("LDA", "absolute_y", 3, 4),
            0xA1: ("LDA", "indexed_indirect", 2, 6),
            0xB1: ("LDA", "indirect_indexed", 2, 5),
            0xA2: ("LDX", "immediate", 2, 2),
            0xA6: ("LDX", "zero_page", 2, 3),
            0xB6: ("LDX", "zero_page_y", 2, 4),
            0xAE: ("LDX", "absolute", 3, 4),
            0xBE: ("LDX", "absolute_y", 3, 4),
            0xA0: ("LDY", "immediate", 2, 2),
            0xA4: ("LDY", "zero_page", 2, 3),
            0xB4: ("LDY", "zero_page_x", 2, 4),
            0xAC: ("LDY", "absolute", 3, 4),
            0xBC: ("LDY", "absolute_x", 3, 4),
            0x85: ("STA", "zero_page", 2, 3),
            0x95: ("STA", "zero_page_x", 2, 4),
            0x8D: ("STA", "absolute", 3, 4),
            0x9D: ("STA", "absolute_x", 3, 5),
            0x99: ("STA", "absolute_y", 3, 5),
            0x81: ("STA", "indexed_indirect", 2, 6),
            0x91: ("STA", "indirect_indexed", 2, 6),
            0x86: ("STX", "zero_page", 2, 3),
            0x96: ("STX", "zero_page_y", 2, 4),
            0x8E: ("STX", "absolute", 3, 4),
            0x84: ("STY", "zero_page", 2, 3),
            0x94: ("STY", "zero_page_x", 2, 4),
            0x8C: ("STY", "absolute", 3, 4),
            # Transfer
            0xAA: ("TAX", "implied", 1, 2),
            0xA8: ("TAY", "implied", 1, 2),
            0xBA: ("TSX", "implied", 1, 2),
            0x8A: ("TXA", "implied", 1, 2),
            0x9A: ("TXS", "implied", 1, 2),
            0x98: ("TYA", "implied", 1, 2),
            # Stack
            0x48: ("PHA", "implied", 1, 3),
            0x68: ("PLA", "implied", 1, 4),
            0x08: ("PHP", "implied", 1, 3),
            0x28: ("PLP", "implied", 1, 4),
            # Arithmetic
            0x69: ("ADC", "immediate", 2, 2),
            0x65: ("ADC", "zero_page", 2, 3),
            0x75: ("ADC", "zero_page_x", 2, 4),
            0x6D: ("ADC", "absolute", 3, 4),
            0x7D: ("ADC", "absolute_x", 3, 4),
            0x79: ("ADC", "absolute_y", 3, 4),
            0x61: ("ADC", "indexed_indirect", 2, 6),
            0x71: ("ADC", "indirect_indexed", 2, 5),
            0xE9: ("SBC", "immediate", 2, 2),
            0xE5: ("SBC", "zero_page", 2, 3),
            0xF5: ("SBC", "zero_page_x", 2, 4),
            0xED: ("SBC", "absolute", 3, 4),
            0xFD: ("SBC", "absolute_x", 3, 4),
            0xF9: ("SBC", "absolute_y", 3, 4),
            0xE1: ("SBC", "indexed_indirect", 2, 6),
            0xF1: ("SBC", "indirect_indexed", 2, 5),
            # Logic
            0x29: ("AND", "immediate", 2, 2),
            0x25: ("AND", "zero_page", 2, 3),
            0x35: ("AND", "zero_page_x", 2, 4),
            0x2D: ("AND", "absolute", 3, 4),
            0x3D: ("AND", "absolute_x", 3, 4),
            0x39: ("AND", "absolute_y", 3, 4),
            0x21: ("AND", "indexed_indirect", 2, 6),
            0x31: ("AND", "indirect_indexed", 2, 5),
            0x49: ("EOR", "immediate", 2, 2),
            0x45: ("EOR", "zero_page", 2, 3),
            0x55: ("EOR", "zero_page_x", 2, 4),
            0x4D: ("EOR", "absolute", 3, 4),
            0x5D: ("EOR", "absolute_x", 3, 4),
            0x59: ("EOR", "absolute_y", 3, 4),
            0x41: ("EOR", "indexed_indirect", 2, 6),
            0x51: ("EOR", "indirect_indexed", 2, 5),
            0x09: ("ORA", "immediate", 2, 2),
            0x05: ("ORA", "zero_page", 2, 3),
            0x15: ("ORA", "zero_page_x", 2, 4),
            0x0D: ("ORA", "absolute", 3, 4),
            0x1D: ("ORA", "absolute_x", 3, 4),
            0x19: ("ORA", "absolute_y", 3, 4),
            0x01: ("ORA", "indexed_indirect", 2, 6),
            0x11: ("ORA", "indirect_indexed", 2, 5),
            # Shift/Rotate
            0x0A: ("ASL", "accumulator", 1, 2),
            0x06: ("ASL", "zero_page", 2, 5),
            0x16: ("ASL", "zero_page_x", 2, 6),
            0x0E: ("ASL", "absolute", 3, 6),
            0x1E: ("ASL", "absolute_x", 3, 7),
            0x4A: ("LSR", "accumulator", 1, 2),
            0x46: ("LSR", "zero_page", 2, 5),
            0x56: ("LSR", "zero_page_x", 2, 6),
            0x4E: ("LSR", "absolute", 3, 6),
            0x5E: ("LSR", "absolute_x", 3, 7),
            0x2A: ("ROL", "accumulator", 1, 2),
            0x26: ("ROL", "zero_page", 2, 5),
            0x36: ("ROL", "zero_page_x", 2, 6),
            0x2E: ("ROL", "absolute", 3, 6),
            0x3E: ("ROL", "absolute_x", 3, 7),
            0x6A: ("ROR", "accumulator", 1, 2),
            0x66: ("ROR", "zero_page", 2, 5),
            0x76: ("ROR", "zero_page_x", 2, 6),
            0x6E: ("ROR", "absolute", 3, 6),
            0x7E: ("ROR", "absolute_x", 3, 7),
            # Compare
            0xC9: ("CMP", "immediate", 2, 2),
            0xC5: ("CMP", "zero_page", 2, 3),
            0xD5: ("CMP", "zero_page_x", 2, 4),
            0xCD: ("CMP", "absolute", 3, 4),
            0xDD: ("CMP", "absolute_x", 3, 4),
            0xD9: ("CMP", "absolute_y", 3, 4),
            0xC1: ("CMP", "indexed_indirect", 2, 6),
            0xD1: ("CMP", "indirect_indexed", 2, 5),
            0xE0: ("CPX", "immediate", 2, 2),
            0xE4: ("CPX", "zero_page", 2, 3),
            0xEC: ("CPX", "absolute", 3, 4),
            0xC0: ("CPY", "immediate", 2, 2),
            0xC4: ("CPY", "zero_page", 2, 3),
            0xCC: ("CPY", "absolute", 3, 4),
            # Bit Test
            0x24: ("BIT", "zero_page", 2, 3),
            0x2C: ("BIT", "absolute", 3, 4),
            # Increment/Decrement
            0xE6: ("INC", "zero_page", 2, 5),
            0xF6: ("INC", "zero_page_x", 2, 6),
            0xEE: ("INC", "absolute", 3, 6),
            0xFE: ("INC", "absolute_x", 3, 7),
            0xE8: ("INX", "implied", 1, 2),
            0xC8: ("INY", "implied", 1, 2),
            0xC6: ("DEC", "zero_page", 2, 5),
            0xD6: ("DEC", "zero_page_x", 2, 6),
            0xCE: ("DEC", "absolute", 3, 6),
            0xDE: ("DEC", "absolute_x", 3, 7),
            0xCA: ("DEX", "implied", 1, 2),
            0x88: ("DEY", "implied", 1, 2),
            # Branches
            0x10: ("BPL", "relative", 2, 2),
            0x30: ("BMI", "relative", 2, 2),
            0x50: ("BVC", "relative", 2, 2),
            0x70: ("BVS", "relative", 2, 2),
            0x90: ("BCC", "relative", 2, 2),
            0xB0: ("BCS", "relative", 2, 2),
            0xD0: ("BNE", "relative", 2, 2),
            0xF0: ("BEQ", "relative", 2, 2),
            # Jumps/Calls
            0x4C: ("JMP", "absolute", 3, 3),
            0x6C: ("JMP", "indirect", 3, 5),
            0x20: ("JSR", "absolute", 3, 6),
            0x60: ("RTS", "implied", 1, 6),
            # Interrupts
            0x00: ("BRK", "implied", 1, 7),
            0x40: ("RTI", "implied", 1, 6),
            # Flags
            0x18: ("CLC", "implied", 1, 2),
            0x38: ("SEC", "implied", 1, 2),
            0x58: ("CLI", "implied", 1, 2),
            0x78: ("SEI", "implied", 1, 2),
            0xB8: ("CLV", "implied", 1, 2),
            0xD8: ("CLD", "implied", 1, 2),
            0xF8: ("SED", "implied", 1, 2),
            # No Operation
            0xEA: ("NOP", "implied", 1, 2),
            # Unofficial/Undocumented opcodes commonly used in NES games
            0x1A: ("NOP", "implied", 1, 2),  # Unofficial NOP
            0x3A: ("NOP", "implied", 1, 2),  # Unofficial NOP
            0x5A: ("NOP", "implied", 1, 2),  # Unofficial NOP
            0x7A: ("NOP", "implied", 1, 2),  # Unofficial NOP
            0xDA: ("NOP", "implied", 1, 2),  # Unofficial NOP
            0xFA: ("NOP", "implied", 1, 2),  # Unofficial NOP
            0x80: ("NOP", "immediate", 2, 2),  # Unofficial NOP with immediate
            0x82: ("NOP", "immediate", 2, 2),  # Unofficial NOP with immediate
            0x89: ("NOP", "immediate", 2, 2),  # Unofficial NOP with immediate
            0xC2: ("NOP", "immediate", 2, 2),  # Unofficial NOP with immediate
            0xE2: ("NOP", "immediate", 2, 2),  # Unofficial NOP with immediate
            0x04: ("NOP", "zero_page", 2, 3),  # Unofficial NOP
            0x44: ("NOP", "zero_page", 2, 3),  # Unofficial NOP
            0x64: ("NOP", "zero_page", 2, 3),  # Unofficial NOP
            0x14: ("NOP", "zero_page_x", 2, 4),  # Unofficial NOP
            0x34: ("NOP", "zero_page_x", 2, 4),  # Unofficial NOP
            0x54: ("NOP", "zero_page_x", 2, 4),  # Unofficial NOP
            0x74: ("NOP", "zero_page_x", 2, 4),  # Unofficial NOP
            0xD4: ("NOP", "zero_page_x", 2, 4),  # Unofficial NOP
            0xF4: ("NOP", "zero_page_x", 2, 4),  # Unofficial NOP
            0x0C: ("NOP", "absolute", 3, 4),  # Unofficial NOP
            0x1C: ("NOP", "absolute_x", 3, 4),  # Unofficial NOP
            0x3C: ("NOP", "absolute_x", 3, 4),  # Unofficial NOP
            0x5C: ("NOP", "absolute_x", 3, 4),  # Unofficial NOP
            0x7C: ("NOP", "absolute_x", 3, 4),  # Unofficial NOP
            0xDC: ("NOP", "absolute_x", 3, 4),  # Unofficial NOP
            0xFC: ("NOP", "absolute_x", 3, 4),  # Unofficial NOP
            # LAX - Load Accumulator and X
            0xA7: ("LAX", "zero_page", 2, 3),
            0xB7: ("LAX", "zero_page_y", 2, 4),
            0xAF: ("LAX", "absolute", 3, 4),
            0xBF: ("LAX", "absolute_y", 3, 4),
            0xA3: ("LAX", "indexed_indirect", 2, 6),
            0xB3: ("LAX", "indirect_indexed", 2, 5),
            # SAX - Store Accumulator AND X
            0x87: ("SAX", "zero_page", 2, 3),
            0x97: ("SAX", "zero_page_y", 2, 4),
            0x8F: ("SAX", "absolute", 3, 4),
            0x83: ("SAX", "indexed_indirect", 2, 6),
            # DCP - Decrement and Compare
            0xC7: ("DCP", "zero_page", 2, 5),
            0xD7: ("DCP", "zero_page_x", 2, 6),
            0xCF: ("DCP", "absolute", 3, 6),
            0xDF: ("DCP", "absolute_x", 3, 7),
            0xDB: ("DCP", "absolute_y", 3, 7),
            0xC3: ("DCP", "indexed_indirect", 2, 8),
            0xD3: ("DCP", "indirect_indexed", 2, 8),
            # ISC - Increment and Subtract with Carry
            0xE7: ("ISC", "zero_page", 2, 5),
            0xF7: ("ISC", "zero_page_x", 2, 6),
            0xEF: ("ISC", "absolute", 3, 6),
            0xFF: ("ISC", "absolute_x", 3, 7),
            0xFB: ("ISC", "absolute_y", 3, 7),
            0xE3: ("ISC", "indexed_indirect", 2, 8),
            0xF3: ("ISC", "indirect_indexed", 2, 8),
            # SLO - Shift Left and OR
            0x07: ("SLO", "zero_page", 2, 5),
            0x17: ("SLO", "zero_page_x", 2, 6),
            0x0F: ("SLO", "absolute", 3, 6),
            0x1F: ("SLO", "absolute_x", 3, 7),
            0x1B: ("SLO", "absolute_y", 3, 7),
            0x03: ("SLO", "indexed_indirect", 2, 8),
            0x13: ("SLO", "indirect_indexed", 2, 8),
            # RLA - Rotate Left and AND
            0x27: ("RLA", "zero_page", 2, 5),
            0x37: ("RLA", "zero_page_x", 2, 6),
            0x2F: ("RLA", "absolute", 3, 6),
            0x3F: ("RLA", "absolute_x", 3, 7),
            0x3B: ("RLA", "absolute_y", 3, 7),
            0x23: ("RLA", "indexed_indirect", 2, 8),
            0x33: ("RLA", "indirect_indexed", 2, 8),
            # SRE - Shift Right and EOR
            0x47: ("SRE", "zero_page", 2, 5),
            0x57: ("SRE", "zero_page_x", 2, 6),
            0x4F: ("SRE", "absolute", 3, 6),
            0x5F: ("SRE", "absolute_x", 3, 7),
            0x5B: ("SRE", "absolute_y", 3, 7),
            0x43: ("SRE", "indexed_indirect", 2, 8),
            0x53: ("SRE", "indirect_indexed", 2, 8),
            # RRA - Rotate Right and Add with Carry
            0x67: ("RRA", "zero_page", 2, 5),
            0x77: ("RRA", "zero_page_x", 2, 6),
            0x6F: ("RRA", "absolute", 3, 6),
            0x7F: ("RRA", "absolute_x", 3, 7),
            0x7B: ("RRA", "absolute_y", 3, 7),
            0x63: ("RRA", "indexed_indirect", 2, 8),
            0x73: ("RRA", "indirect_indexed", 2, 8),
        }

    def reset(self):
        """Reset the CPU to initial state"""
        self.A = 0
        self.X = 0
        self.Y = 0
        self.S = 0xFD
        self.C = 0
        self.Z = 0
        self.I = 1
        self.D = 0
        self.B = 0
        self.V = 0
        self.N = 0

        # Read reset vector
        low = self.memory.read(0xFFFC)
        high = self.memory.read(0xFFFD)
        self.PC = (high << 8) | low

        self.cycles = 0

    def get_status_byte(self):
        """Get the status register as a byte"""
        return (
            (self.N << 7)
            | (self.V << 6)
            | (1 << 5)
            | (self.B << 4)
            | (self.D << 3)
            | (self.I << 2)
            | (self.Z << 1)
            | self.C
        )

    def set_status_byte(self, value):
        """Set the status register from a byte"""
        self.N = (value >> 7) & 1
        self.V = (value >> 6) & 1
        self.B = (value >> 4) & 1
        self.D = (value >> 3) & 1
        self.I = (value >> 2) & 1
        self.Z = (value >> 1) & 1
        self.C = value & 1

    def set_zero_negative(self, value):
        """Set zero and negative flags based on value"""
        self.Z = 1 if value == 0 else 0
        self.N = 1 if value & 0x80 else 0

    def push_stack(self, value):
        """Push a byte onto the stack"""
        self.memory.write(0x0100 + self.S, value)
        self.S = (self.S - 1) & 0xFF

    def pop_stack(self):
        """Pop a byte from the stack"""
        self.S = (self.S + 1) & 0xFF
        return self.memory.read(0x0100 + self.S)

    def step(self):
        """Execute one instruction"""
        # Handle DMA cycles first
        if self.dma_cycles > 0:
            self.dma_cycles -= 1
            return

        if self.cycles > 0:
            self.cycles -= 1
            return

        opcode = self.memory.read(self.PC)
        self.PC = (self.PC + 1) & 0xFFFF

        if opcode not in self.instructions:
            print(f"Unknown opcode: 0x{opcode:02X}")
            return

        instruction, addressing_mode, length, cycles = self.instructions[opcode]
        self.cycles = cycles - 1  # -1 because we already used one cycle

        # Get operand based on addressing mode
        operand = self.get_operand(addressing_mode, length - 1)

        # Execute instruction
        getattr(self, f"execute_{instruction.lower()}")(operand, addressing_mode)

    def add_dma_cycles(self, cycles):
        """Add DMA cycles that will delay CPU execution"""
        self.dma_cycles += cycles

    def get_operand(self, addressing_mode, operand_length):
        """Get operand based on addressing mode"""
        if addressing_mode == "implied" or addressing_mode == "accumulator":
            return None
        elif addressing_mode == "immediate":
            value = self.memory.read(self.PC)
            self.PC = (self.PC + 1) & 0xFFFF
            return value
        elif addressing_mode == "zero_page":
            addr = self.memory.read(self.PC)
            self.PC = (self.PC + 1) & 0xFFFF
            return addr
        elif addressing_mode == "zero_page_x":
            addr = (self.memory.read(self.PC) + self.X) & 0xFF
            self.PC = (self.PC + 1) & 0xFFFF
            return addr
        elif addressing_mode == "zero_page_y":
            addr = (self.memory.read(self.PC) + self.Y) & 0xFF
            self.PC = (self.PC + 1) & 0xFFFF
            return addr
        elif addressing_mode == "absolute":
            low = self.memory.read(self.PC)
            high = self.memory.read(self.PC + 1)
            self.PC = (self.PC + 2) & 0xFFFF
            return (high << 8) | low
        elif addressing_mode == "absolute_x":
            low = self.memory.read(self.PC)
            high = self.memory.read(self.PC + 1)
            self.PC = (self.PC + 2) & 0xFFFF
            addr = ((high << 8) | low) + self.X
            return addr & 0xFFFF
        elif addressing_mode == "absolute_y":
            low = self.memory.read(self.PC)
            high = self.memory.read(self.PC + 1)
            self.PC = (self.PC + 2) & 0xFFFF
            addr = ((high << 8) | low) + self.Y
            return addr & 0xFFFF
        elif addressing_mode == "relative":
            offset = self.memory.read(self.PC)
            self.PC = (self.PC + 1) & 0xFFFF
            if offset & 0x80:  # Negative
                offset = offset - 256
            return (self.PC + offset) & 0xFFFF
        elif addressing_mode == "indirect":
            low = self.memory.read(self.PC)
            high = self.memory.read(self.PC + 1)
            self.PC = (self.PC + 2) & 0xFFFF
            addr = (high << 8) | low
            # 6502 bug: if low byte is 0xFF, high byte wraps around
            if low == 0xFF:
                target_low = self.memory.read(addr)
                target_high = self.memory.read(addr & 0xFF00)
            else:
                target_low = self.memory.read(addr)
                target_high = self.memory.read(addr + 1)
            return (target_high << 8) | target_low
        elif addressing_mode == "indexed_indirect":
            addr = (self.memory.read(self.PC) + self.X) & 0xFF
            self.PC = (self.PC + 1) & 0xFFFF
            low = self.memory.read(addr)
            high = self.memory.read((addr + 1) & 0xFF)
            return (high << 8) | low
        elif addressing_mode == "indirect_indexed":
            addr = self.memory.read(self.PC)
            self.PC = (self.PC + 1) & 0xFFFF
            low = self.memory.read(addr)
            high = self.memory.read((addr + 1) & 0xFF)
            target = ((high << 8) | low) + self.Y
            return target & 0xFFFF

    # Instruction implementations
    def execute_lda(self, operand, addressing_mode):
        if addressing_mode == "immediate":
            self.A = operand
        else:
            self.A = self.memory.read(operand)
        self.set_zero_negative(self.A)

    def execute_ldx(self, operand, addressing_mode):
        if addressing_mode == "immediate":
            self.X = operand
        else:
            self.X = self.memory.read(operand)
        self.set_zero_negative(self.X)

    def execute_ldy(self, operand, addressing_mode):
        if addressing_mode == "immediate":
            self.Y = operand
        else:
            self.Y = self.memory.read(operand)
        self.set_zero_negative(self.Y)

    def execute_sta(self, operand, addressing_mode):
        self.memory.write(operand, self.A)

    def execute_stx(self, operand, addressing_mode):
        self.memory.write(operand, self.X)

    def execute_sty(self, operand, addressing_mode):
        self.memory.write(operand, self.Y)

    def execute_tax(self, operand, addressing_mode):
        self.X = self.A
        self.set_zero_negative(self.X)

    def execute_tay(self, operand, addressing_mode):
        self.Y = self.A
        self.set_zero_negative(self.Y)

    def execute_tsx(self, operand, addressing_mode):
        self.X = self.S
        self.set_zero_negative(self.X)

    def execute_txa(self, operand, addressing_mode):
        self.A = self.X
        self.set_zero_negative(self.A)

    def execute_txs(self, operand, addressing_mode):
        self.S = self.X

    def execute_tya(self, operand, addressing_mode):
        self.A = self.Y
        self.set_zero_negative(self.A)

    def execute_pha(self, operand, addressing_mode):
        self.push_stack(self.A)

    def execute_pla(self, operand, addressing_mode):
        self.A = self.pop_stack()
        self.set_zero_negative(self.A)

    def execute_php(self, operand, addressing_mode):
        self.push_stack(self.get_status_byte() | 0x10)  # B flag set

    def execute_plp(self, operand, addressing_mode):
        self.set_status_byte(self.pop_stack())
        self.B = 0  # B flag always 0

    def execute_adc(self, operand, addressing_mode):
        if addressing_mode == "immediate":
            value = operand
        else:
            value = self.memory.read(operand)

        result = self.A + value + self.C

        # Set overflow flag
        self.V = 1 if ((self.A ^ result) & (value ^ result) & 0x80) else 0

        # Set carry flag
        self.C = 1 if result > 255 else 0

        self.A = result & 0xFF
        self.set_zero_negative(self.A)

    def execute_sbc(self, operand, addressing_mode):
        if addressing_mode == "immediate":
            value = operand
        else:
            value = self.memory.read(operand)

        result = self.A - value - (1 - self.C)

        # Set overflow flag
        self.V = 1 if ((self.A ^ result) & (~value ^ result) & 0x80) else 0

        # Set carry flag (inverted for subtraction)
        self.C = 0 if result < 0 else 1

        self.A = result & 0xFF
        self.set_zero_negative(self.A)

    def execute_and(self, operand, addressing_mode):
        if addressing_mode == "immediate":
            value = operand
        else:
            value = self.memory.read(operand)

        self.A = self.A & value
        self.set_zero_negative(self.A)

    def execute_eor(self, operand, addressing_mode):
        if addressing_mode == "immediate":
            value = operand
        else:
            value = self.memory.read(operand)

        self.A = self.A ^ value
        self.set_zero_negative(self.A)

    def execute_ora(self, operand, addressing_mode):
        if addressing_mode == "immediate":
            value = operand
        else:
            value = self.memory.read(operand)

        self.A = self.A | value
        self.set_zero_negative(self.A)

    def execute_asl(self, operand, addressing_mode):
        if addressing_mode == "accumulator":
            self.C = 1 if self.A & 0x80 else 0
            self.A = (self.A << 1) & 0xFF
            self.set_zero_negative(self.A)
        else:
            value = self.memory.read(operand)
            self.C = 1 if value & 0x80 else 0
            value = (value << 1) & 0xFF
            self.memory.write(operand, value)
            self.set_zero_negative(value)

    def execute_lsr(self, operand, addressing_mode):
        if addressing_mode == "accumulator":
            self.C = self.A & 1
            self.A = self.A >> 1
            self.set_zero_negative(self.A)
        else:
            value = self.memory.read(operand)
            self.C = value & 1
            value = value >> 1
            self.memory.write(operand, value)
            self.set_zero_negative(value)

    def execute_rol(self, operand, addressing_mode):
        if addressing_mode == "accumulator":
            old_carry = self.C
            self.C = 1 if self.A & 0x80 else 0
            self.A = ((self.A << 1) | old_carry) & 0xFF
            self.set_zero_negative(self.A)
        else:
            value = self.memory.read(operand)
            old_carry = self.C
            self.C = 1 if value & 0x80 else 0
            value = ((value << 1) | old_carry) & 0xFF
            self.memory.write(operand, value)
            self.set_zero_negative(value)

    def execute_ror(self, operand, addressing_mode):
        if addressing_mode == "accumulator":
            old_carry = self.C
            self.C = self.A & 1
            self.A = (self.A >> 1) | (old_carry << 7)
            self.set_zero_negative(self.A)
        else:
            value = self.memory.read(operand)
            old_carry = self.C
            self.C = value & 1
            value = (value >> 1) | (old_carry << 7)
            self.memory.write(operand, value)
            self.set_zero_negative(value)

    def execute_cmp(self, operand, addressing_mode):
        if addressing_mode == "immediate":
            value = operand
        else:
            value = self.memory.read(operand)

        result = self.A - value
        self.C = 1 if self.A >= value else 0
        self.set_zero_negative(result & 0xFF)

    def execute_cpx(self, operand, addressing_mode):
        if addressing_mode == "immediate":
            value = operand
        else:
            value = self.memory.read(operand)

        result = self.X - value
        self.C = 1 if self.X >= value else 0
        self.set_zero_negative(result & 0xFF)

    def execute_cpy(self, operand, addressing_mode):
        if addressing_mode == "immediate":
            value = operand
        else:
            value = self.memory.read(operand)

        result = self.Y - value
        self.C = 1 if self.Y >= value else 0
        self.set_zero_negative(result & 0xFF)

    def execute_bit(self, operand, addressing_mode):
        """Bit Test - Test bits in memory with accumulator"""
        value = self.memory.read(operand)

        # Set zero flag based on A & value
        self.Z = 1 if (self.A & value) == 0 else 0

        # Set overflow flag to bit 6 of value
        self.V = 1 if value & 0x40 else 0

        # Set negative flag to bit 7 of value
        self.N = 1 if value & 0x80 else 0

    def execute_inc(self, operand, addressing_mode):
        value = (self.memory.read(operand) + 1) & 0xFF
        self.memory.write(operand, value)
        self.set_zero_negative(value)

    def execute_inx(self, operand, addressing_mode):
        self.X = (self.X + 1) & 0xFF
        self.set_zero_negative(self.X)

    def execute_iny(self, operand, addressing_mode):
        self.Y = (self.Y + 1) & 0xFF
        self.set_zero_negative(self.Y)

    def execute_dec(self, operand, addressing_mode):
        value = (self.memory.read(operand) - 1) & 0xFF
        self.memory.write(operand, value)
        self.set_zero_negative(value)

    def execute_dex(self, operand, addressing_mode):
        self.X = (self.X - 1) & 0xFF
        self.set_zero_negative(self.X)

    def execute_dey(self, operand, addressing_mode):
        self.Y = (self.Y - 1) & 0xFF
        self.set_zero_negative(self.Y)

    def execute_bpl(self, operand, addressing_mode):
        if self.N == 0:
            self.PC = operand

    def execute_bmi(self, operand, addressing_mode):
        if self.N == 1:
            self.PC = operand

    def execute_bvc(self, operand, addressing_mode):
        if self.V == 0:
            self.PC = operand

    def execute_bvs(self, operand, addressing_mode):
        if self.V == 1:
            self.PC = operand

    def execute_bcc(self, operand, addressing_mode):
        if self.C == 0:
            self.PC = operand

    def execute_bcs(self, operand, addressing_mode):
        if self.C == 1:
            self.PC = operand

    def execute_bne(self, operand, addressing_mode):
        if self.Z == 0:
            self.PC = operand

    def execute_beq(self, operand, addressing_mode):
        if self.Z == 1:
            self.PC = operand

    def execute_jmp(self, operand, addressing_mode):
        self.PC = operand

    def execute_jsr(self, operand, addressing_mode):
        return_addr = (self.PC - 1) & 0xFFFF
        self.push_stack((return_addr >> 8) & 0xFF)
        self.push_stack(return_addr & 0xFF)
        self.PC = operand

    def execute_rts(self, operand, addressing_mode):
        low = self.pop_stack()
        high = self.pop_stack()
        self.PC = (((high << 8) | low) + 1) & 0xFFFF

    def execute_brk(self, operand, addressing_mode):
        self.PC = (self.PC + 1) & 0xFFFF
        self.push_stack((self.PC >> 8) & 0xFF)
        self.push_stack(self.PC & 0xFF)
        self.push_stack(self.get_status_byte() | 0x10)
        self.I = 1
        low = self.memory.read(0xFFFE)
        high = self.memory.read(0xFFFF)
        self.PC = (high << 8) | low

    def execute_rti(self, operand, addressing_mode):
        self.set_status_byte(self.pop_stack())
        low = self.pop_stack()
        high = self.pop_stack()
        self.PC = (high << 8) | low

    def execute_clc(self, operand, addressing_mode):
        self.C = 0

    def execute_sec(self, operand, addressing_mode):
        self.C = 1

    def execute_cli(self, operand, addressing_mode):
        self.I = 0

    def execute_sei(self, operand, addressing_mode):
        self.I = 1

    def execute_clv(self, operand, addressing_mode):
        self.V = 0

    def execute_cld(self, operand, addressing_mode):
        self.D = 0

    def execute_sed(self, operand, addressing_mode):
        self.D = 1

    def execute_nop(self, operand, addressing_mode):
        # Handle different NOP variants
        if addressing_mode == "immediate":
            pass  # Consume the immediate operand but do nothing
        elif addressing_mode in ["zero_page", "zero_page_x", "absolute", "absolute_x"]:
            # These NOPs read from memory but don't do anything with the value
            if operand is not None:
                self.memory.read(operand)
        # Implied NOPs do nothing

    # Unofficial opcode implementations
    def execute_lax(self, operand, addressing_mode):
        """Load Accumulator and X - Load the same value into both A and X"""
        if addressing_mode == "immediate":
            value = operand
        else:
            value = self.memory.read(operand)

        self.A = value
        self.X = value
        self.set_zero_negative(value)

    def execute_sax(self, operand, addressing_mode):
        """Store Accumulator AND X - Store A & X to memory"""
        value = self.A & self.X
        self.memory.write(operand, value)

    def execute_dcp(self, operand, addressing_mode):
        """Decrement and Compare - Decrement memory then compare with A"""
        value = (self.memory.read(operand) - 1) & 0xFF
        self.memory.write(operand, value)

        # Compare with A
        result = self.A - value
        self.C = 1 if self.A >= value else 0
        self.set_zero_negative(result & 0xFF)

    def execute_isc(self, operand, addressing_mode):
        """Increment and Subtract with Carry - Increment memory then SBC"""
        value = (self.memory.read(operand) + 1) & 0xFF
        self.memory.write(operand, value)

        # Subtract with carry
        result = self.A - value - (1 - self.C)

        # Set overflow flag
        self.V = 1 if ((self.A ^ result) & (~value ^ result) & 0x80) else 0

        # Set carry flag (inverted for subtraction)
        self.C = 0 if result < 0 else 1

        self.A = result & 0xFF
        self.set_zero_negative(self.A)

    def execute_slo(self, operand, addressing_mode):
        """Shift Left and OR - ASL memory then OR with A"""
        value = self.memory.read(operand)

        # ASL
        self.C = 1 if value & 0x80 else 0
        value = (value << 1) & 0xFF
        self.memory.write(operand, value)

        # OR with A
        self.A = self.A | value
        self.set_zero_negative(self.A)

    def execute_rla(self, operand, addressing_mode):
        """Rotate Left and AND - ROL memory then AND with A"""
        value = self.memory.read(operand)

        # ROL
        old_carry = self.C
        self.C = 1 if value & 0x80 else 0
        value = ((value << 1) | old_carry) & 0xFF
        self.memory.write(operand, value)

        # AND with A
        self.A = self.A & value
        self.set_zero_negative(self.A)

    def execute_sre(self, operand, addressing_mode):
        """Shift Right and EOR - LSR memory then EOR with A"""
        value = self.memory.read(operand)

        # LSR
        self.C = value & 1
        value = value >> 1
        self.memory.write(operand, value)

        # EOR with A
        self.A = self.A ^ value
        self.set_zero_negative(self.A)

    def execute_rra(self, operand, addressing_mode):
        """Rotate Right and Add with Carry - ROR memory then ADC"""
        value = self.memory.read(operand)

        # ROR
        old_carry = self.C
        self.C = value & 1
        value = (value >> 1) | (old_carry << 7)
        self.memory.write(operand, value)

        # ADC
        result = self.A + value + self.C

        # Set overflow flag
        self.V = 1 if ((self.A ^ result) & (value ^ result) & 0x80) else 0

        # Set carry flag
        self.C = 1 if result > 255 else 0

        self.A = result & 0xFF
        self.set_zero_negative(self.A)
