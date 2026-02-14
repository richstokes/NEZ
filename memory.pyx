# cython: boundscheck=False, wraparound=False, cdivision=True, language_level=3
"""
NES Memory Management — Cython accelerated.
Drop-in replacement for memory.py.
"""

cdef class Memory:
    def __init__(self):
        cdef int i
        for i in range(2048):
            self.ram[i] = 0

        self.cartridge = None
        self.ppu = None
        self.cpu = None
        self.apu = None
        self.nes = None

        self.bus = 0
        self.controller1 = 0
        self.controller2 = 0
        self.controller1_shift = 0
        self.controller2_shift = 0
        self.controller1_index = 0
        self.controller2_index = 0
        self.strobe = 0
        self.ppu_status_poll_count = 0
        self.low_ram_log_count = 0

    def set_cartridge(self, cartridge):
        self.cartridge = cartridge

    def set_ppu(self, ppu):
        self.ppu = ppu

    def set_cpu(self, cpu):
        self.cpu = cpu

    def set_apu(self, apu):
        self.apu = apu

    def set_nes(self, nes):
        self.nes = nes

    # ---- Hot path: CPU read ----
    cpdef int read(self, int addr):
        cdef int result
        addr = addr & 0xFFFF

        if addr < 0x2000:
            self.bus = self.ram[addr & 0x7FF]
            return self.bus
        elif addr < 0x4000:
            self.bus = self.ppu.read_register(0x2000 + (addr & 7))
            return self.bus
        elif addr == 0x4015:
            if self.apu is not None:
                self.bus = self.apu.read_status()
            return self.bus
        elif addr == 0x4016:
            if self.strobe:
                result = self.controller1 & 1
            elif self.controller1_index > 7:
                result = 1
            else:
                result = (self.controller1_shift >> self.controller1_index) & 1
                self.controller1_index += 1
            self.bus = (self.bus & 0xE0) | (result & 0x01) | 0x40
            return self.bus
        elif addr == 0x4017:
            if self.strobe:
                result = self.controller2 & 1
            elif self.controller2_index > 7:
                result = 1
            else:
                result = (self.controller2_shift >> self.controller2_index) & 1
                self.controller2_index += 1
            self.bus = (self.bus & 0xE0) | (result & 0x01) | 0x40
            return self.bus
        elif addr < 0x4020:
            return self.bus
        else:
            if self.cartridge is not None:
                self.bus = self.cartridge.cpu_read(addr)
            return self.bus

    # ---- Hot path: CPU write ----
    cpdef void write(self, int addr, int value):
        cdef int old_bus, old_strobe, start_addr, i
        cdef object ptr_data
        cdef int offset
        addr = addr & 0xFFFF
        value = value & 0xFF
        old_bus = self.bus
        self.bus = value

        if addr < 0x2000:
            self.ram[addr & 0x7FF] = value
        elif addr < 0x4000:
            self.ppu.write_register(0x2000 + (addr & 7), value)
        elif addr == 0x4014:
            start_addr = value * 0x100
            ptr_data, offset = self.get_ptr(start_addr)
            if ptr_data is not None and offset + 256 <= len(ptr_data):
                for i in range(256):
                    self.ppu.oam[i] = ptr_data[offset + i]
                self.bus = ptr_data[offset + 255]
            else:
                for i in range(256):
                    self.ppu.oam[i] = self.read(start_addr + i)
            if hasattr(self.cpu, "add_dma_cycles"):
                self.cpu.add_dma_cycles(513)
        elif addr == 0x4016:
            old_strobe = self.strobe
            self.strobe = value & 1
            if old_strobe and not self.strobe:
                self.controller1_shift = self.controller1
                self.controller2_shift = self.controller2
                self.controller1_index = 0
                self.controller2_index = 0
            self.bus = (old_bus & 0xE0) | (value & 0x1F)
        elif 0x4000 <= addr <= 0x4017:
            if self.apu is not None:
                self.apu.write_register(addr, value)
        elif addr < 0x4020:
            pass
        else:
            if self.cartridge is not None:
                self.cartridge.cpu_write(addr, value)

    # ---- Hot path: PPU read (pattern tables via cartridge) ----
    cpdef int ppu_read(self, int addr):
        if addr < 0x2000 and self.cartridge is not None:
            return self.cartridge.ppu_read(addr)
        return 0

    # ---- PPU write ----
    cpdef void ppu_write(self, int addr, int value):
        if self.cartridge is not None:
            self.cartridge.ppu_write(addr, value)

    # ---- Controller state ----
    def set_controller_state(self, int controller, int buttons):
        if controller == 1:
            self.controller1 = buttons
        elif controller == 2:
            self.controller2 = buttons

    # ---- DMA helper ----
    def get_ptr(self, int addr):
        cdef int base, i
        cdef list ram_copy
        if addr < 0x2000:
            base = addr & 0x7FF
            ram_copy = [0] * 256
            for i in range(256):
                ram_copy[i] = self.ram[(base + i) & 0x7FF]
            return ram_copy, 0
        elif 0x6000 <= addr < 0x8000 and self.cartridge is not None and self.cartridge.prg_ram:
            return self.cartridge.prg_ram, addr - 0x6000
        return None, 0


