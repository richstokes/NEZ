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

        # Targeted low-RAM write logging (e.g., $0700-$07FF)
        self.low_ram_log_count = 0

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
        # Instrumentation counters
        self.ppu_status_poll_count = 0  # $2002 polling detection early frames

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
            # APU status
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
            self.bus = (self.bus & 0xE0) | (result & 0x01) | 0x40
            return self.bus
        elif addr == 0x4017:
            # APU Frame Counter (write-only) / Controller 2
            # Most tests expect this to return open bus, not controller data
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
            # OAM DMA - sprite data transfer
            start_addr = value * 0x100
            ptr_data, offset = self.get_ptr(start_addr)
            if ptr_data is not None and offset + 256 <= len(ptr_data):
                # Fast path - direct memory copy
                for i in range(256):
                    self.ppu.oam[i] = ptr_data[offset + i]
                self.bus = ptr_data[offset + 255]
            else:
                # Slow path - use memory reads (handles bank switching)
                for i in range(256):
                    self.ppu.oam[i] = self.read(start_addr + i)

            # DMA takes 513 CPU cycles (hardware-accurate)
            if hasattr(self.cpu, "add_dma_cycles"):
                self.cpu.add_dma_cycles(513)
        elif addr == 0x4016:
            # Controller strobe register - controls both controllers
            old_strobe = self.strobe
            self.strobe = value & 1
            # When strobe goes from high to low, latch the current state
            if old_strobe and not self.strobe:
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
        self.mapper = 0  # Mapper number (numeric id)
        self.mirroring = 0  # 0=horizontal, 1=vertical
        self.has_battery = False
        self.has_trainer = False
        self.four_screen = False
        self.region = 'NTSC'  # Default region, will be detected from ROM

        # Nametable mapping for mirroring like reference implementation
        # Maps nametable index to VRAM offset
        self.name_table_map = [0, 0, 0, 0]  # Will be set based on mirroring

        self.mapper_obj = None  # Concrete mapper implementation

        self.load_rom()
        self.set_mirroring()  # Initial nametable mapping
        self.init_mapper()    # Instantiate mapper implementation

    # ------------------------ Mapper Helpers ------------------------
    def init_mapper(self):
        """Instantiate mapper object based on mapper id"""
        m = self.mapper
        if m == 0:
            self.mapper_obj = Mapper0(self)
        elif m == 1:
            self.mapper_obj = Mapper1(self)
        elif m == 4:
            self.mapper_obj = Mapper4(self)
        else:
            # Fallback to basic ROM access with NROM-like behaviour
            self.mapper_obj = Mapper0(self)

    def set_spec_mirroring(self, mode):
        """Set mirroring according to specified mode string
        mode: 'horizontal','vertical','onescreen_low','onescreen_high','four'
        """
        if mode == 'vertical':
            self.name_table_map = [0, 0x400, 0, 0x400]
        elif mode == 'horizontal':
            self.name_table_map = [0, 0, 0x400, 0x400]
        elif mode == 'onescreen_low':
            self.name_table_map = [0, 0, 0, 0]
        elif mode == 'onescreen_high':
            self.name_table_map = [0x400, 0x400, 0x400, 0x400]
        else:  # four-screen or unknown -> default to vertical if four-screen bit set, else horizontal
            if self.four_screen:
                # We do not allocate extra VRAM pages yet, approximate with vertical
                self.name_table_map = [0, 0x400, 0, 0x400]
            else:
                self.name_table_map = [0, 0, 0x400, 0x400]

    # ------------------------ Existing Mirroring ------------------------

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
            
            # Region detection
            # Check if this is NES 2.0 format
            if (flags7 & 0x0C) == 0x08:
                # NES 2.0 - would need to read byte 12 for region
                # For now, default to NTSC
                self.region = 'NTSC'
            else:
                # iNES 1.0 - check byte 9 for PAL flag if available
                # We need to read more header bytes for this
                current_pos = f.tell()
                f.seek(0)  # Go back to start
                full_header = f.read(16)
                f.seek(current_pos)  # Return to original position
                
                if len(full_header) > 9:
                    # Byte 9, bit 0: 0=NTSC, 1=PAL
                    if full_header[9] & 1:
                        self.region = 'PAL'
                    else:
                        self.region = 'NTSC'
                else:
                    self.region = 'NTSC'
            
            # Fallback: Check filename for region indicators
            rom_name = self.rom_path.upper()
            if ('(E)' in rom_name or '(EUROPE)' in rom_name or 
                '(PAL)' in rom_name or '(EU)' in rom_name or
                '(GERMANY)' in rom_name or '(FRANCE)' in rom_name or
                '(SPAIN)' in rom_name or '(ITALY)' in rom_name or
                '(AUSTRALIA)' in rom_name):
                self.region = 'PAL'
            elif '(U)' in rom_name or '(USA)' in rom_name or '(US)' in rom_name:
                self.region = 'NTSC'
            elif '(J)' in rom_name or '(JAPAN)' in rom_name or '(JPN)' in rom_name:
                self.region = 'NTSC'

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
        print(f"Region: {self.region}")
        # (Removed verbose one-off debug dumping of CHR range 0x1240–0x124F.)
        # If you need to inspect CHR contents, add an ad‑hoc tool/script instead of
        # hard‑coding address ranges here.

    def cpu_read(self, addr):
        """Read from cartridge (CPU side)"""
        return self.mapper_obj.cpu_read(addr)

    def cpu_write(self, addr, value):
        """Write to cartridge (CPU side)"""
        self.mapper_obj.cpu_write(addr, value)

    def ppu_read(self, addr):
        """Read from cartridge (PPU side)"""
        return self.mapper_obj.ppu_read(addr)

    def ppu_write(self, addr, value):
        """Write to cartridge (PPU side)"""
        self.mapper_obj.ppu_write(addr, value)

