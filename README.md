# NEZ - NES Emulator

A Nintendo Entertainment System (NES) emulator written (99% vibe-coded) in Python using SDL2 for graphics. Curious to see how far I can get to a working emulator with the right set of prompts. 

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
pipenv install
```

## Usage

Run the emulator with a ROM file:

```bash
pipenv run python main.py mario.nes
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
