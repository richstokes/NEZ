# cython: boundscheck=False, wraparound=False, cdivision=True, language_level=3
"""
NES 6502 CPU Emulator — Cython accelerated.
"""
from memory cimport Memory

# ── Cycle lookup table (256 entries) ──
cdef int CYCLE_TABLE[256]
CYCLE_TABLE[:] = [
    7,6,2,8,3,3,5,5,3,2,2,2,4,4,6,6,
    2,5,2,8,4,4,6,6,2,4,2,7,4,4,7,7,
    6,6,2,8,3,3,5,5,4,2,2,2,4,4,6,6,
    2,5,2,8,4,4,6,6,2,4,2,7,4,4,7,7,
    6,6,2,8,3,3,5,5,3,2,2,2,3,4,6,6,
    2,5,2,8,4,4,6,6,2,4,2,7,4,4,7,7,
    6,6,2,8,3,3,5,5,4,2,2,2,5,4,6,6,
    2,5,2,8,4,4,6,6,2,4,2,7,4,4,7,7,
    2,6,2,6,3,3,3,3,2,2,2,2,4,4,4,4,
    2,6,2,6,4,4,4,4,2,5,2,5,5,5,5,5,
    2,6,2,6,3,3,3,3,2,2,2,2,4,4,4,4,
    2,5,2,5,4,4,4,4,2,4,2,4,4,4,4,4,
    2,6,2,8,3,3,5,5,2,2,2,2,4,4,6,6,
    2,5,2,8,4,4,6,6,2,4,2,7,4,4,7,7,
    2,6,2,8,3,3,5,5,2,2,2,2,4,4,6,6,
    2,5,2,8,4,4,6,6,2,4,2,7,4,4,7,7,
]

# ── KIL opcode set ──
cdef set KIL_SET = {0x02,0x12,0x22,0x32,0x42,0x52,0x62,0x72,0x92,0xB2,0xD2,0xF2}

# ── Addressing mode constants (encoded as ints for fast dispatch) ──
DEF AM_IMPLIED        = 0
DEF AM_ACCUMULATOR    = 1
DEF AM_IMMEDIATE      = 2
DEF AM_ZERO_PAGE      = 3
DEF AM_ZERO_PAGE_X    = 4
DEF AM_ZERO_PAGE_Y    = 5
DEF AM_ABSOLUTE       = 6
DEF AM_ABSOLUTE_X     = 7
DEF AM_ABSOLUTE_Y     = 8
DEF AM_RELATIVE       = 9
DEF AM_INDIRECT       = 10
DEF AM_INDEXED_INDIRECT = 11
DEF AM_INDIRECT_INDEXED = 12

# ── Instruction ID constants ──
DEF I_LDA=0
DEF I_LDX=1
DEF I_LDY=2
DEF I_STA=3
DEF I_STX=4
DEF I_STY=5
DEF I_TAX=6
DEF I_TAY=7
DEF I_TSX=8
DEF I_TXA=9
DEF I_TXS=10
DEF I_TYA=11
DEF I_PHA=12
DEF I_PLA=13
DEF I_PHP=14
DEF I_PLP=15
DEF I_ADC=16
DEF I_SBC=17
DEF I_AND=18
DEF I_EOR=19
DEF I_ORA=20
DEF I_ASL=21
DEF I_LSR=22
DEF I_ROL=23
DEF I_ROR=24
DEF I_CMP=25
DEF I_CPX=26
DEF I_CPY=27
DEF I_BIT=28
DEF I_INC=29
DEF I_INX=30
DEF I_INY=31
DEF I_DEC=32
DEF I_DEX=33
DEF I_DEY=34
DEF I_BPL=35
DEF I_BMI=36
DEF I_BVC=37
DEF I_BVS=38
DEF I_BCC=39
DEF I_BCS=40
DEF I_BNE=41
DEF I_BEQ=42
DEF I_JMP=43
DEF I_JSR=44
DEF I_RTS=45
DEF I_BRK=46
DEF I_RTI=47
DEF I_CLC=48
DEF I_SEC=49
DEF I_CLI=50
DEF I_SEI=51
DEF I_CLV=52
DEF I_CLD=53
DEF I_SED=54
DEF I_NOP=55
DEF I_LAX=56
DEF I_SAX=57
DEF I_DCP=58
DEF I_ISC=59
DEF I_SLO=60
DEF I_RLA=61
DEF I_SRE=62
DEF I_RRA=63
DEF I_LAS=64
DEF I_TAS=65
DEF I_KIL=66
DEF I_SHX=67
DEF I_SHA=68
DEF I_ALR=69
DEF I_ANC=70
DEF I_ARR=71
DEF I_AXS=72
DEF I_SHY=73
DEF I_XAA=74

# ── Opcode table: (instruction_id, addressing_mode, length) for all 256 opcodes ──
# Stored as flat C arrays for zero-overhead lookup.
cdef int OP_INSTR[256]
cdef int OP_AMODE[256]
cdef int OP_LEN[256]

# Helper to define opcodes
cdef void _set_op(int op, int instr, int am, int length):
    OP_INSTR[op] = instr
    OP_AMODE[op] = am
    OP_LEN[op] = length

