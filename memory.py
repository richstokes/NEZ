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
        self.apu = None  # APU reference

        # Open bus value - important for accurate memory behavior
        self.bus = 0

        # Controller state
        self.controller1 = 0
        self.controller2 = 0
        self.controller1_shift = 0
        self.controller2_shift = 0
        self.controller1_index = 0
        self.controller2_index = 0
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

    def set_apu(self, apu):
        """Set the APU reference"""
        self.apu = apu

    def read(self, addr):
        """Read from CPU memory"""
        addr = addr & 0xFFFF

        if addr < 0x2000:
            # Internal RAM (mirrored every 2KB)
            self.bus = self.ram[addr & 0x7FF]
            return self.bus
        elif addr < 0x4000:
            # PPU registers (mirrored every 8 bytes)
            ppu_addr = 0x2000 + (addr & 7)
            self.bus = self.ppu.read_register(ppu_addr)
            return self.bus
        elif addr == 0x4015:
            # APU Status register
            if self.apu:
                self.bus = self.apu.read_status()
                return self.bus
            return self.bus
        elif addr == 0x4016:
            # Controller 1 - NES standard controller read
            if self.controller1_index > 7:
                # Return 1 for reads beyond 8 buttons (open bus)
                result = 1
            else:
                # Return the current bit
                result = (self.controller1_shift >> self.controller1_index) & 1
                if not self.strobe:
                    # Only advance index if not strobing
                    self.controller1_index += 1

            # Preserve upper bits from open bus (bit 7-5) and mix in result
            self.bus = (
                (self.bus & 0xE0) | (result & 0x01) | 0x40
            )  # Bit 6 often set on real hardware
            return self.bus
        elif addr == 0x4017:
            # Controller 2 - same logic as controller 1
            if self.controller2_index > 7:
                result = 1
            else:
                result = (self.controller2_shift >> self.controller2_index) & 1
                if not self.strobe:
                    self.controller2_index += 1

            # Preserve upper bits from open bus
            self.bus = (self.bus & 0xE0) | (result & 0x01) | 0x40
            return self.bus
        elif addr < 0x4020:
            # APU and I/O registers - return open bus for unimplemented
            return self.bus
        else:
            # Cartridge space
            if self.cartridge:
                self.bus = self.cartridge.cpu_read(addr)
                return self.bus
            return self.bus

    def write(self, addr, value):
        """Write to CPU memory"""
        addr = addr & 0xFFFF
        value = value & 0xFF

        # Update bus value
        old_bus = self.bus
        self.bus = value

        if addr < 0x2000:
            # Internal RAM (mirrored every 2KB)
            self.ram[addr & 0x7FF] = value
        elif addr < 0x4000:
            # PPU registers (mirrored every 8 bytes)
            ppu_addr = 0x2000 + (addr & 7)
            self.ppu.write_register(ppu_addr, value)
        elif addr == 0x4014:
            # OAM DMA - critical for sprite data transfer
            start_addr = value * 0x100

            # Try to use direct memory access for speed
            ptr_data, offset = self.get_ptr(start_addr)
            if ptr_data is not None and offset + 256 <= len(ptr_data):
                # Fast path - direct memory copy
                for i in range(256):
                    self.ppu.oam[i] = ptr_data[offset + i]
                # Update bus with last byte transferred
                self.bus = ptr_data[offset + 255]
            else:
                # Slow path - use memory reads (handles bank switching)
                for i in range(256):
                    self.ppu.oam[i] = self.read(start_addr + i)

            # DMA takes 513 CPU cycles + 1 if on odd cycle (hardware-accurate)
            if hasattr(self.cpu, "add_dma_cycles"):
                self.cpu.add_dma_cycles(513)
        elif addr == 0x4016:
            # Controller strobe register - controls both controllers
            old_strobe = self.strobe
            self.strobe = value & 1

            if self.strobe:
                # Strobe high - reset controller read indices and latch current state
                self.controller1_index = 0
                self.controller2_index = 0
                self.controller1_shift = self.controller1
                self.controller2_shift = self.controller2

            # Update bus with mixed old/new values as per hardware
            self.bus = (old_bus & 0xE0) | (value & 0x1F)
        elif addr >= 0x4000 and addr <= 0x4017:
            # APU registers
            if self.apu:
                self.apu.write_register(addr, value)
        elif addr < 0x4020:
            # Other I/O registers - not implemented but preserve bus
            pass
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

    def get_ptr(self, addr):
        """Get direct memory pointer for fast access (for DMA optimization)"""
        if addr < 0x2000:
            # Internal RAM
            return self.ram, addr & 0x7FF
        elif 0x6000 <= addr < 0x8000 and self.cartridge and self.cartridge.prg_ram:
            # PRG RAM
            return self.cartridge.prg_ram, addr - 0x6000
        return None, 0


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
        if addr < 0x6000:
            # Expansion ROM area - typically not used, return open bus
            return 0
        elif 0x6000 <= addr <= 0x7FFF:
            # PRG RAM/SRAM
            return self.prg_ram[addr - 0x6000]
        elif addr >= 0x8000:
            # PRG ROM
            if self.mapper == 0:  # NROM
                if self.prg_rom_size == 1:
                    # 16KB ROM mirrored to both 0x8000-0xBFFF and 0xC000-0xFFFF
                    return self.prg_rom[(addr - 0x8000) & 0x3FFF]
                else:
                    # 32KB ROM
                    return self.prg_rom[addr - 0x8000]
            else:
                # Other mappers - simple fallback
                return self.prg_rom[(addr - 0x8000) % len(self.prg_rom)]
        return 0

    def cpu_write(self, addr, value):
        """Write to cartridge (CPU side)"""
        if addr < 0x6000:
            # Expansion ROM area - typically not writable
            return
        elif 0x6000 <= addr <= 0x7FFF:
            # PRG RAM/SRAM
            self.prg_ram[addr - 0x6000] = value
        elif addr >= 0x8000:
            # PRG ROM area - mapper register writes
            if self.mapper == 0:  # NROM
                # NROM doesn't have mapper registers, writes are ignored
                pass
            else:
                # Other mappers would handle bank switching here
                pass

    def ppu_read(self, addr):
        """Read from cartridge (PPU side)"""
        if addr < 0x2000:
            # Pattern tables (CHR ROM/RAM)
            if addr < len(self.chr_rom):
                return self.chr_rom[addr]
        return 0

    def ppu_write(self, addr, value):
        """Write to cartridge (PPU side)"""
        if addr < 0x2000:
            # CHR RAM (if no CHR ROM) - only writable if CHR RAM
            if self.chr_rom_size == 0 and addr < len(self.chr_rom):
                self.chr_rom[addr] = value