# ------------------------ Mapper Implementations ------------------------

class Mapper:
    def __init__(self, cart: 'Cartridge'):
        self.cart = cart

    # CPU
    def cpu_read(self, addr: int) -> int:
        return 0
    def cpu_write(self, addr: int, value: int):
        pass
    # PPU
    def ppu_read(self, addr: int) -> int:
        return 0
    def ppu_write(self, addr: int, value: int):
        pass


class Mapper0(Mapper):
    """NROM"""
    def __init__(self, cart):
        super().__init__(cart)
        self.prg_rom = cart.prg_rom
        self.chr = cart.chr_rom

    def cpu_read(self, addr):
        if addr < 0x6000:
            return 0
        if 0x6000 <= addr <= 0x7FFF:
            return self.cart.prg_ram[addr - 0x6000]
        if addr >= 0x8000:
            if self.cart.prg_rom_size == 1:
                return self.prg_rom[(addr - 0x8000) & 0x3FFF]
            return self.prg_rom[addr - 0x8000]
        return 0

    def cpu_write(self, addr, value):
        if 0x6000 <= addr <= 0x7FFF:
            self.cart.prg_ram[addr - 0x6000] = value
        # No mapper registers

    def ppu_read(self, addr):
        if addr < 0x2000:
            size = len(self.chr)
            if size == 0:
                return 0
            # Mirror power-of-two size
            if (size & (size - 1)) == 0:
                return self.chr[addr & (size - 1)]
            return self.chr[addr % size]
        return 0

    def ppu_write(self, addr, value):
        if addr < 0x2000 and self.cart.chr_rom_size == 0:
            if addr < len(self.chr):
                self.chr[addr] = value