def _init_opcode_tables():
    """Initialize the opcode lookup tables."""
    cdef int i
    # Default all to NOP implied
    for i in range(256):
        OP_INSTR[i] = I_NOP
        OP_AMODE[i] = AM_IMPLIED
        OP_LEN[i] = 1

    # Load/Store
    _set_op(0xA9, I_LDA, AM_IMMEDIATE, 2); _set_op(0xA5, I_LDA, AM_ZERO_PAGE, 2)
    _set_op(0xB5, I_LDA, AM_ZERO_PAGE_X, 2); _set_op(0xAD, I_LDA, AM_ABSOLUTE, 3)
    _set_op(0xBD, I_LDA, AM_ABSOLUTE_X, 3); _set_op(0xB9, I_LDA, AM_ABSOLUTE_Y, 3)
    _set_op(0xA1, I_LDA, AM_INDEXED_INDIRECT, 2); _set_op(0xB1, I_LDA, AM_INDIRECT_INDEXED, 2)

    _set_op(0xA2, I_LDX, AM_IMMEDIATE, 2); _set_op(0xA6, I_LDX, AM_ZERO_PAGE, 2)
    _set_op(0xB6, I_LDX, AM_ZERO_PAGE_Y, 2); _set_op(0xAE, I_LDX, AM_ABSOLUTE, 3)
    _set_op(0xBE, I_LDX, AM_ABSOLUTE_Y, 3)

    _set_op(0xA0, I_LDY, AM_IMMEDIATE, 2); _set_op(0xA4, I_LDY, AM_ZERO_PAGE, 2)
    _set_op(0xB4, I_LDY, AM_ZERO_PAGE_X, 2); _set_op(0xAC, I_LDY, AM_ABSOLUTE, 3)
    _set_op(0xBC, I_LDY, AM_ABSOLUTE_X, 3)

    _set_op(0x85, I_STA, AM_ZERO_PAGE, 2); _set_op(0x95, I_STA, AM_ZERO_PAGE_X, 2)
    _set_op(0x8D, I_STA, AM_ABSOLUTE, 3); _set_op(0x9D, I_STA, AM_ABSOLUTE_X, 3)
    _set_op(0x99, I_STA, AM_ABSOLUTE_Y, 3); _set_op(0x81, I_STA, AM_INDEXED_INDIRECT, 2)
    _set_op(0x91, I_STA, AM_INDIRECT_INDEXED, 2)

    _set_op(0x86, I_STX, AM_ZERO_PAGE, 2); _set_op(0x96, I_STX, AM_ZERO_PAGE_Y, 2)
    _set_op(0x8E, I_STX, AM_ABSOLUTE, 3)

    _set_op(0x84, I_STY, AM_ZERO_PAGE, 2); _set_op(0x94, I_STY, AM_ZERO_PAGE_X, 2)
    _set_op(0x8C, I_STY, AM_ABSOLUTE, 3)

    # Transfer
    _set_op(0xAA, I_TAX, AM_IMPLIED, 1); _set_op(0xA8, I_TAY, AM_IMPLIED, 1)
    _set_op(0xBA, I_TSX, AM_IMPLIED, 1); _set_op(0x8A, I_TXA, AM_IMPLIED, 1)
    _set_op(0x9A, I_TXS, AM_IMPLIED, 1); _set_op(0x98, I_TYA, AM_IMPLIED, 1)

    # Stack
    _set_op(0x48, I_PHA, AM_IMPLIED, 1); _set_op(0x68, I_PLA, AM_IMPLIED, 1)
    _set_op(0x08, I_PHP, AM_IMPLIED, 1); _set_op(0x28, I_PLP, AM_IMPLIED, 1)

    # Arithmetic
    _set_op(0x69, I_ADC, AM_IMMEDIATE, 2); _set_op(0x65, I_ADC, AM_ZERO_PAGE, 2)
    _set_op(0x75, I_ADC, AM_ZERO_PAGE_X, 2); _set_op(0x6D, I_ADC, AM_ABSOLUTE, 3)
    _set_op(0x7D, I_ADC, AM_ABSOLUTE_X, 3); _set_op(0x79, I_ADC, AM_ABSOLUTE_Y, 3)
    _set_op(0x61, I_ADC, AM_INDEXED_INDIRECT, 2); _set_op(0x71, I_ADC, AM_INDIRECT_INDEXED, 2)

    _set_op(0xE9, I_SBC, AM_IMMEDIATE, 2); _set_op(0xE5, I_SBC, AM_ZERO_PAGE, 2)
    _set_op(0xF5, I_SBC, AM_ZERO_PAGE_X, 2); _set_op(0xED, I_SBC, AM_ABSOLUTE, 3)
    _set_op(0xFD, I_SBC, AM_ABSOLUTE_X, 3); _set_op(0xF9, I_SBC, AM_ABSOLUTE_Y, 3)
    _set_op(0xE1, I_SBC, AM_INDEXED_INDIRECT, 2); _set_op(0xF1, I_SBC, AM_INDIRECT_INDEXED, 2)
    _set_op(0xEB, I_SBC, AM_IMMEDIATE, 2)  # unofficial

    # Logic
    _set_op(0x29, I_AND, AM_IMMEDIATE, 2); _set_op(0x25, I_AND, AM_ZERO_PAGE, 2)
    _set_op(0x35, I_AND, AM_ZERO_PAGE_X, 2); _set_op(0x2D, I_AND, AM_ABSOLUTE, 3)
    _set_op(0x3D, I_AND, AM_ABSOLUTE_X, 3); _set_op(0x39, I_AND, AM_ABSOLUTE_Y, 3)
    _set_op(0x21, I_AND, AM_INDEXED_INDIRECT, 2); _set_op(0x31, I_AND, AM_INDIRECT_INDEXED, 2)

    _set_op(0x49, I_EOR, AM_IMMEDIATE, 2); _set_op(0x45, I_EOR, AM_ZERO_PAGE, 2)
    _set_op(0x55, I_EOR, AM_ZERO_PAGE_X, 2); _set_op(0x4D, I_EOR, AM_ABSOLUTE, 3)
    _set_op(0x5D, I_EOR, AM_ABSOLUTE_X, 3); _set_op(0x59, I_EOR, AM_ABSOLUTE_Y, 3)
    _set_op(0x41, I_EOR, AM_INDEXED_INDIRECT, 2); _set_op(0x51, I_EOR, AM_INDIRECT_INDEXED, 2)

    _set_op(0x09, I_ORA, AM_IMMEDIATE, 2); _set_op(0x05, I_ORA, AM_ZERO_PAGE, 2)
    _set_op(0x15, I_ORA, AM_ZERO_PAGE_X, 2); _set_op(0x0D, I_ORA, AM_ABSOLUTE, 3)
    _set_op(0x1D, I_ORA, AM_ABSOLUTE_X, 3); _set_op(0x19, I_ORA, AM_ABSOLUTE_Y, 3)
    _set_op(0x01, I_ORA, AM_INDEXED_INDIRECT, 2); _set_op(0x11, I_ORA, AM_INDIRECT_INDEXED, 2)

    # Shift/Rotate
    _set_op(0x0A, I_ASL, AM_ACCUMULATOR, 1); _set_op(0x06, I_ASL, AM_ZERO_PAGE, 2)
    _set_op(0x16, I_ASL, AM_ZERO_PAGE_X, 2); _set_op(0x0E, I_ASL, AM_ABSOLUTE, 3)
    _set_op(0x1E, I_ASL, AM_ABSOLUTE_X, 3)

    _set_op(0x4A, I_LSR, AM_ACCUMULATOR, 1); _set_op(0x46, I_LSR, AM_ZERO_PAGE, 2)
    _set_op(0x56, I_LSR, AM_ZERO_PAGE_X, 2); _set_op(0x4E, I_LSR, AM_ABSOLUTE, 3)
    _set_op(0x5E, I_LSR, AM_ABSOLUTE_X, 3)

    _set_op(0x2A, I_ROL, AM_ACCUMULATOR, 1); _set_op(0x26, I_ROL, AM_ZERO_PAGE, 2)
    _set_op(0x36, I_ROL, AM_ZERO_PAGE_X, 2); _set_op(0x2E, I_ROL, AM_ABSOLUTE, 3)
    _set_op(0x3E, I_ROL, AM_ABSOLUTE_X, 3)

    _set_op(0x6A, I_ROR, AM_ACCUMULATOR, 1); _set_op(0x66, I_ROR, AM_ZERO_PAGE, 2)
    _set_op(0x76, I_ROR, AM_ZERO_PAGE_X, 2); _set_op(0x6E, I_ROR, AM_ABSOLUTE, 3)
    _set_op(0x7E, I_ROR, AM_ABSOLUTE_X, 3)

    # Compare
    _set_op(0xC9, I_CMP, AM_IMMEDIATE, 2); _set_op(0xC5, I_CMP, AM_ZERO_PAGE, 2)
    _set_op(0xD5, I_CMP, AM_ZERO_PAGE_X, 2); _set_op(0xCD, I_CMP, AM_ABSOLUTE, 3)
    _set_op(0xDD, I_CMP, AM_ABSOLUTE_X, 3); _set_op(0xD9, I_CMP, AM_ABSOLUTE_Y, 3)
    _set_op(0xC1, I_CMP, AM_INDEXED_INDIRECT, 2); _set_op(0xD1, I_CMP, AM_INDIRECT_INDEXED, 2)

    _set_op(0xE0, I_CPX, AM_IMMEDIATE, 2); _set_op(0xE4, I_CPX, AM_ZERO_PAGE, 2)
    _set_op(0xEC, I_CPX, AM_ABSOLUTE, 3)

    _set_op(0xC0, I_CPY, AM_IMMEDIATE, 2); _set_op(0xC4, I_CPY, AM_ZERO_PAGE, 2)
    _set_op(0xCC, I_CPY, AM_ABSOLUTE, 3)

    _set_op(0x24, I_BIT, AM_ZERO_PAGE, 2); _set_op(0x2C, I_BIT, AM_ABSOLUTE, 3)

    # Inc/Dec
    _set_op(0xE6, I_INC, AM_ZERO_PAGE, 2); _set_op(0xF6, I_INC, AM_ZERO_PAGE_X, 2)
    _set_op(0xEE, I_INC, AM_ABSOLUTE, 3); _set_op(0xFE, I_INC, AM_ABSOLUTE_X, 3)
    _set_op(0xE8, I_INX, AM_IMPLIED, 1); _set_op(0xC8, I_INY, AM_IMPLIED, 1)
    _set_op(0xC6, I_DEC, AM_ZERO_PAGE, 2); _set_op(0xD6, I_DEC, AM_ZERO_PAGE_X, 2)
    _set_op(0xCE, I_DEC, AM_ABSOLUTE, 3); _set_op(0xDE, I_DEC, AM_ABSOLUTE_X, 3)
    _set_op(0xCA, I_DEX, AM_IMPLIED, 1); _set_op(0x88, I_DEY, AM_IMPLIED, 1)

    # Branches
    _set_op(0x10, I_BPL, AM_RELATIVE, 2); _set_op(0x30, I_BMI, AM_RELATIVE, 2)
    _set_op(0x50, I_BVC, AM_RELATIVE, 2); _set_op(0x70, I_BVS, AM_RELATIVE, 2)
    _set_op(0x90, I_BCC, AM_RELATIVE, 2); _set_op(0xB0, I_BCS, AM_RELATIVE, 2)
    _set_op(0xD0, I_BNE, AM_RELATIVE, 2); _set_op(0xF0, I_BEQ, AM_RELATIVE, 2)

    # Jumps
    _set_op(0x4C, I_JMP, AM_ABSOLUTE, 3); _set_op(0x6C, I_JMP, AM_INDIRECT, 3)
    _set_op(0x20, I_JSR, AM_ABSOLUTE, 3); _set_op(0x60, I_RTS, AM_IMPLIED, 1)

    # Interrupts
    _set_op(0x00, I_BRK, AM_IMPLIED, 1); _set_op(0x40, I_RTI, AM_IMPLIED, 1)

    # Flags
    _set_op(0x18, I_CLC, AM_IMPLIED, 1); _set_op(0x38, I_SEC, AM_IMPLIED, 1)
    _set_op(0x58, I_CLI, AM_IMPLIED, 1); _set_op(0x78, I_SEI, AM_IMPLIED, 1)
    _set_op(0xB8, I_CLV, AM_IMPLIED, 1); _set_op(0xD8, I_CLD, AM_IMPLIED, 1)
    _set_op(0xF8, I_SED, AM_IMPLIED, 1)

    # NOP
    _set_op(0xEA, I_NOP, AM_IMPLIED, 1)
    # Unofficial NOPs
    for op in [0x1A,0x3A,0x5A,0x7A,0xDA,0xFA]:
        _set_op(op, I_NOP, AM_IMPLIED, 1)
    for op in [0x80,0x82,0x89,0xC2,0xE2]:
        _set_op(op, I_NOP, AM_IMMEDIATE, 2)
    for op in [0x04,0x44,0x64]:
        _set_op(op, I_NOP, AM_ZERO_PAGE, 2)
    for op in [0x14,0x34,0x54,0x74,0xD4,0xF4]:
        _set_op(op, I_NOP, AM_ZERO_PAGE_X, 2)
    _set_op(0x0C, I_NOP, AM_ABSOLUTE, 3)
    for op in [0x1C,0x3C,0x5C,0x7C,0xDC,0xFC]:
        _set_op(op, I_NOP, AM_ABSOLUTE_X, 3)

    # Unofficial opcodes
    _set_op(0xA7, I_LAX, AM_ZERO_PAGE, 2); _set_op(0xB7, I_LAX, AM_ZERO_PAGE_Y, 2)
    _set_op(0xAF, I_LAX, AM_ABSOLUTE, 3); _set_op(0xBF, I_LAX, AM_ABSOLUTE_Y, 3)
    _set_op(0xA3, I_LAX, AM_INDEXED_INDIRECT, 2); _set_op(0xB3, I_LAX, AM_INDIRECT_INDEXED, 2)
    _set_op(0xAB, I_LAX, AM_IMMEDIATE, 2)

    _set_op(0x87, I_SAX, AM_ZERO_PAGE, 2); _set_op(0x97, I_SAX, AM_ZERO_PAGE_Y, 2)
    _set_op(0x8F, I_SAX, AM_ABSOLUTE, 3); _set_op(0x83, I_SAX, AM_INDEXED_INDIRECT, 2)

    _set_op(0xC7, I_DCP, AM_ZERO_PAGE, 2); _set_op(0xD7, I_DCP, AM_ZERO_PAGE_X, 2)
    _set_op(0xCF, I_DCP, AM_ABSOLUTE, 3); _set_op(0xDF, I_DCP, AM_ABSOLUTE_X, 3)
    _set_op(0xDB, I_DCP, AM_ABSOLUTE_Y, 3); _set_op(0xC3, I_DCP, AM_INDEXED_INDIRECT, 2)
    _set_op(0xD3, I_DCP, AM_INDIRECT_INDEXED, 2)

    _set_op(0xE7, I_ISC, AM_ZERO_PAGE, 2); _set_op(0xF7, I_ISC, AM_ZERO_PAGE_X, 2)
    _set_op(0xEF, I_ISC, AM_ABSOLUTE, 3); _set_op(0xFF, I_ISC, AM_ABSOLUTE_X, 3)
    _set_op(0xFB, I_ISC, AM_ABSOLUTE_Y, 3); _set_op(0xE3, I_ISC, AM_INDEXED_INDIRECT, 2)
    _set_op(0xF3, I_ISC, AM_INDIRECT_INDEXED, 2)

    _set_op(0x07, I_SLO, AM_ZERO_PAGE, 2); _set_op(0x17, I_SLO, AM_ZERO_PAGE_X, 2)
    _set_op(0x0F, I_SLO, AM_ABSOLUTE, 3); _set_op(0x1F, I_SLO, AM_ABSOLUTE_X, 3)
    _set_op(0x1B, I_SLO, AM_ABSOLUTE_Y, 3); _set_op(0x03, I_SLO, AM_INDEXED_INDIRECT, 2)
    _set_op(0x13, I_SLO, AM_INDIRECT_INDEXED, 2)

    _set_op(0x27, I_RLA, AM_ZERO_PAGE, 2); _set_op(0x37, I_RLA, AM_ZERO_PAGE_X, 2)
    _set_op(0x2F, I_RLA, AM_ABSOLUTE, 3); _set_op(0x3F, I_RLA, AM_ABSOLUTE_X, 3)
    _set_op(0x3B, I_RLA, AM_ABSOLUTE_Y, 3); _set_op(0x23, I_RLA, AM_INDEXED_INDIRECT, 2)
    _set_op(0x33, I_RLA, AM_INDIRECT_INDEXED, 2)

    _set_op(0x47, I_SRE, AM_ZERO_PAGE, 2); _set_op(0x57, I_SRE, AM_ZERO_PAGE_X, 2)
    _set_op(0x4F, I_SRE, AM_ABSOLUTE, 3); _set_op(0x5F, I_SRE, AM_ABSOLUTE_X, 3)
    _set_op(0x5B, I_SRE, AM_ABSOLUTE_Y, 3); _set_op(0x43, I_SRE, AM_INDEXED_INDIRECT, 2)
    _set_op(0x53, I_SRE, AM_INDIRECT_INDEXED, 2)

    _set_op(0x67, I_RRA, AM_ZERO_PAGE, 2); _set_op(0x77, I_RRA, AM_ZERO_PAGE_X, 2)
    _set_op(0x6F, I_RRA, AM_ABSOLUTE, 3); _set_op(0x7F, I_RRA, AM_ABSOLUTE_X, 3)
    _set_op(0x7B, I_RRA, AM_ABSOLUTE_Y, 3); _set_op(0x63, I_RRA, AM_INDEXED_INDIRECT, 2)
    _set_op(0x73, I_RRA, AM_INDIRECT_INDEXED, 2)

    _set_op(0xBB, I_LAS, AM_ABSOLUTE_Y, 3)
    _set_op(0x9B, I_TAS, AM_ABSOLUTE_Y, 3)
    _set_op(0x9E, I_SHX, AM_ABSOLUTE_Y, 3)
    _set_op(0x9F, I_SHA, AM_ABSOLUTE_Y, 3); _set_op(0x93, I_SHA, AM_INDIRECT_INDEXED, 2)
    _set_op(0x4B, I_ALR, AM_IMMEDIATE, 2)
    _set_op(0x0B, I_ANC, AM_IMMEDIATE, 2); _set_op(0x2B, I_ANC, AM_IMMEDIATE, 2)
    _set_op(0x6B, I_ARR, AM_IMMEDIATE, 2)
    _set_op(0xCB, I_AXS, AM_IMMEDIATE, 2)
    _set_op(0x9C, I_SHY, AM_ABSOLUTE_X, 3)
    _set_op(0x8B, I_XAA, AM_IMMEDIATE, 2)

    # KIL opcodes
    for op in [0x02,0x12,0x22,0x32,0x42,0x52,0x62,0x72,0x92,0xB2,0xD2,0xF2]:
        _set_op(op, I_KIL, AM_IMPLIED, 1)

