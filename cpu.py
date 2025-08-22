"""
NES 6502 CPU Emulator
Implements the MOS Technology 6502 processor used in the NES
Hardware-accurate cycle timing and behavior based on reference implementation
"""

from utils import debug_print


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

        # Cycle tracking
        self.cycles = 0
        self.dma_cycles = 0  # Additional cycles from DMA operations
        self.total_cycles = 0  # Total cycles executed
        self.odd_cycle = 0  # Track odd/even cycles for DMA timing

        # Interrupt handling
        self.interrupt_pending = None  # NOI, NMI, IRQ, RSI
        self.interrupt_state = (
            0  # 0 = normal, 1 = branch pending, 2 = interrupt pending
        )

        # CLI/SEI/PLP latency tracking for interrupt flag changes
        self.interrupt_inhibit = 1  # Effective interrupt disable (tracks delay)
        self.interrupt_delay_counter = 0  # Number of full instructions to wait before applying to interrupt_inhibit
        self.interrupt_delay_pending = False  # Back-compat flag for tests
        self.interrupt_delay_value = None  # Back-compat: target I value after delay

        # Branch state tracking
        self.branch_pending = False
        self.branch_target = 0

        # Cycle lookup table for hardware-accurate timing
        self.cycle_lookup = [
            # 0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F
            7,
            6,
            2,
            8,
            3,
            3,
            5,
            5,
            3,
            2,
            2,
            2,
            4,
            4,
            6,
            6,  # 0
            2,
            5,
            2,
            8,
            4,
            4,
            6,
            6,
            2,
            4,
            2,
            7,
            4,
            4,
            7,
            7,  # 1
            6,
            6,
            2,
            8,
            3,
            3,
            5,
            5,
            4,
            2,
            2,
            2,
            4,
            4,
            6,
            6,  # 2
            2,
            5,
            2,
            8,
            4,
            4,
            6,
            6,
            2,
            4,
            2,
            7,
            4,
            4,
            7,
            7,  # 3
            6,
            6,
            2,
            8,
            3,
            3,
            5,
            5,
            3,
            2,
            2,
            2,
            3,
            4,
            6,
            6,  # 4
            2,
            5,
            2,
            8,
            4,
            4,
            6,
            6,
            2,
            4,
            2,
            7,
            4,
            4,
            7,
            7,  # 5
            6,
            6,
            2,
            8,
            3,
            3,
            5,
            5,
            4,
            2,
            2,
            2,
            5,
            4,
            6,
            6,  # 6
            2,
            5,
            2,
            8,
            4,
            4,
            6,
            6,
            2,
            4,
            2,
            7,
            4,
            4,
            7,
            7,  # 7
            2,
            6,
            2,
            6,
            3,
            3,
            3,
            3,
            2,
            2,
            2,
            2,
            4,
            4,
            4,
            4,  # 8
            2,
            6,
            2,
            6,
            4,
            4,
            4,
            4,
            2,
            5,
            2,
            5,
            5,
            5,
            5,
            5,  # 9
            2,
            6,
            2,
            6,
            3,
            3,
            3,
            3,
            2,
            2,
            2,
            2,
            4,
            4,
            4,
            4,  # A
            2,
            5,
            2,
            5,
            4,
            4,
            4,
            4,
            2,
            4,
            2,
            4,
            4,
            4,
            4,
            4,  # B
            2,
            6,
            2,
            8,
            3,
            3,
            5,
            5,
            2,
            2,
            2,
            2,
            4,
            4,
            6,
            6,  # C
            2,
            5,
            2,
            8,
            4,
            4,
            6,
            6,
            2,
            4,
            2,
            7,
            4,
            4,
            7,
            7,  # D
            2,
            6,
            2,
            8,
            3,
            3,
            5,
            5,
            2,
            2,
            2,
            2,
            4,
            4,
            6,
            6,  # E
            2,
            5,
            2,
            8,
            4,
            4,
            6,
            6,
            2,
            4,
            2,
            7,
            4,
            4,
            7,
            7,  # F
        ]

        # Instruction set with optimized dispatch
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
            # Additional missing unofficial opcodes
            0xEB: ("SBC", "immediate", 2, 2),  # Unofficial SBC
            0xBB: ("LAX", "absolute_y", 3, 4),  # LAX - Load Accumulator and X
            0x9B: ("TAS", "absolute_y", 3, 5),  # TAS - Transfer A and X to Stack
            0x02: ("KIL", "implied", 1, 2),  # KIL - Kill (jam/halt processor)
            0x12: ("KIL", "implied", 1, 2),  # KIL
            0x22: ("KIL", "implied", 1, 2),  # KIL
            0x32: ("KIL", "implied", 1, 2),  # KIL
            0x42: ("KIL", "implied", 1, 2),  # KIL
            0x52: ("KIL", "implied", 1, 2),  # KIL
            0x62: ("KIL", "implied", 1, 2),  # KIL
            0x72: ("KIL", "implied", 1, 2),  # KIL
            0x92: ("KIL", "implied", 1, 2),  # KIL
            0xB2: ("KIL", "implied", 1, 2),  # KIL
            0xD2: ("KIL", "implied", 1, 2),  # KIL
            0xF2: ("KIL", "implied", 1, 2),  # KIL
            0x9E: ("SHX", "absolute_y", 3, 5),  # SHX - Store X AND (High Byte + 1)
            0x9F: (
                "SHA",
                "absolute_y",
                3,
                5,
            ),  # SHA - Store A AND X AND (High Byte + 1)
            0x93: ("SHA", "indirect_indexed", 2, 6),  # SHA
            0x4B: ("ALR", "immediate", 2, 2),  # ALR - AND then LSR
        }

        # Optimized instruction dispatch table for performance
        self.instruction_dispatch = {
            0xA9: self.execute_lda,
            0xA5: self.execute_lda,
            0xB5: self.execute_lda,
            0xAD: self.execute_lda,
            0xBD: self.execute_lda,
            0xB9: self.execute_lda,
            0xA1: self.execute_lda,
            0xB1: self.execute_lda,
            0xA2: self.execute_ldx,
            0xA6: self.execute_ldx,
            0xB6: self.execute_ldx,
            0xAE: self.execute_ldx,
            0xBE: self.execute_ldx,
            0xA0: self.execute_ldy,
            0xA4: self.execute_ldy,
            0xB4: self.execute_ldy,
            0xAC: self.execute_ldy,
            0xBC: self.execute_ldy,
            0x85: self.execute_sta,
            0x95: self.execute_sta,
            0x8D: self.execute_sta,
            0x9D: self.execute_sta,
            0x99: self.execute_sta,
            0x81: self.execute_sta,
            0x91: self.execute_sta,
            0x86: self.execute_stx,
            0x96: self.execute_stx,
            0x8E: self.execute_stx,
            0x84: self.execute_sty,
            0x94: self.execute_sty,
            0x8C: self.execute_sty,
            0xAA: self.execute_tax,
            0xA8: self.execute_tay,
            0xBA: self.execute_tsx,
            0x8A: self.execute_txa,
            0x9A: self.execute_txs,
            0x98: self.execute_tya,
            0x48: self.execute_pha,
            0x68: self.execute_pla,
            0x08: self.execute_php,
            0x28: self.execute_plp,
            0x69: self.execute_adc,
            0x65: self.execute_adc,
            0x75: self.execute_adc,
            0x6D: self.execute_adc,
            0x7D: self.execute_adc,
            0x79: self.execute_adc,
            0x61: self.execute_adc,
            0x71: self.execute_adc,
            0xE9: self.execute_sbc,
            0xE5: self.execute_sbc,
            0xF5: self.execute_sbc,
            0xED: self.execute_sbc,
            0xFD: self.execute_sbc,
            0xF9: self.execute_sbc,
            0xE1: self.execute_sbc,
            0xF1: self.execute_sbc,
            0x29: self.execute_and,
            0x25: self.execute_and,
            0x35: self.execute_and,
            0x2D: self.execute_and,
            0x3D: self.execute_and,
            0x39: self.execute_and,
            0x21: self.execute_and,
            0x31: self.execute_and,
            0x49: self.execute_eor,
            0x45: self.execute_eor,
            0x55: self.execute_eor,
            0x4D: self.execute_eor,
            0x5D: self.execute_eor,
            0x59: self.execute_eor,
            0x41: self.execute_eor,
            0x51: self.execute_eor,
            0x09: self.execute_ora,
            0x05: self.execute_ora,
            0x15: self.execute_ora,
            0x0D: self.execute_ora,
            0x1D: self.execute_ora,
            0x19: self.execute_ora,
            0x01: self.execute_ora,
            0x11: self.execute_ora,
            0x0A: self.execute_asl,
            0x06: self.execute_asl,
            0x16: self.execute_asl,
            0x0E: self.execute_asl,
            0x1E: self.execute_asl,
            0x4A: self.execute_lsr,
            0x46: self.execute_lsr,
            0x56: self.execute_lsr,
            0x4E: self.execute_lsr,
            0x5E: self.execute_lsr,
            0x2A: self.execute_rol,
            0x26: self.execute_rol,
            0x36: self.execute_rol,
            0x2E: self.execute_rol,
            0x3E: self.execute_rol,
            0x6A: self.execute_ror,
            0x66: self.execute_ror,
            0x76: self.execute_ror,
            0x6E: self.execute_ror,
            0x7E: self.execute_ror,
            0xC9: self.execute_cmp,
            0xC5: self.execute_cmp,
            0xD5: self.execute_cmp,
            0xCD: self.execute_cmp,
            0xDD: self.execute_cmp,
            0xD9: self.execute_cmp,
            0xC1: self.execute_cmp,
            0xD1: self.execute_cmp,
            0xE0: self.execute_cpx,
            0xE4: self.execute_cpx,
            0xEC: self.execute_cpx,
            0xC0: self.execute_cpy,
            0xC4: self.execute_cpy,
            0xCC: self.execute_cpy,
            0x24: self.execute_bit,
            0x2C: self.execute_bit,
            0xE6: self.execute_inc,
            0xF6: self.execute_inc,
            0xEE: self.execute_inc,
            0xFE: self.execute_inc,
            0xE8: self.execute_inx,
            0xC8: self.execute_iny,
            0xC6: self.execute_dec,
            0xD6: self.execute_dec,
            0xCE: self.execute_dec,
            0xDE: self.execute_dec,
            0xCA: self.execute_dex,
            0x88: self.execute_dey,
            0x10: self.execute_bpl,
            0x30: self.execute_bmi,
            0x50: self.execute_bvc,
            0x70: self.execute_bvs,
            0x90: self.execute_bcc,
            0xB0: self.execute_bcs,
            0xD0: self.execute_bne,
            0xF0: self.execute_beq,
            0x4C: self.execute_jmp,
            0x6C: self.execute_jmp,
            0x20: self.execute_jsr,
            0x60: self.execute_rts,
            0x00: self.execute_brk,
            0x40: self.execute_rti,
            0x18: self.execute_clc,
            0x38: self.execute_sec,
            0x58: self.execute_cli,
            0x78: self.execute_sei,
            0xB8: self.execute_clv,
            0xD8: self.execute_cld,
            0xF8: self.execute_sed,
            0xEA: self.execute_nop,
            # Add NOP variants
            0x1A: self.execute_nop,
            0x3A: self.execute_nop,
            0x5A: self.execute_nop,
            0x7A: self.execute_nop,
            0xDA: self.execute_nop,
            0xFA: self.execute_nop,
            0x80: self.execute_nop,
            0x82: self.execute_nop,
            0x89: self.execute_nop,
            0xC2: self.execute_nop,
            0xE2: self.execute_nop,
            0x04: self.execute_nop,
            0x44: self.execute_nop,
            0x64: self.execute_nop,
            0x14: self.execute_nop,
            0x34: self.execute_nop,
            0x54: self.execute_nop,
            0x74: self.execute_nop,
            0xD4: self.execute_nop,
            0xF4: self.execute_nop,
            0x0C: self.execute_nop,
            0x1C: self.execute_nop,
            0x3C: self.execute_nop,
            0x5C: self.execute_nop,
            0x7C: self.execute_nop,
            0xDC: self.execute_nop,
            0xFC: self.execute_nop,
            # LAX unofficial instructions
            0xBB: self.execute_lax,
            0xBF: self.execute_lax,
            0xB3: self.execute_lax,
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
        self.total_cycles = 0
        self.odd_cycle = 0
        self.interrupt_pending = None
        self.interrupt_state = 0
        self.branch_pending = False

        # Initialize interrupt latency state
        self.interrupt_inhibit = self.I  # Initialize to match I flag
        self.interrupt_delay_counter = 0
        self.interrupt_delay_pending = False
        self.interrupt_delay_value = None

    def step(self):
        """Execute one CPU cycle with hardware-accurate timing"""
        # Track odd/even cycles for accurate DMA timing
        self.odd_cycle = 1 - self.odd_cycle
        self.total_cycles += 1

        # Handle DMA cycles first (CPU is halted during DMA)
        if self.dma_cycles > 0:
            self.dma_cycles -= 1
            return 1

        # If we're in the middle of an instruction, just count down cycles
        if self.cycles > 0:
            self.cycles -= 1
            return 1

        # RustyNES-style: Execute complete instruction and return total cycles consumed
        cycles_consumed = self.run_instruction()

        # Set cycles to count down for the remaining cycles
        self.cycles = cycles_consumed - 1  # -1 because we already used one cycle
        return 1

    def run_instruction(self):
        """Execute complete instruction following RustyNES model - returns total cycles consumed"""
        # Store whether there was a delay active before this instruction started
        delay_was_active = self.interrupt_delay_counter > 0
        
        # Apply any deferred interrupt recognition changes from previous instruction FIRST,
        # then check for pending interrupts. This matches 6502 order at instruction boundary.
        if self.interrupt_delay_counter > 0:
            self.interrupt_delay_counter -= 1
            self.interrupt_delay_pending = self.interrupt_delay_counter > 0
            if self.interrupt_delay_counter == 0:
                self.interrupt_inhibit = self.I
                debug_print(
                    f"CPU: Interrupt inhibit updated at boundary: I={self.I}, interrupt_inhibit={self.interrupt_inhibit}"
                )

        # Fetch opcode first to check for BRK special case
        old_pc = self.PC
        opcode = self.memory.read(self.PC)
        self.PC = (self.PC + 1) & 0xFFFF

        # Handle pending interrupts at the start of a new instruction
        # NMI is never masked and always processed immediately
        # IRQ can only be taken when interrupt_inhibit == 0 AND there was no delay active
        # when this instruction started (ensures one instruction executes after CLI)
        # Special case: If NMI is pending and current instruction is BRK, let BRK execute first
        # and handle NMI during BRK execution (for BRK signature behavior)
        if self.interrupt_pending and self.interrupt_state == 0 and opcode != 0x00:
            if (self.interrupt_pending == "NMI") or (
                self.interrupt_pending == "IRQ" and self.interrupt_inhibit == 0 and not delay_was_active
            ):
                debug_print(
                    f"CPU: Starting interrupt handling for {self.interrupt_pending}, PC=0x{self.PC:04X}"
                )
                self._handle_interrupt()
                self.interrupt_pending = None
                self.interrupt_state = 0
                return 7  # Interrupt handling takes 7 cycles total

        # Note whether a delay was already pending before this instruction began
        pre_delay_counter = self.interrupt_delay_counter

        # Get base cycle count from lookup table for hardware accuracy
        base_cycles = self.cycle_lookup[opcode]

        if opcode not in self.instructions:
            print(f"Unknown opcode: 0x{opcode:02X} at PC: 0x{self.PC-1:04X}")
            return base_cycles

        instruction, addressing_mode, length, _ = self.instructions[opcode]

        # Debug: Log instruction execution to see if we're getting stuck
        if (
            self.total_cycles % 10000 == 0
            or instruction in ["RTI", "LDA", "STA", "JMP", "BNE", "BEQ", "BCC", "BCS"]
            or old_pc == 0x8150
            or old_pc == 0x8153
            or old_pc == 0x8227
            or old_pc == 0x822E
        ):
            debug_print(
                f"CPU: Executing {instruction} at PC=0x{old_pc:04X}, opcode=0x{opcode:02X}, cycles={self.total_cycles}, length={length}"
            )

        # Fetch operand (following RustyNES fetch_operand pattern)
        pc_before_address = self.PC
        address, page_crossing_penalty = self._get_address_with_page_crossing_info(
            addressing_mode, length - 1, instruction
        )
        pc_after_address = self.PC

        # Debug: Check if PC is advancing properly
        if old_pc == 0x8150 or old_pc == 0x8153 or old_pc == 0x8227 or old_pc == 0x822E:
            address_str = f"{address:04X}" if address is not None else "0000"
            debug_print(
                f"CPU: PC progression: {old_pc:04X} -> {pc_before_address:04X} -> {pc_after_address:04X}, addressing_mode={addressing_mode}, length={length}, address=0x{address_str}"
            )

        # Execute instruction (following RustyNES instruction dispatch pattern)
        extra_cycles = 0
        if opcode in self.instruction_dispatch:
            extra_cycles = self.instruction_dispatch[opcode](address, addressing_mode)
        else:
            # Fallback to dynamic dispatch for unofficial opcodes
            extra_cycles = getattr(self, f"execute_{instruction.lower()}")(
                address, addressing_mode
            )

        # Handle return value from instruction execution
        if extra_cycles is None:
            extra_cycles = 0

        # Debug: Check if PC changed after instruction execution
        if old_pc == 0x8150 or old_pc == 0x8153:
            debug_print(f"CPU: PC after instruction execution: {self.PC:04X}")

        # Handle branch instructions with proper cycle calculation
        branch_cycles = 0
        if instruction in ["BPL", "BMI", "BVC", "BVS", "BCC", "BCS", "BNE", "BEQ"]:
            branch_cycles = self._prepare_branch(instruction, address)

        # Return total cycles consumed by this complete instruction
        total_cycles = (
            base_cycles + extra_cycles + branch_cycles + page_crossing_penalty
        )

        # Deferred interrupt recognition already applied at boundary above.
        # Keep these legacy flags in sync for tests but do not re-apply.
        if pre_delay_counter > 0:
            # No-op here; the actual decrement happened at entry.
            pass

        return total_cycles

    def execute_instruction(self):
        """Legacy method - no longer used with integrated execution model"""
        debug_print("Executing LEGACY instruction...")
        # This method is kept for compatibility but is no longer called
        pass

    def _handle_interrupt(self):
        """Handle pending interrupt"""
        old_PC = self.PC

        if self.interrupt_pending == "NMI":
            vector_addr = 0xFFFA
            debug_print(f"CPU: Handling NMI interrupt, vector=0xFFFA")
        elif self.interrupt_pending == "IRQ":
            vector_addr = 0xFFFE
            debug_print(f"CPU: Handling IRQ interrupt, vector=0xFFFE")
        elif self.interrupt_pending == "RST":
            vector_addr = 0xFFFC
            debug_print(f"CPU: Handling RESET interrupt, vector=0xFFFC")
        else:
            debug_print(f"CPU: No valid interrupt to handle: {self.interrupt_pending}")
            return

        # Push PC and status register to stack in correct 6502 order
        # 6502 pushes: high byte of PC, low byte of PC, then status
        self.push_stack((self.PC >> 8) & 0xFF)  # High byte first
        self.push_stack(self.PC & 0xFF)         # Low byte second

        # Hardware-accurate: Both NMI and IRQ clear the B flag when pushing status
        # The B flag (bit 4) and bit 5 are cleared for hardware interrupts
        status = self.get_status_byte() & 0xCF  # Clear bits 4 and 5 for interrupts
        status |= 0x20  # Set bit 5 (unused, but always set)
        self.push_stack(status)                  # Status last

        # Set interrupt disable flag (takes effect immediately)
        self.I = 1
        self.interrupt_inhibit = 1

        # Jump to interrupt vector
        low = self.memory.read(vector_addr)
        high = self.memory.read(vector_addr + 1)
        self.PC = (high << 8) | low

        debug_print(
            f"CPU: Interrupt handler jumping to 0x{self.PC:04X}, old PC=0x{old_PC:04X}"
        )

        # Clear the pending interrupt
        self.interrupt_pending = None

    def _prepare_branch(self, instruction, address):
        """Prepare branch instruction execution - returns extra cycles"""
        # Get the condition for the branch
        conditions = {
            "BPL": self.N == 0,
            "BMI": self.N == 1,
            "BVC": self.V == 0,
            "BVS": self.V == 1,
            "BCC": self.C == 0,
            "BCS": self.C == 1,
            "BNE": self.Z == 0,
            "BEQ": self.Z == 1,
        }

        extra_cycles = 0
        if conditions.get(instruction, False):
            # Branch will be taken
            old_pc = self.PC
            self.PC = address

            # Add extra cycle for branch taken
            extra_cycles += 1

            # Add extra cycle if page boundary crossed
            if self._page_crossed(old_pc, address):
                extra_cycles += 1

        return extra_cycles

    def _page_crossed(self, addr1, addr2):
        """Check if two addresses are on different pages"""
        return (addr1 & 0xFF00) != (addr2 & 0xFF00)

    def _get_address_with_page_crossing_info(
        self, addressing_mode, operand_length, instruction
    ):
        """Get operand address and return page crossing penalty separately"""
        page_crossing_penalty = 0

        if addressing_mode == "implied" or addressing_mode == "accumulator":
            # Dummy read for implied instructions
            self.memory.read(self.PC)
            return None, 0
        elif addressing_mode == "immediate":
            addr = self.PC
            self.PC = (self.PC + 1) & 0xFFFF
            return addr, 0
        elif addressing_mode == "zero_page":
            addr = self.memory.read(self.PC)
            self.PC = (self.PC + 1) & 0xFFFF
            return addr, 0
        elif addressing_mode == "zero_page_x":
            addr = (self.memory.read(self.PC) + self.X) & 0xFF
            self.PC = (self.PC + 1) & 0xFFFF
            return addr, 0
        elif addressing_mode == "zero_page_y":
            addr = (self.memory.read(self.PC) + self.Y) & 0xFF
            self.PC = (self.PC + 1) & 0xFFFF
            return addr, 0
        elif addressing_mode == "absolute":
            low = self.memory.read(self.PC)
            high = self.memory.read(self.PC + 1)
            self.PC = (self.PC + 2) & 0xFFFF
            return (high << 8) | low, 0
        elif addressing_mode == "absolute_x":
            low = self.memory.read(self.PC)
            high = self.memory.read(self.PC + 1)
            self.PC = (self.PC + 2) & 0xFFFF
            base_addr = (high << 8) | low
            final_addr = (base_addr + self.X) & 0xFFFF

            # Check if page boundary crossed for read instructions
            # Including unofficial NOPs that have page crossing penalties: $1C $3C $5C $7C $DC $FC
            if instruction in [
                "LDA",
                "LDX",
                "LDY",
                "EOR",
                "AND",
                "ORA",
                "ADC",
                "SBC",
                "CMP",
                "NOP",  # Some unofficial NOPs have page crossing penalties
            ]:
                if self._page_crossed(base_addr, final_addr):
                    # Perform dummy read at wrong address
                    self.memory.read(
                        (base_addr & 0xFF00) | ((base_addr + self.X) & 0xFF)
                    )
                    page_crossing_penalty = 1
            elif instruction in [
                "STA",
                "STX",
                "STY",
                "ASL",
                "LSR",
                "ROL",
                "ROR",
                "INC",
                "DEC",
            ]:
                # Write instructions always do dummy read
                self.memory.read((base_addr & 0xFF00) | ((base_addr + self.X) & 0xFF))

            return final_addr, page_crossing_penalty
        elif addressing_mode == "absolute_y":
            low = self.memory.read(self.PC)
            high = self.memory.read(self.PC + 1)
            self.PC = (self.PC + 2) & 0xFFFF
            base_addr = (high << 8) | low
            final_addr = (base_addr + self.Y) & 0xFFFF

            # Check if page boundary crossed for read instructions
            # Including unofficial instructions that have page crossing penalties: $BB $BF
            if instruction in [
                "LDA",
                "LDX",
                "LDY",
                "EOR",
                "AND",
                "ORA",
                "ADC",
                "SBC",
                "CMP",
                "LAX",  # Unofficial instruction $BB $BF
            ]:
                if self._page_crossed(base_addr, final_addr):
                    # Perform dummy read at wrong address
                    self.memory.read(
                        (base_addr & 0xFF00) | ((base_addr + self.Y) & 0xFF)
                    )
                    page_crossing_penalty = 1
            elif instruction in ["STA", "STX", "STY"]:
                # Write instructions always do dummy read
                self.memory.read((base_addr & 0xFF00) | ((base_addr + self.Y) & 0xFF))

            return final_addr, page_crossing_penalty
        elif addressing_mode == "relative":
            offset = self.memory.read(self.PC)
            self.PC = (self.PC + 1) & 0xFFFF
            if offset & 0x80:  # Negative
                offset = offset - 256
            return (self.PC + offset) & 0xFFFF, 0
        elif addressing_mode == "indirect":
            low = self.memory.read(self.PC)
            high = self.memory.read(self.PC + 1)
            self.PC = (self.PC + 2) & 0xFFFF
            addr = (high << 8) | low
            # 6502 bug: if low byte is 0xFF, high byte wraps around within same page
            if low == 0xFF:
                target_low = self.memory.read(addr)
                target_high = self.memory.read(addr & 0xFF00)
            else:
                target_low = self.memory.read(addr)
                target_high = self.memory.read(addr + 1)
            return (target_high << 8) | target_low, 0
        elif addressing_mode == "indexed_indirect":
            base = self.memory.read(self.PC)
            self.PC = (self.PC + 1) & 0xFFFF
            addr = (base + self.X) & 0xFF
            low = self.memory.read(addr)
            high = self.memory.read((addr + 1) & 0xFF)
            return (high << 8) | low, 0
        elif addressing_mode == "indirect_indexed":
            base = self.memory.read(self.PC)
            self.PC = (self.PC + 1) & 0xFFFF
            low = self.memory.read(base)
            high = self.memory.read((base + 1) & 0xFF)
            base_addr = (high << 8) | low
            final_addr = (base_addr + self.Y) & 0xFFFF

            # Check if page boundary crossed for read instructions
            # Including unofficial instruction $B3 (LAX)
            if instruction in [
                "LDA",
                "LDX",
                "LDY",
                "EOR",
                "AND",
                "ORA",
                "ADC",
                "SBC",
                "CMP",
                "LAX",  # Unofficial instruction $B3
            ]:
                if self._page_crossed(base_addr, final_addr):
                    # Perform dummy read at wrong address
                    self.memory.read(
                        (base_addr & 0xFF00) | ((base_addr + self.Y) & 0xFF)
                    )
                    page_crossing_penalty = 1
            elif instruction in ["STA", "STX", "STY"]:
                # Write instructions always do dummy read
                self.memory.read((base_addr & 0xFF00) | ((base_addr + self.Y) & 0xFF))

            return final_addr, page_crossing_penalty

        return None, 0

    def _get_address_with_cycles(self, addressing_mode, operand_length, instruction):
        """Legacy method - get operand address with cycle-accurate page boundary handling"""
        address, page_crossing_penalty = self._get_address_with_page_crossing_info(
            addressing_mode, operand_length, instruction
        )
        # Add the penalty to cycles for compatibility with old execution model
        self.cycles += page_crossing_penalty
        return address

    def trigger_interrupt(self, interrupt_type):
        """Trigger an interrupt (NMI, IRQ, RST)"""
        debug_print(
            f"CPU: Interrupt triggered: {interrupt_type}, PC=0x{self.PC:04X}, prev_interrupt={self.interrupt_pending}"
        )

        # NMI takes precedence over IRQ
        if interrupt_type == "NMI":
            # NMI always takes precedence regardless of previous interrupt
            self.interrupt_pending = "NMI"
            # Ensure it will be handled at the next instruction boundary
            self.interrupt_state = 0
            # Do not modify the I flag here; precedence is handled when servicing
        elif interrupt_type == "IRQ" and self.interrupt_pending != "NMI":
            # Latch IRQ. It will only be serviced when interrupts are enabled (after CLI/PLP latency)
            self.interrupt_pending = "IRQ"
            if self.interrupt_inhibit == 1:
                debug_print(f"CPU: IRQ pending but masked (I={self.I})")

    def add_dma_cycles(self, cycles):
        """Add DMA cycles that will delay CPU execution"""
        self.dma_cycles += cycles
        # DMA takes extra cycle on odd CPU cycles
        if self.odd_cycle:
            self.dma_cycles += 1

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

    def get_operand(self, addressing_mode, operand_length):
        """Legacy operand getter for compatibility"""
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

    # Instruction implementations - Updated for hardware accuracy
    def execute_lda(self, operand, addressing_mode):
        # Optimized: avoid duplicate reads for immediate mode
        value = self.memory.read(operand)
        self.A = value
        self.set_zero_negative(self.A)

        # Debug: Log LDA reads from specific addresses that might be causing loops
        if operand == 0x2002 or operand == 0x2000 or operand == 0x2001:
            debug_print(
                f"CPU: LDA from PPU register 0x{operand:04X} = 0x{value:02X}, A=0x{self.A:02X}"
            )
        elif self.total_cycles % 1000 == 0:
            debug_print(
                f"CPU: LDA from 0x{operand:04X} = 0x{value:02X}, A=0x{self.A:02X}"
            )

    def execute_ldx(self, operand, addressing_mode):
        value = self.memory.read(operand)
        self.X = value
        self.set_zero_negative(self.X)

    def execute_ldy(self, operand, addressing_mode):
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
        # Hardware-accurate: B and bit 5 are always set when pushed by PHP
        self.push_stack(self.get_status_byte() | 0x30)

    def execute_plp(self, operand, addressing_mode):
        """Pull Processor flags with I flag delay"""
        # Hardware-accurate: ignore bits 4 and 5 from stack
        status = self.pop_stack()
        old_i = self.I

        # Extract the new I flag value from the pulled status
        new_i = (status >> 2) & 1

        # Apply all flags immediately, including I visibility, but preserve bits 4 and 5
        temp_status = self.get_status_byte()
        temp_status = (status & ~0x30) | (temp_status & 0x30)
        self.set_status_byte(temp_status)

        # If I changed, recognition is delayed one instruction
        if new_i != old_i:
            self.I = new_i  # Visible immediately
            # One-instruction latency, applied at next boundary
            self.interrupt_delay_counter = 1
            self.interrupt_delay_pending = True
            self.interrupt_delay_value = self.I
            debug_print(
                f"CPU: PLP changed I -> {self.I}, scheduling IRQ mask update after 1 instruction"
            )
        else:
            self.I = new_i
            self.interrupt_delay_value = self.I

    def execute_adc(self, operand, addressing_mode):
        # Optimized: single read operation
        value = self.memory.read(operand)
        result = self.A + value + self.C

        # Set overflow flag
        self.V = 1 if ((self.A ^ result) & (value ^ result) & 0x80) else 0

        # Set carry flag
        self.C = 1 if result > 255 else 0

        self.A = result & 0xFF
        self.set_zero_negative(self.A)

    def execute_sbc(self, operand, addressing_mode):
        # Optimized: single read operation
        value = self.memory.read(operand)
        result = self.A - value - (1 - self.C)

        # Set overflow flag
        self.V = 1 if ((self.A ^ result) & (~value ^ result) & 0x80) else 0

        # Set carry flag (inverted for subtraction)
        self.C = 0 if result < 0 else 1

        self.A = result & 0xFF
        self.set_zero_negative(self.A)

    def execute_and(self, operand, addressing_mode):
        # Optimized: single read operation
        value = self.memory.read(operand)
        self.A = self.A & value
        self.set_zero_negative(self.A)

    def execute_eor(self, operand, addressing_mode):
        # Optimized: single read operation
        value = self.memory.read(operand)
        self.A = self.A ^ value
        self.set_zero_negative(self.A)

    def execute_ora(self, operand, addressing_mode):
        # Optimized: single read operation
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
            # Hardware-accurate: dummy write the original value
            self.memory.write(operand, value)
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
            # Hardware-accurate: dummy write the original value
            self.memory.write(operand, value)
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
            # Hardware-accurate: dummy write the original value
            self.memory.write(operand, value)
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
            # Hardware-accurate: dummy write the original value
            self.memory.write(operand, value)
            old_carry = self.C
            self.C = value & 1
            value = (value >> 1) | (old_carry << 7)
            self.memory.write(operand, value)
            self.set_zero_negative(value)

    def execute_cmp(self, operand, addressing_mode):
        # Optimized: single read operation
        value = self.memory.read(operand)
        result = self.A - value
        self.C = 1 if self.A >= value else 0
        self.set_zero_negative(result & 0xFF)

    def execute_cpx(self, operand, addressing_mode):
        # Optimized: single read operation
        value = self.memory.read(operand)
        result = self.X - value
        self.C = 1 if self.X >= value else 0
        self.set_zero_negative(result & 0xFF)

    def execute_cpy(self, operand, addressing_mode):
        # Optimized: single read operation
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
        value = self.memory.read(operand)
        # Hardware-accurate: dummy write the original value
        self.memory.write(operand, value)
        value = (value + 1) & 0xFF
        self.memory.write(operand, value)
        self.set_zero_negative(value)

    def execute_inx(self, operand, addressing_mode):
        self.X = (self.X + 1) & 0xFF
        self.set_zero_negative(self.X)

    def execute_iny(self, operand, addressing_mode):
        self.Y = (self.Y + 1) & 0xFF
        self.set_zero_negative(self.Y)

    def execute_dec(self, operand, addressing_mode):
        value = self.memory.read(operand)
        # Hardware-accurate: dummy write the original value
        self.memory.write(operand, value)
        value = (value - 1) & 0xFF
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
        # BNE branches if Z flag is 0 (not equal)
        if self.Z == 0:
            self.PC = operand

    def execute_beq(self, operand, addressing_mode):
        # BEQ branches if Z flag is 1 (equal)
        if self.Z == 1:
            self.PC = operand

    def execute_jmp(self, operand, addressing_mode):
        # Debug JMP loops
        if operand == 0x8057:
            debug_print(f"CPU: JMP infinite loop detected at PC=0x{operand:04X}")
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
        # BRK is a 2-byte instruction; increment PC to skip the padding byte
        self.PC = (self.PC + 1) & 0xFFFF
        
        # Push PC and status to stack
        self.push_stack((self.PC >> 8) & 0xFF)
        self.push_stack(self.PC & 0xFF)
        
        # If an NMI is pending at this exact moment, NMI takes precedence over BRK.
        # This matches hardware behavior verified by cpu_interrupts_v2 2-nmi_and_brk.
        if self.interrupt_pending == "NMI":
            # Special 6502 quirk: If NMI and BRK coincide, vector to NMI but push BRK signature (B flag set)
            # This matches cpu_interrupts_v2 expectations.
            self.push_stack(self.get_status_byte() | 0x30)
            
            # Set interrupt disable immediately
            self.I = 1
            self.interrupt_inhibit = 1
            
            # Vector to NMI
            low = self.memory.read(0xFFFA)
            high = self.memory.read(0xFFFB)
            self.PC = (high << 8) | low
            
            # Clear the pending NMI now that it's been serviced
            self.interrupt_pending = None
        else:
            # Software interrupt path (BRK behaves like IRQ using the IRQ/BRK vector)
            # Hardware-accurate: B and bit 5 are set when pushed by BRK
            self.push_stack(self.get_status_byte() | 0x30)
            
            # BRK sets I flag immediately (no delay like CLI/SEI)
            self.I = 1
            self.interrupt_inhibit = 1
            
            # Jump to IRQ/BRK vector
            low = self.memory.read(0xFFFE)
            high = self.memory.read(0xFFFF)
            self.PC = (high << 8) | low

    def execute_rti(self, operand, addressing_mode):
        """Return from Interrupt - I flag takes effect immediately"""
        # Hardware-accurate: Pop status first (last pushed by interrupt)
        status = self.pop_stack()
        self.set_status_byte((status & ~0x30) | (self.get_status_byte() & 0x30))

        # RTI affects interrupt inhibition immediately (no delay)
        self.interrupt_inhibit = self.I

        # Pop return address: low byte first (pushed second), then high byte (pushed first)
        low = self.pop_stack()
        high = self.pop_stack()
        self.PC = (high << 8) | low

    def execute_clc(self, operand, addressing_mode):
        self.C = 0

    def execute_sec(self, operand, addressing_mode):
        self.C = 1

    def execute_cli(self, operand, addressing_mode):
        """Clear Interrupt flag with one-instruction latency on recognition.
        Status bit I is updated immediately; interrupt_inhibit updates after next instruction.
        """
        # Update visible I flag immediately
        self.I = 0
        # Defer the effective recognition change by one instruction
        # Apply at the next instruction boundary
        self.interrupt_delay_counter = 1
        self.interrupt_delay_pending = True
        self.interrupt_delay_value = self.I
        debug_print(
            f"CPU: CLI executed, I={self.I}, will enable IRQs after 1 instruction"
        )

    def execute_sei(self, operand, addressing_mode):
        """Set Interrupt flag with one-instruction latency on recognition.
        Status bit I is updated immediately; interrupt_inhibit updates after next instruction.
        """
        # Update visible I flag immediately
        self.I = 1
        # Defer the effective recognition change by one instruction
        # Apply at the next instruction boundary
        self.interrupt_delay_counter = 1
        self.interrupt_delay_pending = True
        self.interrupt_delay_value = self.I
        debug_print(
            f"CPU: SEI executed, I={self.I}, will mask IRQs after 1 instruction"
        )

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
            value = self.memory.read(operand)
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
        value = self.memory.read(operand)
        # Hardware-accurate: dummy write the original value
        self.memory.write(operand, value)
        value = (value - 1) & 0xFF
        self.memory.write(operand, value)

        # Compare with A
        result = self.A - value
        self.C = 1 if self.A >= value else 0
        self.set_zero_negative(result & 0xFF)

    def execute_isc(self, operand, addressing_mode):
        """Increment and Subtract with Carry - Increment memory then SBC"""
        value = self.memory.read(operand)
        # Hardware-accurate: dummy write the original value
        self.memory.write(operand, value)
        value = (value + 1) & 0xFF
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
        # Hardware-accurate: dummy write the original value
        self.memory.write(operand, value)

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
        # Hardware-accurate: dummy write the original value
        self.memory.write(operand, value)

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
        # Hardware-accurate: dummy write the original value
        self.memory.write(operand, value)

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
        # Hardware-accurate: dummy write the original value
        self.memory.write(operand, value)

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

    def execute_las(self, operand, addressing_mode):
        """LAS - Load Accumulator and Stack Pointer"""
        value = self.memory.read(operand)
        result = value & self.S
        self.A = result
        self.X = result
        self.S = result
        self.set_zero_negative(result)

    def execute_tas(self, operand, addressing_mode):
        """TAS - Transfer A and X to Stack Pointer, then store A & X & (high byte + 1)"""
        self.S = self.A & self.X
        # Store A & X & (high byte of address + 1)
        high_byte = (operand >> 8) & 0xFF
        value = self.A & self.X & (high_byte + 1)
        self.memory.write(operand, value)

    def execute_kil(self, operand, addressing_mode):
        """KIL - Kill/Jam the processor (halt)"""
        # In a real 6502, this would halt the processor
        # For emulation purposes, we'll just infinite loop by decrementing PC
        self.PC = (self.PC - 1) & 0xFFFF
        print(f"KIL instruction executed at PC: 0x{self.PC:04X} - processor halted")

    def execute_shx(self, operand, addressing_mode):
        """SHX - Store X AND (high byte + 1)"""
        high_byte = (operand >> 8) & 0xFF
        value = self.X & (high_byte + 1)
        # Calculate the actual address with the AND operation
        actual_addr = ((value << 8) | (operand & 0xFF)) & 0xFFFF
        self.memory.write(actual_addr, value)

    def execute_sha(self, operand, addressing_mode):
        """SHA - Store A AND X AND (high byte + 1)"""
        high_byte = (operand >> 8) & 0xFF
        value = self.A & self.X & (high_byte + 1)
        # Calculate the actual address with the AND operation
        if addressing_mode == "absolute_y":
            actual_addr = ((value << 8) | (operand & 0xFF)) & 0xFFFF
        else:
            actual_addr = operand
        self.memory.write(actual_addr, value)

    def execute_alr(self, operand, addressing_mode):
        """ALR - AND then LSR"""
        value = self.memory.read(operand)
        # AND with accumulator
        self.A = self.A & value
        # LSR on accumulator
        self.C = self.A & 1
        self.A = self.A >> 1
        self.set_zero_negative(self.A)