class Mapper1(Mapper):
    """MMC1 - Implements shift register logic (no SRAM protect variations)"""
    def __init__(self, cart):
        super().__init__(cart)
        self.shift_reg = 0x10  # bit4 set indicates empty
        self.control = 0x0C    # default after reset (16KB switch, vertical)
        self.chr_bank0 = 0
        self.chr_bank1 = 0
        self.prg_bank = 0
        self.update_mirroring()

    def update_mirroring(self):
        mirr_mode = self.control & 0x03
        if mirr_mode == 0:
            self.cart.set_spec_mirroring('onescreen_low')
        elif mirr_mode == 1:
            self.cart.set_spec_mirroring('onescreen_high')
        elif mirr_mode == 2:
            self.cart.set_spec_mirroring('vertical')
        else:
            self.cart.set_spec_mirroring('horizontal')

    def write_register(self, addr, value):
        # Reset if bit7 set
        if value & 0x80:
            self.shift_reg = 0x10
            self.control |= 0x0C
            self.update_mirroring()
            return
        # Shift in bit (LSB first)
        carry = value & 1
        complete = (self.shift_reg & 1) == 1
        self.shift_reg >>= 1
        self.shift_reg |= (carry << 4)
        if complete:
            reg_val = self.shift_reg & 0x1F
            if 0x8000 <= addr <= 0x9FFF:
                self.control = reg_val
                self.update_mirroring()
            elif 0xA000 <= addr <= 0xBFFF:
                self.chr_bank0 = reg_val
            elif 0xC000 <= addr <= 0xDFFF:
                self.chr_bank1 = reg_val
            elif 0xE000 <= addr <= 0xFFFF:
                self.prg_bank = reg_val & 0x0F
            self.shift_reg = 0x10

    def cpu_read(self, addr):
        if addr < 0x6000:
            return 0
        if 0x6000 <= addr <= 0x7FFF:
            return self.cart.prg_ram[addr - 0x6000]
        if addr >= 0x8000:
            prg_mode = (self.control >> 2) & 0x03
            prg_size = len(self.cart.prg_rom)
            bank_16k = self.prg_bank % max(1, self.cart.prg_rom_size * 2)
            if prg_mode in (0,1):  # 32KB switch (ignore low bit)
                base = (bank_16k & 0xFE) * 0x4000
                return self.cart.prg_rom[(base + (addr - 0x8000)) % prg_size]
            elif prg_mode == 2:  # Fix first bank at $8000, switch at $C000
                if addr < 0xC000:
                    return self.cart.prg_rom[addr - 0x8000]
                else:
                    base = bank_16k * 0x4000
                    return self.cart.prg_rom[(base + (addr - 0xC000)) % prg_size]
            else:  # prg_mode == 3: switch at $8000, fix last bank at $C000
                if addr < 0xC000:
                    base = bank_16k * 0x4000
                    return self.cart.prg_rom[(base + (addr - 0x8000)) % prg_size]
                else:
                    base = (self.cart.prg_rom_size - 1) * 0x4000
                    return self.cart.prg_rom[(base + (addr - 0xC000)) % prg_size]
        return 0

    def cpu_write(self, addr, value):
        if 0x6000 <= addr <= 0x7FFF:
            self.cart.prg_ram[addr - 0x6000] = value
        elif addr >= 0x8000:
            self.write_register(addr, value)

    def ppu_read(self, addr):
        if addr < 0x2000:
            chr_mode = (self.control >> 4) & 1
            chr_size = len(self.cart.chr_rom)
            if chr_size == 0:
                return 0
            if chr_mode == 0:  # 8KB
                bank = (self.chr_bank0 & 0x1E) * 0x1000
                return self.cart.chr_rom[(bank + addr) % chr_size]
            else:  # 4KB + 4KB
                if addr < 0x1000:
                    bank = self.chr_bank0 * 0x1000
                    return self.cart.chr_rom[(bank + addr) % chr_size]
                else:
                    bank = self.chr_bank1 * 0x1000
                    return self.cart.chr_rom[(bank + (addr - 0x1000)) % chr_size]
        return 0

    def ppu_write(self, addr, value):
        if addr < 0x2000 and self.cart.chr_rom_size == 0:
            if addr < len(self.cart.chr_rom):
                self.cart.chr_rom[addr] = value