# Initialize tables at import time
_init_opcode_tables()

# ── Instruction name strings for branch detection ──
# Branch instruction IDs
cdef bint _is_branch(int instr_id):
    return (instr_id >= I_BPL and instr_id <= I_BEQ)

# Read-type instructions for page-crossing penalty in absolute_x/absolute_y/indirect_indexed
cdef bint _is_read_ax(int instr_id):
    return (instr_id == I_LDA or instr_id == I_LDX or instr_id == I_LDY or
            instr_id == I_EOR or instr_id == I_AND or instr_id == I_ORA or
            instr_id == I_ADC or instr_id == I_SBC or instr_id == I_CMP or
            instr_id == I_NOP)

cdef bint _is_read_ay(int instr_id):
    return (instr_id == I_LDA or instr_id == I_LDX or instr_id == I_LDY or
            instr_id == I_EOR or instr_id == I_AND or instr_id == I_ORA or
            instr_id == I_ADC or instr_id == I_SBC or instr_id == I_CMP or
            instr_id == I_LAX)

cdef bint _is_read_iy(int instr_id):
    return (instr_id == I_LDA or instr_id == I_LDX or instr_id == I_LDY or
            instr_id == I_EOR or instr_id == I_AND or instr_id == I_ORA or
            instr_id == I_ADC or instr_id == I_SBC or instr_id == I_CMP or
            instr_id == I_LAX)

