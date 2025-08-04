# NEZ - NES Emulator

A Nintendo Entertainment System (NES) emulator written in Python using SDL2 for graphics.

## Features

- **6502 CPU Emulation**: Full implementation of the MOS Technology 6502 processor
- **PPU (Picture Processing Unit)**: Graphics rendering with sprite and background support
- **Memory Management**: Proper memory mapping and cartridge support
- **Controller Input**: Support for standard NES controller
- **SDL2 Graphics**: Hardware-accelerated rendering
- **NROM Mapper**: Support for simple cartridges (Mapper 0)

## Requirements

- Python 3.7+
- PySDL2 (already in Pipfile)
- PySDL2-dll (already in Pipfile)

## Installation

The environment is already set up with pipenv. Just activate it:

```bash
pipenv shell
```

## Usage

Run the emulator with a ROM file:

```bash
python main.py mario.nes
```

### Controls

| Key | NES Button |
|-----|------------|
| Arrow Keys | D-Pad |
| Z | A Button |
| X | B Button |
| Space | Select |
| Enter | Start |
| R | Reset |
| Escape | Quit |

## Testing

Run the test suite to verify the emulator components:

```bash
python test.py
```

## ROM Compatibility

Currently supports:

- NROM (Mapper 0) cartridges
- Games like Super Mario Bros, Donkey Kong, etc.

## Architecture

The emulator consists of several key components:

### CPU (`cpu.py`)

- Complete 6502 instruction set
- All addressing modes
- Proper cycle timing
- Interrupt handling

### PPU (`ppu.py`)

- Background and sprite rendering
- Proper timing (3 PPU cycles per CPU cycle)
- VBlank and NMI generation
- Palette system

### Memory (`memory.py`)

- CPU memory mapping
- PPU memory access
- Cartridge interface
- Controller input handling

### Main Emulator (`nes.py`)

- Coordinates all components
- Frame timing
- State management

### Graphics (`main.py`)

- SDL2 integration
- Input handling
- Display scaling
- FPS monitoring

## Implementation Notes

### CPU Accuracy

- Cycle-accurate execution
- All documented 6502 instructions
- Proper flag handling
- Stack operations

### PPU Accuracy

- Scanline-based rendering
- Sprite evaluation
- Background scrolling
- Palette handling

### Memory Layout

```
$0000-$07FF: 2KB internal RAM (mirrored to $0800-$1FFF)
$2000-$2007: PPU registers (mirrored to $2008-$3FFF)
$4000-$4017: APU and I/O registers
$4020-$FFFF: Cartridge space (PRG ROM/RAM)
```

### PPU Memory Layout

```
$0000-$0FFF: Pattern Table 0
$1000-$1FFF: Pattern Table 1
$2000-$23FF: Name Table 0
$2400-$27FF: Name Table 1
$2800-$2BFF: Name Table 2
$2C00-$2FFF: Name Table 3
$3000-$3EFF: Mirrors of $2000-$2EFF
$3F00-$3F1F: Palette RAM
$3F20-$3FFF: Mirrors of $3F00-$3F1F
```

## Debugging

The emulator provides state inspection methods:

```python
cpu_state = nes.get_cpu_state()
ppu_state = nes.get_ppu_state()
```

## Known Limitations

- Only NROM mapper supported
- No APU (sound) implementation
- Limited to basic controller input
- No save state functionality

## Future Improvements

- Additional mappers (MMC1, MMC3, etc.)
- APU and sound generation
- Save states
- Debugger interface
- Better accuracy optimizations

## Resources

- [NESDev Wiki](https://www.nesdev.org/wiki/Nesdev_Wiki)
- [6502 Reference](http://www.6502.org/tutorials/6502opcodes.html)
- [NES PPU Reference](https://www.nesdev.org/wiki/PPU)

## License

This project is for educational purposes.
