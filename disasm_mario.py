#!/usr/bin/env python3

rom_data = open('mario.nes', 'rb').read()
prg_start = 16 + 512  # Skip header and trainer if present  
prg_rom = rom_data[prg_start:prg_start+32768]

def disassemble(data, start_addr, count=20):
    opcodes = {
        0x00: ('BRK', 1, ''),
        0x4C: ('JMP', 3, 'abs'),
        0xA9: ('LDA', 2, '#'),
        0xAD: ('LDA', 3, 'abs'),
        0x8D: ('STA', 3, 'abs'),
        0x10: ('BPL', 2, 'rel'),
        0x30: ('BMI', 2, 'rel'),
        0x78: ('SEI', 1, ''),
        0xD8: ('CLD', 1, ''),
        0xA2: ('LDX', 2, '#'),
        0x9A: ('TXS', 1, ''),
        0xCA: ('DEX', 1, ''),
        0xD0: ('BNE', 2, 'rel'),
        0x20: ('JSR', 3, 'abs'),
        0x60: ('RTS', 1, ''),
        0x18: ('CLC', 1, ''),
        0x38: ('SEC', 1, ''),
        0x08: ('PHP', 1, ''),
        0x28: ('PLP', 1, ''),
        0x48: ('PHA', 1, ''),
        0x68: ('PLA', 1, ''),
        0xAA: ('TAX', 1, ''),
        0x8A: ('TXA', 1, ''),
        0xA8: ('TAY', 1, ''),
        0x98: ('TYA', 1, ''),
        0x85: ('STA', 2, 'zp'),
        0xA5: ('LDA', 2, 'zp'),
        0x95: ('STA', 2, 'zpx'),
        0xB5: ('LDA', 2, 'zpx'),
        0x8E: ('STX', 3, 'abs'),
        0xAE: ('LDX', 3, 'abs'),
        0x8C: ('STY', 3, 'abs'),
        0xAC: ('LDY', 3, 'abs'),
        0xC9: ('CMP', 2, '#'),
        0xCD: ('CMP', 3, 'abs'),
        0xF0: ('BEQ', 2, 'rel'),
        0x84: ('STY', 2, 'zp'),
        0x86: ('STX', 2, 'zp'),
        0xA0: ('LDY', 2, '#'),
        0x88: ('DEY', 1, ''),
        0xE8: ('INX', 1, ''),
        0xC8: ('INY', 1, ''),
        0xEA: ('NOP', 1, ''),
    }
    
    output = []
    offset = start_addr - 0x8000
    for i in range(count):
        if offset >= len(data):
            break
        opcode = data[offset]
        if opcode in opcodes:
            name, length, mode = opcodes[opcode]
            addr = 0x8000 + offset
            
            if length == 1:
                output.append(f'  ${addr:04X}: ${opcode:02X}      {name}')
            elif length == 2:
                if offset + 1 < len(data):
                    operand = data[offset + 1]
                    if mode == 'rel':
                        target = addr + 2 + ((operand - 256) if operand > 127 else operand)
                        output.append(f'  ${addr:04X}: ${opcode:02X} ${operand:02X}   {name} ${target:04X}')
                    else:
                        output.append(f'  ${addr:04X}: ${opcode:02X} ${operand:02X}   {name} {mode}${operand:02X}')
            elif length == 3:
                if offset + 2 < len(data):
                    lo = data[offset + 1]
                    hi = data[offset + 2]
                    target = hi * 256 + lo
                    if mode == 'abs':
                        output.append(f'  ${addr:04X}: ${opcode:02X} ${lo:02X} ${hi:02X} {name} ${target:04X}')
                    else:
                        output.append(f'  ${addr:04X}: ${opcode:02X} ${lo:02X} ${hi:02X} {name} {mode}${target:04X}')
        else:
            addr = 0x8000 + offset
            output.append(f'  ${addr:04X}: ${opcode:02X}      .byte ${opcode:02X}')
            
        offset += length if opcode in opcodes else 1
    
    return output

# Disassemble from the reset vector area
print('NES reset vector and early boot code:')
for line in disassemble(prg_rom, 0x8000, 30):
    print(line)