cdef bint _is_write_ax(int instr_id):
    return (instr_id == I_STA or instr_id == I_STX or instr_id == I_STY or
            instr_id == I_ASL or instr_id == I_LSR or instr_id == I_ROL or
            instr_id == I_ROR or instr_id == I_INC or instr_id == I_DEC or
            instr_id == I_DCP or instr_id == I_ISC or instr_id == I_SLO or
            instr_id == I_RLA or instr_id == I_SRE or instr_id == I_RRA or
            instr_id == I_SHY or instr_id == I_SHX or instr_id == I_SHA)

cdef bint _is_write_ay(int instr_id):
    return (instr_id == I_STA or instr_id == I_STX or instr_id == I_STY or
            instr_id == I_DCP or instr_id == I_ISC or instr_id == I_SLO or
            instr_id == I_RLA or instr_id == I_SRE or instr_id == I_RRA or
            instr_id == I_TAS or instr_id == I_SHX or instr_id == I_SHA)

cdef bint _is_write_iy(int instr_id):
    return (instr_id == I_STA or instr_id == I_STX or instr_id == I_STY or
            instr_id == I_DCP or instr_id == I_ISC or instr_id == I_SLO or
            instr_id == I_RLA or instr_id == I_SRE or instr_id == I_RRA or
            instr_id == I_SHA)


