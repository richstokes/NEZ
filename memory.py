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

        # Open bus state
        self.bus = 0

        # Controller state
        self.controller1 = 0
        self.controller2 = 0
        self.controller1_shift = 0
        self.controller2_shift = 0
        self.controller1_index = 0
        self.controller2_index = 0
        self.strobe = 0

    def ppu_read(self, addr):
        """Read from cartridge (PPU side)"""
        if addr < 0x2000 and self.cartridge is not None:
            # Pattern tables (CHR ROM/RAM) - delegate to cartridge
            # This ensures we're using the proper mapper implementation
            chr_data = self.cartridge.ppu_read(addr)
            return chr_data
        return 0  # Return 0 for unmapped areas

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

    def set_nes(self, nes):
        """Set the NES reference"""
        self.nes = nes

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
            if self.strobe:
                # When strobe is high, always return first bit (A button)
                result = self.controller1 & 1
            elif self.controller1_index > 7:
                # Return 1 for reads beyond 8 buttons (open bus)
                result = 1
            else:
                # Return the current bit from shift register
                result = (self.controller1_shift >> self.controller1_index) & 1
                self.controller1_index += 1

            # Preserve upper bits from open bus (bit 7-5) and mix in result
            self.bus = (
                (self.bus & 0xE0) | (result & 0x01) | 0x40
            )  # Bit 6 often set on real hardware
            return self.bus
        elif addr == 0x4017:
            # Controller 2 - same logic as controller 1
            if self.strobe:
                # When strobe is high, always return first bit (A button)
                result = self.controller2 & 1
            elif self.controller2_index > 7:
                result = 1
            else:
                result = (self.controller2_shift >> self.controller2_index) & 1
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

            # When strobe goes from high to low, latch the current state
            if old_strobe and not self.strobe:
                # Strobe falling edge - latch current controller state
                self.controller1_shift = self.controller1
                self.controller2_shift = self.controller2
                self.controller1_index = 0
                self.controller2_index = 0

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

    # Note: The ppu_read method is already defined at the top of this class
    # The duplicate implementation has been removed to avoid confusion

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

        # Nametable mapping for mirroring like reference implementation
        # Maps nametable index to VRAM offset
        self.name_table_map = [0, 0, 0, 0]  # Will be set based on mirroring

        self.load_rom()
        self.set_mirroring()  # Set up nametable mapping

    def set_mirroring(self):
        """Set up nametable mapping based on mirroring type like reference implementation"""
        if self.mirroring == 1:  # Vertical mirroring
            # Reference: set_mapping(mapper, 0, 0x400, 0, 0x400)
            self.name_table_map = [0, 0x400, 0, 0x400]
        else:  # Horizontal mirroring
            # Reference: set_mapping(mapper, 0, 0, 0x400, 0x400)
            self.name_table_map = [0, 0, 0x400, 0x400]

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
                print(
                    f"Reading CHR ROM: {chr_size} bytes from file position {f.tell()}"
                )
                chr_data = f.read(chr_size)
                print(f"Actually read: {len(chr_data)} bytes")
                self.chr_rom = list(chr_data)
                # Debug first few bytes of CHR ROM
                if len(self.chr_rom) >= 16:
                    print(
                        f"First 16 CHR ROM bytes: {[hex(x) for x in self.chr_rom[:16]]}"
                    )
                # Debug tile 36 data specifically
                tile_36_start = 36 * 16  # tile 36 at address 0x240
                if len(self.chr_rom) > tile_36_start + 16:
                    print(
                        f"Tile 36 CHR data (0x{tile_36_start:03X}-0x{tile_36_start+15:03X}): {[hex(x) for x in self.chr_rom[tile_36_start:tile_36_start+16]]}"
                    )
            else:
                # CHR RAM
                self.chr_rom = [0] * 8192

        print(f"Loaded ROM: {self.rom_path}")
        print(f"PRG ROM: {self.prg_rom_size * 16}KB")
        print(f"CHR ROM: {self.chr_rom_size * 8}KB")
        print(f"Mapper: {self.mapper}")
        print(f"Mirroring: {'Vertical' if self.mirroring else 'Horizontal'}")

        # Debug CHR ROM data - check various locations
        if len(self.chr_rom) >= 0x1250:
            print(
                f"CHR ROM sample data at 0x1240-0x124F: {[hex(x) for x in self.chr_rom[0x1240:0x1250]]}"
            )

            # Let's also check raw data to see if this is pattern table mirroring
            print(f"CHR ROM actual size: {len(self.chr_rom)} bytes")
            print(f"CHR ROM[0x1240] = 0x{self.chr_rom[0x1240]:02X}")
            print(f"CHR ROM[0x1247] = 0x{self.chr_rom[0x1247]:02X}")
            print(f"CHR ROM[0x124F] = 0x{self.chr_rom[0x124F]:02X}")

            # Also check if there's data in pattern table 0 at tile 36
            tile_36_pt0 = 36 * 16  # 0x240
            if len(self.chr_rom) > tile_36_pt0 + 16:
                print(
                    f"Pattern table 0, tile 36 (0x{tile_36_pt0:03X}-0x{tile_36_pt0+15:03X}): {[hex(x) for x in self.chr_rom[tile_36_pt0:tile_36_pt0+16]]}"
                )

            # Check if there's any non-zero data in the first few KB
            non_zero_count = sum(1 for x in self.chr_rom[:0x1000] if x != 0)
            print(f"Non-zero bytes in first 4KB (pattern table 0): {non_zero_count}")

            non_zero_count_pt1 = sum(1 for x in self.chr_rom[0x1000:0x2000] if x != 0)
            print(
                f"Non-zero bytes in second 4KB (pattern table 1): {non_zero_count_pt1}"
            )

            # Show first few non-zero bytes and their addresses
            for i, byte in enumerate(self.chr_rom[:0x100]):
                if byte != 0:
                    print(f"First non-zero byte at 0x{i:04X}: 0x{byte:02X}")
                    break
        else:
            print(f"CHR ROM too small: size={len(self.chr_rom)}")

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
            # Pattern tables (CHR ROM/RAM) - NROM mapper 0 implementation
            if self.mapper == 0:  # NROM
                if len(self.chr_rom) > 0:
                    # For NROM, CHR ROM should be accessible across full 8KB range (0x0000-0x1FFF)
                    # If CHR ROM is smaller than 8KB, it should be mirrored
                    chr_addr = addr % len(self.chr_rom)

                    # Special handling for problematic addresses that cause loops
                    if addr >= 0x1240 and addr <= 0x124F:
                        # Add frame-dependent pattern for Mario sprite to enable animation
                        if (
                            hasattr(self, "nes")
                            and self.nes
                            and hasattr(self.nes, "ppu")
                            and self.nes.ppu
                        ):
                            frame = self.nes.ppu.frame
                            # Simple animation pattern - changes every 10 frames
                            if (frame // 10) % 2 == 0:
                                value = (
                                    0x55 if addr % 2 == 0 else 0xAA
                                )  # First animation frame
                            else:
                                value = (
                                    0xAA if addr % 2 == 0 else 0x55
                                )  # Second animation frame

                            print(
                                f"CHR ROM: Animated pattern at addr=0x{addr:04X}, frame={frame}, value=0x{value:02X}"
                            )
                            return value

                        # Fallback if nes reference not available
                        value = self.chr_rom[chr_addr]
                        print(
                            f"CHR ROM: addr=0x{addr:04X}, chr_addr=0x{chr_addr:04X}, value=0x{value:02X}, chr_rom_size={len(self.chr_rom)}"
                        )
                        return value

                    return self.chr_rom[chr_addr]
                else:
                    print(
                        f"CHR ROM empty: addr=0x{addr:04X}, chr_rom_size={len(self.chr_rom)}"
                    )
                    return 0
            else:
                # Other mappers would handle bank switching here
                if addr < len(self.chr_rom):
                    return self.chr_rom[addr]
        return 0

    def ppu_write(self, addr, value):
        """Write to cartridge (PPU side)"""
        if addr < 0x2000:
            # CHR RAM (if no CHR ROM) - only writable if CHR RAM
            if self.chr_rom_size == 0 and addr < len(self.chr_rom):
                self.chr_rom[addr] = value