class Mapper4(Mapper):
    """MMC3 with PRG/CHR banking, mirroring, and IRQ counter"""
    def __init__(self, cart):
        super().__init__(cart)
        self.bank_select = 0
        self.bank_regs = [0]*8  # 0-5 CHR, 6-7 PRG
        self.prg_mode = 0
        self.chr_mode = 0
        # IRQ related
        self.irq_latch = 0
        self.irq_counter = 0
        self.irq_reload = False
        self.irq_enabled = False
        self.prev_a12 = 0
        self.last_a12_cycle = 0  # CPU cycle timestamp to filter rapid toggles
        self.update_prg_banks()

    def update_prg_banks(self):
        prg_size = len(self.cart.prg_rom)
        if prg_size == 0:
            self.prg_map = [0,0,0,0]
            return
        bank_count = prg_size // 0x2000  # 8KB banks
        last_bank = bank_count - 1
        second_last_bank = bank_count - 2
        b6 = self.bank_regs[6] % bank_count
        b7 = self.bank_regs[7] % bank_count
        if self.prg_mode == 0:
            self.prg_map = [b6, b7, second_last_bank, last_bank]
        else:
            self.prg_map = [second_last_bank, b7, b6, last_bank]

    def update_chr_banks(self):
        # We'll map 1KB pages directly (simplified).
        chr_size = len(self.cart.chr_rom)
        if chr_size == 0:
            self.chr_map = [0]*8
            return
        regs = self.bank_regs
        if self.chr_mode == 0:
            r0 = regs[0] & 0xFE; r1 = regs[1] & 0xFE
            self.chr_map = [r0, r0+1, r1, r1+1, regs[2], regs[3], regs[4], regs[5]]
        else:
            r0 = regs[0] & 0xFE; r1 = regs[1] & 0xFE
            self.chr_map = [regs[2], regs[3], regs[4], regs[5], r0, r0+1, r1, r1+1]
        pages = chr_size // 0x400
        if pages == 0: pages = 1
        for i in range(8):
            self.chr_map[i] %= pages

    def clock_irq(self):
        """Clock MMC3 IRQ counter on valid A12 rising edge during rendering."""
        # When counter is zero OR reload flag set, reload from latch then decrement to 0
        if self.irq_counter == 0 or self.irq_reload:
            self.irq_counter = self.irq_latch if self.irq_latch != 0 else 0x100
            self.irq_reload = False
        else:
            self.irq_counter -= 1
        # Trigger IRQ when counter hits zero after decrement
        if self.irq_counter == 0 and self.irq_enabled:
            # Trigger CPU IRQ
            mem = getattr(self.cart, 'memory', None)
            if mem and hasattr(mem, 'nes') and hasattr(mem.nes, 'cpu') and hasattr(mem.nes.cpu, 'trigger_interrupt'):
                mem.nes.cpu.trigger_interrupt('IRQ')

    def cpu_read(self, addr):
        if addr < 0x6000:
            return 0
        if 0x6000 <= addr <= 0x7FFF:
            return self.cart.prg_ram[addr - 0x6000]
        if addr >= 0x8000:
            bank_slot = (addr - 0x8000) // 0x2000
            offset = addr & 0x1FFF
            if bank_slot < 4:
                bank_index = self.prg_map[bank_slot]
                base = bank_index * 0x2000
                prg_size = len(self.cart.prg_rom)
                if prg_size:
                    return self.cart.prg_rom[(base + offset) % prg_size]
        return 0

    def cpu_write(self, addr, value):
        if 0x6000 <= addr <= 0x7FFF:
            self.cart.prg_ram[addr - 0x6000] = value; return
        if addr >= 0x8000:
            even = (addr & 1) == 0
            if 0x8000 <= addr <= 0x9FFF:
                if even:
                    self.bank_select = value
                    self.chr_mode = (value >> 7) & 1
                    self.prg_mode = (value >> 6) & 1
                else:
                    reg_index = self.bank_select & 0x07
                    self.bank_regs[reg_index] = value
                    if reg_index >=6:
                        self.update_prg_banks()
                    else:
                        self.update_chr_banks()
                    self.update_prg_banks(); self.update_chr_banks()
            elif 0xA000 <= addr <= 0xBFFF:
                if even:
                    if value & 1:
                        self.cart.set_spec_mirroring('horizontal')
                    else:
                        self.cart.set_spec_mirroring('vertical')
                else:
                    pass  # PRG RAM protect ignored
            elif 0xC000 <= addr <= 0xDFFF:
                if even:
                    # $C000 even: IRQ latch
                    self.irq_latch = value
                else:
                    # $C001 odd: IRQ reload
                    self.irq_reload = True
                # No immediate counter decrement here; occurs on next A12 rise
            elif 0xE000 <= addr <= 0xFFFF:
                if even:
                    # $E000 even: IRQ disable + acknowledge
                    self.irq_enabled = False
                    # Acknowledge pending IRQ by clearing any CPU pending flag is left to CPU status read ($4015) or explicit design; do nothing else
                else:
                    # $E001 odd: IRQ enable
                    self.irq_enabled = True

    def ppu_read(self, addr):
        # CHR fetch with A12 edge detection
        if addr < 0x2000:
            chr_size = len(self.cart.chr_rom)
            if chr_size == 0:
                return 0
            if not hasattr(self, 'chr_map'):
                self.update_chr_banks()
            bank = self.chr_map[(addr // 0x400) & 7]
            base = bank * 0x400
            value = self.cart.chr_rom[(base + (addr & 0x3FF)) % chr_size]
            # Detect rising edge of A12 (bit 12 of PPU address) with 2 PPU cycle minimum spacing
            a12 = (addr >> 12) & 1
            if self.prev_a12 == 0 and a12 == 1:
                # Use CPU cycle count as time reference
                mem = getattr(self.cart, 'memory', None)
                cpu_cycles = getattr(mem.nes.cpu, 'total_cycles', 0) if mem and hasattr(mem, 'nes') else 0
                # MMC3 spec: ignore rapid toggles (< 8 PPU cycles ~ < 3 CPU cycles). We'll use >= 3 CPU cycles filter
                if cpu_cycles - self.last_a12_cycle >= 3:
                    self.clock_irq()
                    self.last_a12_cycle = cpu_cycles
            self.prev_a12 = a12
            return value
        return 0

    def ppu_write(self, addr, value):
        if addr < 0x2000 and self.cart.chr_rom_size == 0:
            if not hasattr(self, 'chr_map'):
                self.update_chr_banks()
            bank = self.chr_map[(addr // 0x400) & 7]
            base = bank * 0x400
            chr_size = len(self.cart.chr_rom)
            target = (base + (addr & 0x3FF)) % chr_size
            self.cart.chr_rom[target] = value