cdef class CPU:
    # Attribute declarations are in cpu.pxd

    def __init__(self, memory):
        self.memory = memory

        self.A = 0; self.X = 0; self.Y = 0; self.PC = 0; self.S = 0xFD
        self.C = 0; self.Z = 0; self.I = 1; self.D = 0; self.B = 0; self.V = 0; self.N = 0
        self.cycles = 0; self.dma_cycles = 0; self.total_cycles = 0; self.odd_cycle = 0
        self.interrupt_pending = None; self.interrupt_state = 0
        self.interrupt_inhibit = 1; self.pending_interrupt_inhibit = 1
        self.interrupt_latency_remaining = 0; self.interrupt_latency_armed = True
        self.interrupt_unmask_grace = 0
        self.branch_pending = False; self.branch_target = 0
        self.in_nmi = False; self.current_interrupt_type = None
        self.jam_reported_at = None; self.current_instruction_pc = 0

        # Keep kil_opcodes set for Python-level compat
        self.kil_opcodes = KIL_SET

        # Keep cycle_lookup list for Python-level compat
        self.cycle_lookup = list(CYCLE_TABLE)

        # Build Python-visible instructions dict (only used by external code, not hot path)
        self.instructions = {}
        self.instruction_dispatch = {}

    def reset(self):
        self.A = 0; self.X = 0; self.Y = 0; self.S = 0xFD
        self.C = 0; self.Z = 0; self.I = 1; self.D = 0; self.B = 0; self.V = 0; self.N = 0

        cdef int low = self.memory.read(0xFFFC)
        cdef int high = self.memory.read(0xFFFD)
        self.PC = (high << 8) | low

        self.cycles = 0; self.total_cycles = 0; self.odd_cycle = 0
        self.interrupt_pending = None; self.interrupt_state = 0
        self.branch_pending = False

        self.interrupt_inhibit = self.I
        self.pending_interrupt_inhibit = self.interrupt_inhibit
        self.interrupt_latency_remaining = 0
        self.interrupt_latency_armed = True
        self.interrupt_unmask_grace = 0

    # ── Inline helpers ──
    cdef inline void _set_zn(self, int value):
        self.Z = 1 if value == 0 else 0
        self.N = 1 if value & 0x80 else 0

    cdef inline int _get_status(self):
        return ((self.N << 7) | (self.V << 6) | (1 << 5) | (self.B << 4) |
                (self.D << 3) | (self.I << 2) | (self.Z << 1) | self.C)

    cdef inline void _set_status(self, int value):
        self.N = (value >> 7) & 1
        self.V = (value >> 6) & 1
        self.B = (value >> 4) & 1
        self.D = (value >> 3) & 1
        self.I = (value >> 2) & 1
        self.Z = (value >> 1) & 1
        self.C = value & 1

    cdef inline void _push(self, int value):
        self.memory.write(0x0100 + self.S, value)
        self.S = (self.S - 1) & 0xFF

    cdef inline int _pop(self):
        self.S = (self.S + 1) & 0xFF
        return self.memory.read(0x0100 + self.S)

    cdef inline bint _page_crossed(self, int a1, int a2):
        return (a1 & 0xFF00) != (a2 & 0xFF00)

    # ── Address resolution ──
    cdef int _resolve_address(self, int am, int instr_id, int *penalty):
        """Resolve operand address; sets penalty[0] to page crossing penalty."""
        cdef int addr, low, high, base_addr, final_addr, base, offset
        penalty[0] = 0

        if am == AM_IMPLIED or am == AM_ACCUMULATOR:
            self.memory.read(self.PC)
            return -1  # sentinel for no address
        elif am == AM_IMMEDIATE:
            addr = self.PC
            self.PC = (self.PC + 1) & 0xFFFF
            return addr
        elif am == AM_ZERO_PAGE:
            addr = self.memory.read(self.PC)
            self.PC = (self.PC + 1) & 0xFFFF
            return addr
        elif am == AM_ZERO_PAGE_X:
            addr = (self.memory.read(self.PC) + self.X) & 0xFF
            self.PC = (self.PC + 1) & 0xFFFF
            return addr
        elif am == AM_ZERO_PAGE_Y:
            addr = (self.memory.read(self.PC) + self.Y) & 0xFF
            self.PC = (self.PC + 1) & 0xFFFF
            return addr
        elif am == AM_ABSOLUTE:
            low = self.memory.read(self.PC)
            high = self.memory.read(self.PC + 1)
            self.PC = (self.PC + 2) & 0xFFFF
            return (high << 8) | low
        elif am == AM_ABSOLUTE_X:
            low = self.memory.read(self.PC)
            high = self.memory.read(self.PC + 1)
            self.PC = (self.PC + 2) & 0xFFFF
            base_addr = (high << 8) | low
            final_addr = (base_addr + self.X) & 0xFFFF
            if _is_read_ax(instr_id):
                if self._page_crossed(base_addr, final_addr):
                    self.memory.read((base_addr & 0xFF00) | ((base_addr + self.X) & 0xFF))
                    penalty[0] = 1
            elif _is_write_ax(instr_id):
                self.memory.read((base_addr & 0xFF00) | ((base_addr + self.X) & 0xFF))
            return final_addr
        elif am == AM_ABSOLUTE_Y:
            low = self.memory.read(self.PC)
            high = self.memory.read(self.PC + 1)
            self.PC = (self.PC + 2) & 0xFFFF
            base_addr = (high << 8) | low
            final_addr = (base_addr + self.Y) & 0xFFFF
            if _is_read_ay(instr_id):
                if self._page_crossed(base_addr, final_addr):
                    self.memory.read((base_addr & 0xFF00) | ((base_addr + self.Y) & 0xFF))
                    penalty[0] = 1
            elif _is_write_ay(instr_id):
                self.memory.read((base_addr & 0xFF00) | ((base_addr + self.Y) & 0xFF))
            return final_addr
        elif am == AM_RELATIVE:
            offset = self.memory.read(self.PC)
            self.PC = (self.PC + 1) & 0xFFFF
            if offset & 0x80:
                offset = offset - 256
            return (self.PC + offset) & 0xFFFF
        elif am == AM_INDIRECT:
            low = self.memory.read(self.PC)
            high = self.memory.read(self.PC + 1)
            self.PC = (self.PC + 2) & 0xFFFF
            addr = (high << 8) | low
            if low == 0xFF:
                return (self.memory.read(addr & 0xFF00) << 8) | self.memory.read(addr)
            else:
                return (self.memory.read(addr + 1) << 8) | self.memory.read(addr)
        elif am == AM_INDEXED_INDIRECT:
            base = self.memory.read(self.PC)
            self.PC = (self.PC + 1) & 0xFFFF
            addr = (base + self.X) & 0xFF
            low = self.memory.read(addr)
            high = self.memory.read((addr + 1) & 0xFF)
            return (high << 8) | low
        elif am == AM_INDIRECT_INDEXED:
            base = self.memory.read(self.PC)
            self.PC = (self.PC + 1) & 0xFFFF
            low = self.memory.read(base)
            high = self.memory.read((base + 1) & 0xFF)
            base_addr = (high << 8) | low
            final_addr = (base_addr + self.Y) & 0xFFFF
            if _is_read_iy(instr_id):
                if self._page_crossed(base_addr, final_addr):
                    self.memory.read((base_addr & 0xFF00) | ((base_addr + self.Y) & 0xFF))
                    penalty[0] = 1
            elif _is_write_iy(instr_id):
                self.memory.read((base_addr & 0xFF00) | ((base_addr + self.Y) & 0xFF))
            return final_addr
        return -1

    # ── Interrupt handling ──
    cdef void _handle_interrupt_c(self):
        cdef int vector_addr, low, high, status
        if self.interrupt_pending == "NMI":
            vector_addr = 0xFFFA
            self.in_nmi = True
            self.current_interrupt_type = "NMI"
        elif self.interrupt_pending == "IRQ":
            vector_addr = 0xFFFE
        elif self.interrupt_pending == "RST":
            vector_addr = 0xFFFC
        else:
            return

        self._push((self.PC >> 8) & 0xFF)
        self._push(self.PC & 0xFF)
        status = self._get_status() & 0xCF
        status |= 0x20
        self._push(status)

        self.I = 1
        self.interrupt_inhibit = 1

        low = self.memory.read(vector_addr)
        high = self.memory.read(vector_addr + 1)
        self.PC = (high << 8) | low
        self.interrupt_pending = None

    # ── Branch handling ──
    cdef int _do_branch(self, int instr_id, int address):
        cdef bint take = False
        cdef int old_pc, extra = 0
        if instr_id == I_BPL: take = self.N == 0
        elif instr_id == I_BMI: take = self.N == 1
        elif instr_id == I_BVC: take = self.V == 0
        elif instr_id == I_BVS: take = self.V == 1
        elif instr_id == I_BCC: take = self.C == 0
        elif instr_id == I_BCS: take = self.C == 1
        elif instr_id == I_BNE: take = self.Z == 0
        elif instr_id == I_BEQ: take = self.Z == 1

        if take:
            old_pc = self.PC
            self.PC = address
            extra = 1
            if self._page_crossed(old_pc, address):
                extra = 2
        return extra

    # ── Execute instruction ──
    cdef int _exec(self, int instr_id, int am, int address):
        """Execute instruction. Returns extra_cycles (beyond base)."""
        cdef int value, result, old_carry, temp, high_byte, status
        cdef int old_i, new_i

        if instr_id == I_LDA:
            self.A = self.memory.read(address)
            self._set_zn(self.A)
        elif instr_id == I_LDX:
            self.X = self.memory.read(address)
            self._set_zn(self.X)
        elif instr_id == I_LDY:
            self.Y = self.memory.read(address)
            self._set_zn(self.Y)
        elif instr_id == I_STA:
            self.memory.write(address, self.A)
        elif instr_id == I_STX:
            self.memory.write(address, self.X)
        elif instr_id == I_STY:
            self.memory.write(address, self.Y)
        elif instr_id == I_TAX:
            self.X = self.A; self._set_zn(self.X)
        elif instr_id == I_TAY:
            self.Y = self.A; self._set_zn(self.Y)
        elif instr_id == I_TSX:
            self.X = self.S; self._set_zn(self.X)
        elif instr_id == I_TXA:
            self.A = self.X; self._set_zn(self.A)
        elif instr_id == I_TXS:
            self.S = self.X
        elif instr_id == I_TYA:
            self.A = self.Y; self._set_zn(self.A)
        elif instr_id == I_PHA:
            self._push(self.A)
        elif instr_id == I_PLA:
            self.A = self._pop(); self._set_zn(self.A)
        elif instr_id == I_PHP:
            self._push(self._get_status() | 0x30)
        elif instr_id == I_PLP:
            status = self._pop()
            old_i = self.I
            new_i = (status >> 2) & 1
            temp = self._get_status()
            temp = (status & ~0x30) | (temp & 0x30)
            self._set_status(temp)
            if new_i != old_i:
                self.I = new_i
                if self.interrupt_inhibit != self.I:
                    self.pending_interrupt_inhibit = self.I
                    self.interrupt_latency_remaining = 1
                    self.interrupt_latency_armed = False
            else:
                self.I = new_i
        elif instr_id == I_ADC:
            value = self.memory.read(address)
            result = self.A + value + self.C
            self.V = 1 if ((self.A ^ result) & (value ^ result) & 0x80) else 0
            self.C = 1 if result > 255 else 0
            self.A = result & 0xFF; self._set_zn(self.A)
        elif instr_id == I_SBC:
            value = self.memory.read(address)
            result = self.A - value - (1 - self.C)
            self.V = 1 if ((self.A ^ result) & (~value ^ result) & 0x80) else 0
            self.C = 0 if result < 0 else 1
            self.A = result & 0xFF; self._set_zn(self.A)
        elif instr_id == I_AND:
            self.A = self.A & self.memory.read(address); self._set_zn(self.A)
        elif instr_id == I_EOR:
            self.A = self.A ^ self.memory.read(address); self._set_zn(self.A)
        elif instr_id == I_ORA:
            self.A = self.A | self.memory.read(address); self._set_zn(self.A)
        elif instr_id == I_ASL:
            if am == AM_ACCUMULATOR:
                self.C = 1 if self.A & 0x80 else 0
                self.A = (self.A << 1) & 0xFF; self._set_zn(self.A)
            else:
                value = self.memory.read(address)
                self.memory.write(address, value)
                self.C = 1 if value & 0x80 else 0
                value = (value << 1) & 0xFF
                self.memory.write(address, value); self._set_zn(value)
        elif instr_id == I_LSR:
            if am == AM_ACCUMULATOR:
                self.C = self.A & 1
                self.A = self.A >> 1; self._set_zn(self.A)
            else:
                value = self.memory.read(address)
                self.memory.write(address, value)
                self.C = value & 1
                value = value >> 1
                self.memory.write(address, value); self._set_zn(value)
        elif instr_id == I_ROL:
            if am == AM_ACCUMULATOR:
                old_carry = self.C
                self.C = 1 if self.A & 0x80 else 0
                self.A = ((self.A << 1) | old_carry) & 0xFF; self._set_zn(self.A)
            else:
                value = self.memory.read(address)
                self.memory.write(address, value)
                old_carry = self.C
                self.C = 1 if value & 0x80 else 0
                value = ((value << 1) | old_carry) & 0xFF
                self.memory.write(address, value); self._set_zn(value)
        elif instr_id == I_ROR:
            if am == AM_ACCUMULATOR:
                old_carry = self.C
                self.C = self.A & 1
                self.A = (self.A >> 1) | (old_carry << 7); self._set_zn(self.A)
            else:
                value = self.memory.read(address)
                self.memory.write(address, value)
                old_carry = self.C
                self.C = value & 1
                value = (value >> 1) | (old_carry << 7)
                self.memory.write(address, value); self._set_zn(value)
        elif instr_id == I_CMP:
            value = self.memory.read(address)
            self.C = 1 if self.A >= value else 0
            self._set_zn((self.A - value) & 0xFF)
        elif instr_id == I_CPX:
            value = self.memory.read(address)
            self.C = 1 if self.X >= value else 0
            self._set_zn((self.X - value) & 0xFF)
        elif instr_id == I_CPY:
            value = self.memory.read(address)
            self.C = 1 if self.Y >= value else 0
            self._set_zn((self.Y - value) & 0xFF)
        elif instr_id == I_BIT:
            value = self.memory.read(address)
            self.Z = 1 if (self.A & value) == 0 else 0
            self.V = 1 if value & 0x40 else 0
            self.N = 1 if value & 0x80 else 0
        elif instr_id == I_INC:
            value = self.memory.read(address)
            self.memory.write(address, value)
            value = (value + 1) & 0xFF
            self.memory.write(address, value); self._set_zn(value)
        elif instr_id == I_INX:
            self.X = (self.X + 1) & 0xFF; self._set_zn(self.X)
        elif instr_id == I_INY:
            self.Y = (self.Y + 1) & 0xFF; self._set_zn(self.Y)
        elif instr_id == I_DEC:
            value = self.memory.read(address)
            self.memory.write(address, value)
            value = (value - 1) & 0xFF
            self.memory.write(address, value); self._set_zn(value)
        elif instr_id == I_DEX:
            self.X = (self.X - 1) & 0xFF; self._set_zn(self.X)
        elif instr_id == I_DEY:
            self.Y = (self.Y - 1) & 0xFF; self._set_zn(self.Y)
        elif instr_id == I_JMP:
            self.PC = address
        elif instr_id == I_JSR:
            temp = (self.PC - 1) & 0xFFFF
            self._push((temp >> 8) & 0xFF)
            self._push(temp & 0xFF)
            self.PC = address
        elif instr_id == I_RTS:
            value = self._pop()
            high_byte = self._pop()
            self.PC = (((high_byte << 8) | value) + 1) & 0xFFFF
        elif instr_id == I_BRK:
            self.PC = (self.PC + 1) & 0xFFFF
            self._push((self.PC >> 8) & 0xFF)
            self._push(self.PC & 0xFF)
            if self.interrupt_pending == "NMI":
                self._push(self._get_status() | 0x30)
                self.I = 1; self.interrupt_inhibit = 1
                value = self.memory.read(0xFFFA)
                high_byte = self.memory.read(0xFFFB)
                self.PC = (high_byte << 8) | value
                self.interrupt_pending = None
            else:
                self._push(self._get_status() | 0x30)
                self.I = 1; self.interrupt_inhibit = 1
                value = self.memory.read(0xFFFE)
                high_byte = self.memory.read(0xFFFF)
                self.PC = (high_byte << 8) | value
        elif instr_id == I_RTI:
            status = self._pop()
            self._set_status((status & ~0x30) | (self._get_status() & 0x30))
            self.interrupt_inhibit = self.I
            value = self._pop()
            high_byte = self._pop()
            self.PC = (high_byte << 8) | value
            if self.in_nmi:
                self.in_nmi = False
                self.current_interrupt_type = None
        elif instr_id == I_CLC: self.C = 0
        elif instr_id == I_SEC: self.C = 1
        elif instr_id == I_CLI:
            self.I = 0
            if self.interrupt_inhibit != self.I:
                self.pending_interrupt_inhibit = self.I
                self.interrupt_latency_remaining = 1
                self.interrupt_latency_armed = False
        elif instr_id == I_SEI:
            self.I = 1
            if self.interrupt_inhibit != self.I:
                self.pending_interrupt_inhibit = self.I
                self.interrupt_latency_remaining = 1
                self.interrupt_latency_armed = False
        elif instr_id == I_CLV: self.V = 0
        elif instr_id == I_CLD: self.D = 0
        elif instr_id == I_SED: self.D = 1
        elif instr_id == I_NOP:
            if am == AM_IMMEDIATE:
                pass
            elif am in (AM_ZERO_PAGE, AM_ZERO_PAGE_X, AM_ABSOLUTE, AM_ABSOLUTE_X):
                if address >= 0:
                    self.memory.read(address)
        elif instr_id == I_LAX:
            value = self.memory.read(address)
            self.A = value; self.X = value; self._set_zn(value)
        elif instr_id == I_SAX:
            self.memory.write(address, self.A & self.X)
        elif instr_id == I_DCP:
            value = self.memory.read(address)
            self.memory.write(address, value)
            value = (value - 1) & 0xFF
            self.memory.write(address, value)
            self.C = 1 if self.A >= value else 0
            self._set_zn((self.A - value) & 0xFF)
        elif instr_id == I_ISC:
            value = self.memory.read(address)
            self.memory.write(address, value)
            value = (value + 1) & 0xFF
            self.memory.write(address, value)
            result = self.A - value - (1 - self.C)
            self.V = 1 if ((self.A ^ result) & (~value ^ result) & 0x80) else 0
            self.C = 0 if result < 0 else 1
            self.A = result & 0xFF; self._set_zn(self.A)
        elif instr_id == I_SLO:
            value = self.memory.read(address)
            self.memory.write(address, value)
            self.C = 1 if value & 0x80 else 0
            value = (value << 1) & 0xFF
            self.memory.write(address, value)
            self.A = self.A | value; self._set_zn(self.A)
        elif instr_id == I_RLA:
            value = self.memory.read(address)
            self.memory.write(address, value)
            old_carry = self.C
            self.C = 1 if value & 0x80 else 0
            value = ((value << 1) | old_carry) & 0xFF
            self.memory.write(address, value)
            self.A = self.A & value; self._set_zn(self.A)
        elif instr_id == I_SRE:
            value = self.memory.read(address)
            self.memory.write(address, value)
            self.C = value & 1
            value = value >> 1
            self.memory.write(address, value)
            self.A = self.A ^ value; self._set_zn(self.A)
        elif instr_id == I_RRA:
            value = self.memory.read(address)
            self.memory.write(address, value)
            old_carry = self.C
            self.C = value & 1
            value = (value >> 1) | (old_carry << 7)
            self.memory.write(address, value)
            result = self.A + value + self.C
            self.V = 1 if ((self.A ^ result) & (value ^ result) & 0x80) else 0
            self.C = 1 if result > 255 else 0
            self.A = result & 0xFF; self._set_zn(self.A)
        elif instr_id == I_LAS:
            value = self.memory.read(address)
            result = value & self.S
            self.A = result; self.X = result; self.S = result
            self._set_zn(result)
        elif instr_id == I_TAS:
            self.S = self.A & self.X
            high_byte = (address >> 8) & 0xFF
            self.memory.write(address & 0xFFFF, self.A & self.X & (high_byte + 1))
        elif instr_id == I_KIL:
            self.PC = (self.PC - 1) & 0xFFFF
            if self.jam_reported_at != self.PC:
                print(f"KIL instruction executed at PC: 0x{self.PC:04X} - processor halted")
                self.jam_reported_at = self.PC
            return 0
        elif instr_id == I_SHX:
            high_byte = (address >> 8) & 0xFF
            self.memory.write(address & 0xFFFF, self.X & (high_byte + 1))
        elif instr_id == I_SHA:
            high_byte = (address >> 8) & 0xFF
            self.memory.write(address & 0xFFFF, self.A & self.X & (high_byte + 1))
        elif instr_id == I_ALR:
            value = self.memory.read(address)
            self.A = self.A & value
            self.C = self.A & 1
            self.A = self.A >> 1; self._set_zn(self.A)
        elif instr_id == I_ANC:
            value = self.memory.read(address)
            self.A = self.A & value; self._set_zn(self.A)
            self.C = self.N
        elif instr_id == I_ARR:
            value = self.memory.read(address)
            self.A = self.A & value
            old_carry = self.C
            self.A = (self.A >> 1) | (old_carry << 7)
            self._set_zn(self.A)
            self.C = (self.A >> 6) & 1
            self.V = ((self.A >> 6) ^ (self.A >> 5)) & 1
        elif instr_id == I_AXS:
            value = self.memory.read(address)
            temp = (self.A & self.X) - value
            self.C = 0 if temp < 0 else 1
            self.X = temp & 0xFF; self._set_zn(self.X)
        elif instr_id == I_SHY:
            high_byte = (address >> 8) & 0xFF
            self.memory.write(address & 0xFFFF, self.Y & (high_byte + 1))
        elif instr_id == I_XAA:
            value = self.memory.read(address)
            self.A = (self.A | 0xFF) & self.X & value; self._set_zn(self.A)
        # Branches are handled separately
        return 0

    # ── Main step ──
    cpdef int step(self):
        self.odd_cycle = 1 - self.odd_cycle
        self.total_cycles += 1

        if self.dma_cycles > 0:
            self.dma_cycles -= 1
            return 1

        if self.cycles > 0:
            self.cycles -= 1
            return 1

        cdef int cycles_consumed = self._run_instruction()
        self.cycles = cycles_consumed - 1
        return 1

    cdef int _run_instruction(self):
        cdef int opcode, base_cycles, instr_id, am, length
        cdef int address, page_penalty, extra_cycles, branch_cycles, total
        cdef int penalty_storage

        # Interrupt recognition
        if self.interrupt_pending is not None and self.interrupt_state == 0:
            if self.interrupt_pending == "NMI":
                self._handle_interrupt_c()
                self.interrupt_pending = None
                self.interrupt_state = 0
                return 7
            elif self.interrupt_pending == "IRQ":
                if self.interrupt_inhibit == 0:
                    self._handle_interrupt_c()
                    self.interrupt_pending = None
                    self.interrupt_state = 0
                    return 7

        self.current_instruction_pc = self.PC
        opcode = self.memory.read(self.PC)
        self.PC = (self.PC + 1) & 0xFFFF

        # KIL detection
        if opcode in KIL_SET:
            if self.jam_reported_at != self.current_instruction_pc:
                print(f"CPU JAM: KIL opcode 0x{opcode:02X} at PC=0x{self.current_instruction_pc:04X}")
                self.jam_reported_at = self.current_instruction_pc

        base_cycles = CYCLE_TABLE[opcode]
        instr_id = OP_INSTR[opcode]
        am = OP_AMODE[opcode]

        # Resolve address
        address = self._resolve_address(am, instr_id, &penalty_storage)

        # Execute
        extra_cycles = self._exec(instr_id, am, address)

        # Handle branches
        branch_cycles = 0
        if _is_branch(instr_id):
            branch_cycles = self._do_branch(instr_id, address)

        total = base_cycles + extra_cycles + branch_cycles + penalty_storage

        # End-of-instruction latency processing
        if self.interrupt_latency_remaining > 0:
            if not self.interrupt_latency_armed:
                self.interrupt_latency_armed = True
            else:
                self.interrupt_latency_remaining -= 1
                if self.interrupt_latency_remaining == 0:
                    self.interrupt_inhibit = self.pending_interrupt_inhibit

        return total

    # ── Python-visible compatibility methods ──
    def run_instruction(self):
        return self._run_instruction()

    def trigger_interrupt(self, interrupt_type):
        if interrupt_type == "NMI":
            self.interrupt_pending = "NMI"
            self.interrupt_state = 0
        elif interrupt_type == "IRQ" and self.interrupt_pending != "NMI":
            self.interrupt_pending = "IRQ"

    def add_dma_cycles(self, int cycles):
        self.dma_cycles += cycles
        if self.odd_cycle:
            self.dma_cycles += 1

    def get_status_byte(self):
        return self._get_status()

    def set_status_byte(self, int value):
        self._set_status(value)

    def set_zero_negative(self, int value):
        self._set_zn(value)

    def push_stack(self, int value):
        self._push(value)

    def pop_stack(self):
        return self._pop()

    # Legacy compatibility - these are needed if anything calls them via Python
    def execute_lda(self, operand, addressing_mode): self.A = self.memory.read(operand); self._set_zn(self.A)
    def execute_ldx(self, operand, addressing_mode): self.X = self.memory.read(operand); self._set_zn(self.X)
    def execute_ldy(self, operand, addressing_mode): self.Y = self.memory.read(operand); self._set_zn(self.Y)
    def execute_sta(self, operand, addressing_mode): self.memory.write(operand, self.A)
    def execute_stx(self, operand, addressing_mode): self.memory.write(operand, self.X)
    def execute_sty(self, operand, addressing_mode): self.memory.write(operand, self.Y)
    def execute_nop(self, operand, addressing_mode): pass
    def execute_kil(self, operand, addressing_mode): pass