class Cartridge:
    """NES Cartridge (ROM) loader and mapper"""

    def __init__(self, rom_path):
        self.rom_path = rom_path
        self.prg_rom = []
        self.chr_rom = []
        self.prg_ram = [0] * 0x2000

        self.prg_rom_size = 0
        self.chr_rom_size = 0
        self.mapper = 0
        self.mirroring = 0
        self.has_battery = False
        self.has_trainer = False
        self.four_screen = False
        self.region = 'NTSC'
        self.name_table_map = [0, 0, 0, 0]
        self.mapper_obj = None
        self.memory = None

        self.load_rom()
        self.set_mirroring()
        self.init_mapper()

    def init_mapper(self):
        m = self.mapper
        if m == 0:
            self.mapper_obj = Mapper0(self)
        elif m == 1:
            self.mapper_obj = Mapper1(self)
        elif m == 4:
            self.mapper_obj = Mapper4(self)
        else:
            self.mapper_obj = Mapper0(self)

    def set_spec_mirroring(self, mode):
        if mode == 'vertical':
            self.name_table_map = [0, 0x400, 0, 0x400]
        elif mode == 'horizontal':
            self.name_table_map = [0, 0, 0x400, 0x400]
        elif mode == 'onescreen_low':
            self.name_table_map = [0, 0, 0, 0]
        elif mode == 'onescreen_high':
            self.name_table_map = [0x400, 0x400, 0x400, 0x400]
        else:
            if self.four_screen:
                self.name_table_map = [0, 0x400, 0, 0x400]
            else:
                self.name_table_map = [0, 0, 0x400, 0x400]

    def set_mirroring(self):
        if self.mirroring == 1:
            self.name_table_map = [0, 0x400, 0, 0x400]
        else:
            self.name_table_map = [0, 0, 0x400, 0x400]

    def load_rom(self):
        with open(self.rom_path, "rb") as f:
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

            if (flags7 & 0x0C) == 0x08:
                self.region = 'NTSC'
            else:
                current_pos = f.tell()
                f.seek(0)
                full_header = f.read(16)
                f.seek(current_pos)
                if len(full_header) > 9:
                    if full_header[9] & 1:
                        self.region = 'PAL'
                    else:
                        self.region = 'NTSC'
                else:
                    self.region = 'NTSC'

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

            if self.has_trainer:
                f.read(512)

            prg_size = self.prg_rom_size * 16384
            self.prg_rom = list(f.read(prg_size))

            if self.chr_rom_size > 0:
                chr_size = self.chr_rom_size * 8192
                print(f"Reading CHR ROM: {chr_size} bytes from file position {f.tell()}")
                chr_data = f.read(chr_size)
                print(f"Actually read: {len(chr_data)} bytes")
                self.chr_rom = list(chr_data)
                if len(self.chr_rom) >= 16:
                    print(f"First 16 CHR ROM bytes: {[hex(x) for x in self.chr_rom[:16]]}")
                tile_36_start = 36 * 16
                if len(self.chr_rom) > tile_36_start + 16:
                    print(f"Tile 36 CHR data (0x{tile_36_start:03X}-0x{tile_36_start+15:03X}): {[hex(x) for x in self.chr_rom[tile_36_start:tile_36_start+16]]}")
            else:
                self.chr_rom = [0] * 8192

        print(f"Loaded ROM: {self.rom_path}")
        print(f"PRG ROM: {self.prg_rom_size * 16}KB")
        print(f"CHR ROM: {self.chr_rom_size * 8}KB")
        print(f"Mapper: {self.mapper}")
        print(f"Mirroring: {'Vertical' if self.mirroring else 'Horizontal'}")
        print(f"Region: {self.region}")

    def cpu_read(self, addr):
        return self.mapper_obj.cpu_read(addr)

    def cpu_write(self, addr, value):
        self.mapper_obj.cpu_write(addr, value)

    def ppu_read(self, addr):
        return self.mapper_obj.ppu_read(addr)

    def ppu_write(self, addr, value):
        self.mapper_obj.ppu_write(addr, value)


# ---- Mapper implementations (kept as regular classes for now) ----

