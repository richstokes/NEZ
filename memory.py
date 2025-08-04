"""
NES Memory Management
Handles CPU and PPU memory mapping
"""


class Memory:
    def __init__(self):
        # CPU Memory
        self.ram = [0] * 0x800  # 2KB internal RAM
        self.cartridge = None  # Cartridge reference
        self.ppu = None  # PPU reference
        self.cpu = None  # CPU reference (for NMI)

        # Controller state
        self.controller1 = 0
        self.controller2 = 0
        self.controller1_shift = 0
        self.controller2_shift = 0
        self.strobe = 0

    def set_cartridge(self, cartridge):
        """Set the cartridge reference"""
        self.cartridge = cartridge

    def set_ppu(self, ppu):
        """Set the PPU reference"""
        self.ppu = ppu

    def set_cpu(self, cpu):
        """Set the CPU reference"""
        self.cpu = cpu

    def read(self, addr):
        """Read from CPU memory"""
        addr = addr & 0xFFFF

        if addr < 0x2000:
            # Internal RAM (mirrored)
            return self.ram[addr & 0x7FF]
        elif addr < 0x4000:
            # PPU registers (mirrored)
            return self.ppu.read_register(0x2000 + (addr & 7))
        elif addr == 0x4016:
            # Controller 1
            result = self.controller1_shift & 1
            self.controller1_shift >>= 1
            return result
        elif addr == 0x4017:
            # Controller 2
            result = self.controller2_shift & 1
            self.controller2_shift >>= 1
            return result
        elif addr < 0x4020:
            # APU and I/O registers
            return 0  # Not implemented
        else:
            # Cartridge space
            if self.cartridge:
                return self.cartridge.cpu_read(addr)
            return 0

    def write(self, addr, value):
        """Write to CPU memory"""
        addr = addr & 0xFFFF
        value = value & 0xFF

        if addr < 0x2000:
            # Internal RAM (mirrored)
            self.ram[addr & 0x7FF] = value
        elif addr < 0x4000:
            # PPU registers (mirrored)
            self.ppu.write_register(0x2000 + (addr & 7), value)
        elif addr == 0x4014:
            # OAM DMA
            start_addr = value * 0x100
            for i in range(256):
                self.ppu.oam[i] = self.read(start_addr + i)
        elif addr == 0x4016:
            # Controller strobe
            if self.strobe == 1 and (value & 1) == 0:
                # Latch controller state
                self.controller1_shift = self.controller1
                self.controller2_shift = self.controller2
            self.strobe = value & 1
        elif addr < 0x4020:
            # APU and I/O registers
            pass  # Not implemented
        else:
            # Cartridge space
            if self.cartridge:
                self.cartridge.cpu_write(addr, value)

    def ppu_read(self, addr):
        """Read from PPU memory (pattern tables)"""
        if self.cartridge:
            return self.cartridge.ppu_read(addr)
        return 0

    def ppu_write(self, addr, value):
        """Write to PPU memory (pattern tables)"""
        if self.cartridge:
            self.cartridge.ppu_write(addr, value)

    def set_controller_state(self, controller, buttons):
        """Set controller button state
        buttons: 8-bit value representing A, B, Select, Start, Up, Down, Left, Right
        """
        if controller == 1:
            self.controller1 = buttons
        elif controller == 2:
            self.controller2 = buttons


class Cartridge:
    """NES Cartridge (ROM) loader and mapper"""

    def __init__(self, rom_path):
        self.rom_path = rom_path
        self.prg_rom = []  # Program ROM
        self.chr_rom = []  # Character ROM
        self.prg_ram = [0] * 0x2000  # PRG RAM (8KB)

        # Header info
        self.prg_rom_size = 0  # Size in 16KB units
        self.chr_rom_size = 0  # Size in 8KB units
        self.mapper = 0  # Mapper number
        self.mirroring = 0  # 0=horizontal, 1=vertical
        self.has_battery = False
        self.has_trainer = False
        self.four_screen = False

        self.load_rom()

    def load_rom(self):
        """Load ROM file"""
        with open(self.rom_path, "rb") as f:
            # Read header
            header = f.read(16)

            if header[:4] != b"NES\x1a":
                raise ValueError("Invalid NES ROM file")

            self.prg_rom_size = header[4]
            self.chr_rom_size = header[5]

            flags6 = header[6]
            flags7 = header[7]

            self.mirroring = flags6 & 1
            self.has_battery = (flags6 >> 1) & 1
            self.has_trainer = (flags6 >> 2) & 1
            self.four_screen = (flags6 >> 3) & 1

            self.mapper = (flags6 >> 4) | (flags7 & 0xF0)

            # Skip trainer if present
            if self.has_trainer:
                f.read(512)

            # Read PRG ROM
            prg_size = self.prg_rom_size * 16384
            self.prg_rom = list(f.read(prg_size))

            # Read CHR ROM
            if self.chr_rom_size > 0:
                chr_size = self.chr_rom_size * 8192
                self.chr_rom = list(f.read(chr_size))
            else:
                # CHR RAM
                self.chr_rom = [0] * 8192

        print(f"Loaded ROM: {self.rom_path}")
        print(f"PRG ROM: {self.prg_rom_size * 16}KB")
        print(f"CHR ROM: {self.chr_rom_size * 8}KB")
        print(f"Mapper: {self.mapper}")
        print(f"Mirroring: {'Vertical' if self.mirroring else 'Horizontal'}")

    def cpu_read(self, addr):
        """Read from cartridge (CPU side)"""
        if 0x6000 <= addr <= 0x7FFF:
            # PRG RAM
            return self.prg_ram[addr - 0x6000]
        elif addr >= 0x8000:
            # PRG ROM
            if self.mapper == 0:  # NROM
                if self.prg_rom_size == 1:
                    # 16KB ROM mirrored
                    return self.prg_rom[(addr - 0x8000) & 0x3FFF]
                else:
                    # 32KB ROM
                    return self.prg_rom[addr - 0x8000]
            else:
                # Other mappers not implemented
                return self.prg_rom[(addr - 0x8000) % len(self.prg_rom)]
        return 0

    def cpu_write(self, addr, value):
        """Write to cartridge (CPU side)"""
        if 0x6000 <= addr <= 0x7FFF:
            # PRG RAM
            self.prg_ram[addr - 0x6000] = value
        elif addr >= 0x8000:
            # Mapper registers (not implemented for NROM)
            pass

    def ppu_read(self, addr):
        """Read from cartridge (PPU side)"""
        if addr < 0x2000:
            # Pattern tables
            if len(self.chr_rom) > 0:
                return self.chr_rom[addr]
        return 0

    def ppu_write(self, addr, value):
        """Write to cartridge (PPU side)"""
        if addr < 0x2000:
            # CHR RAM (if no CHR ROM)
            if self.chr_rom_size == 0:
                self.chr_rom[addr] = value