class Mapper:
    def __init__(self, cart):
        self.cart = cart

    def cpu_read(self, addr):
        return 0
    def cpu_write(self, addr, value):
        pass
    def ppu_read(self, addr):
        return 0
    def ppu_write(self, addr, value):
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

    def ppu_read(self, addr):
        if addr < 0x2000:
            size = len(self.chr)
            if size == 0:
                return 0
            if (size & (size - 1)) == 0:
                return self.chr[addr & (size - 1)]
            return self.chr[addr % size]
        return 0

    def ppu_write(self, addr, value):
        if addr < 0x2000 and self.cart.chr_rom_size == 0:
            if addr < len(self.chr):
                self.chr[addr] = value


class Mapper1(Mapper):
    """MMC1"""
    def __init__(self, cart):
        super().__init__(cart)
        self.shift_reg = 0x10
        self.control = 0x0C
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
        if value & 0x80:
            self.shift_reg = 0x10
            self.control |= 0x0C
            self.update_mirroring()
            return
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
            if prg_mode in (0, 1):
                base = (bank_16k & 0xFE) * 0x4000
                return self.cart.prg_rom[(base + (addr - 0x8000)) % prg_size]
            elif prg_mode == 2:
                if addr < 0xC000:
                    return self.cart.prg_rom[addr - 0x8000]
                else:
                    base = bank_16k * 0x4000
                    return self.cart.prg_rom[(base + (addr - 0xC000)) % prg_size]
            else:
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
            if chr_mode == 0:
                bank = (self.chr_bank0 & 0x1E) * 0x1000
                return self.cart.chr_rom[(bank + addr) % chr_size]
            else:
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
    """MMC3"""
    def __init__(self, cart):
        super().__init__(cart)
        self.bank_select = 0
        self.bank_regs = [0] * 8
        self.prg_mode = 0
        self.chr_mode = 0
        self.irq_latch = 0
        self.irq_counter = 0
        self.irq_reload = False
        self.irq_enabled = False
        self.prev_a12 = 0
        self.last_a12_cycle = 0
        self.update_prg_banks()

    def update_prg_banks(self):
        prg_size = len(self.cart.prg_rom)
        if prg_size == 0:
            self.prg_map = [0, 0, 0, 0]
            return
        bank_count = prg_size // 0x2000
        last_bank = bank_count - 1
        second_last_bank = bank_count - 2
        b6 = self.bank_regs[6] % bank_count
        b7 = self.bank_regs[7] % bank_count
        if self.prg_mode == 0:
            self.prg_map = [b6, b7, second_last_bank, last_bank]
        else:
            self.prg_map = [second_last_bank, b7, b6, last_bank]

    def update_chr_banks(self):
        chr_size = len(self.cart.chr_rom)
        if chr_size == 0:
            self.chr_map = [0] * 8
            return
        regs = self.bank_regs
        if self.chr_mode == 0:
            r0 = regs[0] & 0xFE; r1 = regs[1] & 0xFE
            self.chr_map = [r0, r0+1, r1, r1+1, regs[2], regs[3], regs[4], regs[5]]
        else:
            r0 = regs[0] & 0xFE; r1 = regs[1] & 0xFE
            self.chr_map = [regs[2], regs[3], regs[4], regs[5], r0, r0+1, r1, r1+1]
        pages = chr_size // 0x400
        if pages == 0:
            pages = 1
        for i in range(8):
            self.chr_map[i] %= pages

    def clock_irq(self):
        if self.irq_counter == 0 or self.irq_reload:
            self.irq_counter = self.irq_latch if self.irq_latch != 0 else 0x100
            self.irq_reload = False
        else:
            self.irq_counter -= 1
        if self.irq_counter == 0 and self.irq_enabled:
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
            self.cart.prg_ram[addr - 0x6000] = value
            return
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
                    self.update_prg_banks()
                    self.update_chr_banks()
            elif 0xA000 <= addr <= 0xBFFF:
                if even:
                    if value & 1:
                        self.cart.set_spec_mirroring('horizontal')
                    else:
                        self.cart.set_spec_mirroring('vertical')
            elif 0xC000 <= addr <= 0xDFFF:
                if even:
                    self.irq_latch = value
                else:
                    self.irq_reload = True
            elif 0xE000 <= addr <= 0xFFFF:
                if even:
                    self.irq_enabled = False
                else:
                    self.irq_enabled = True

    def ppu_read(self, addr):
        if addr < 0x2000:
            chr_size = len(self.cart.chr_rom)
            if chr_size == 0:
                return 0
            if not hasattr(self, 'chr_map'):
                self.update_chr_banks()
            bank = self.chr_map[(addr // 0x400) & 7]
            base = bank * 0x400
            value = self.cart.chr_rom[(base + (addr & 0x3FF)) % chr_size]
            a12 = (addr >> 12) & 1
            if self.prev_a12 == 0 and a12 == 1:
                mem = getattr(self.cart, 'memory', None)
                cpu_cycles = getattr(mem.nes.cpu, 'total_cycles', 0) if mem and hasattr(mem, 'nes') else 0
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
