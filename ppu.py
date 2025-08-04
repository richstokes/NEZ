"""
NES PPU (Picture Processing Unit) Emulator
Handles graphics rendering for the NES
"""


class PPU:
    def __init__(self, memory):
        self.memory = memory

        # PPU Registers
        self.ctrl = 0  # $2000 - PPUCTRL
        self.mask = 0  # $2001 - PPUMASK
        self.status = 0  # $2002 - PPUSTATUS
        self.oam_addr = 0  # $2003 - OAMADDR
        self.oam_data = 0  # $2004 - OAMDATA
        self.scroll = 0  # $2005 - PPUSCROLL
        self.addr = 0  # $2006 - PPUADDR
        self.data = 0  # $2007 - PPUDATA

        # Internal registers
        self.v = 0  # Current VRAM address (15 bits)
        self.t = 0  # Temporary VRAM address (15 bits)
        self.x = 0  # Fine X scroll (3 bits)
        self.w = 0  # Write toggle (1 bit)

        # PPU Memory
        self.vram = [0] * 0x4000  # Pattern tables, name tables, etc.
        self.palette_ram = [0] * 0x20  # Palette memory
        self.oam = [0] * 0x100  # Object Attribute Memory (sprites)

        # Rendering state
        self.scanline = 0
        self.cycle = 0
        self.frame = 0
        self.odd_frame = False

        # Background rendering
        self.nt_byte = 0  # Name table byte
        self.at_byte = 0  # Attribute table byte
        self.bg_low_byte = 0  # Background pattern low byte
        self.bg_high_byte = 0  # Background pattern high byte

        # Shift registers for background
        self.bg_shift_pattern_low = 0
        self.bg_shift_pattern_high = 0
        self.bg_shift_attrib_low = 0
        self.bg_shift_attrib_high = 0

        # Sprite rendering
        self.sprite_count = 0
        self.sprite_patterns = [0] * 8
        self.sprite_positions = [0] * 8
        self.sprite_priorities = [0] * 8
        self.sprite_indices = [0] * 8

        # Flags
        self.sprite_zero_hit = False
        self.sprite_overflow = False

        # Output buffer (256x240 pixels, RGB values)
        self.screen = [[[0, 0, 0] for _ in range(256)] for _ in range(240)]

        # NES color palette (RGB values)
        self.palette = [
            [84, 84, 84],
            [0, 30, 116],
            [8, 16, 144],
            [48, 0, 136],
            [68, 0, 100],
            [92, 0, 48],
            [84, 4, 0],
            [60, 24, 0],
            [32, 42, 0],
            [8, 58, 0],
            [0, 64, 0],
            [0, 60, 0],
            [0, 50, 60],
            [0, 0, 0],
            [0, 0, 0],
            [0, 0, 0],
            [152, 150, 152],
            [8, 76, 196],
            [48, 50, 236],
            [92, 30, 228],
            [136, 20, 176],
            [160, 20, 100],
            [152, 34, 32],
            [120, 60, 0],
            [84, 90, 0],
            [40, 114, 0],
            [8, 124, 0],
            [0, 118, 40],
            [0, 102, 120],
            [0, 0, 0],
            [0, 0, 0],
            [0, 0, 0],
            [236, 238, 236],
            [76, 154, 236],
            [120, 124, 236],
            [176, 98, 236],
            [228, 84, 236],
            [236, 88, 180],
            [236, 106, 100],
            [212, 136, 32],
            [160, 170, 0],
            [116, 196, 0],
            [76, 208, 32],
            [56, 204, 108],
            [56, 180, 204],
            [60, 60, 60],
            [0, 0, 0],
            [0, 0, 0],
            [236, 238, 236],
            [168, 204, 236],
            [188, 188, 236],
            [212, 178, 236],
            [236, 174, 236],
            [236, 174, 212],
            [236, 180, 176],
            [228, 196, 144],
            [204, 210, 120],
            [180, 222, 120],
            [168, 226, 144],
            [152, 226, 180],
            [160, 214, 228],
            [160, 162, 160],
            [0, 0, 0],
            [0, 0, 0],
        ]

        self.buffer = 0  # PPU data buffer

    def reset(self):
        """Reset PPU to initial state"""
        self.ctrl = 0
        self.mask = 0
        self.status = 0xA0  # VBlank flag set
        self.oam_addr = 0
        self.v = 0
        self.t = 0
        self.x = 0
        self.w = 0
        self.scanline = 0
        self.cycle = 0
        self.frame = 0
        self.odd_frame = False

        # Clear memory
        self.vram = [0] * 0x4000
        self.palette_ram = [0] * 0x20
        self.oam = [0] * 0x100

        self.buffer = 0

    def read_register(self, addr):
        """Read from PPU register"""
        if addr == 0x2002:  # PPUSTATUS
            result = self.status
            self.status &= 0x7F  # Clear VBlank flag
            self.w = 0  # Reset write toggle
            return result
        elif addr == 0x2004:  # OAMDATA
            return self.oam[self.oam_addr]
        elif addr == 0x2007:  # PPUDATA
            result = self.buffer
            if self.v < 0x3F00:
                self.buffer = self.read_vram(self.v)
            else:
                self.buffer = self.read_vram(self.v - 0x1000)
                result = self.read_vram(self.v)

            # Increment VRAM address
            if self.ctrl & 0x04:
                self.v = (self.v + 32) & 0x7FFF
            else:
                self.v = (self.v + 1) & 0x7FFF

            return result
        return 0

    def write_register(self, addr, value):
        """Write to PPU register"""
        if addr == 0x2000:  # PPUCTRL
            self.ctrl = value
            self.t = (self.t & 0xF3FF) | ((value & 0x03) << 10)
        elif addr == 0x2001:  # PPUMASK
            self.mask = value
        elif addr == 0x2003:  # OAMADDR
            self.oam_addr = value
        elif addr == 0x2004:  # OAMDATA
            self.oam[self.oam_addr] = value
            self.oam_addr = (self.oam_addr + 1) & 0xFF
        elif addr == 0x2005:  # PPUSCROLL
            if self.w == 0:
                self.t = (self.t & 0xFFE0) | (value >> 3)
                self.x = value & 0x07
                self.w = 1
            else:
                self.t = (self.t & 0x8FFF) | ((value & 0x07) << 12)
                self.t = (self.t & 0xFC1F) | ((value & 0xF8) << 2)
                self.w = 0
        elif addr == 0x2006:  # PPUADDR
            if self.w == 0:
                self.t = (self.t & 0x80FF) | ((value & 0x3F) << 8)
                self.w = 1
            else:
                self.t = (self.t & 0xFF00) | value
                self.v = self.t
                self.w = 0
        elif addr == 0x2007:  # PPUDATA
            self.write_vram(self.v, value)

            # Increment VRAM address
            if self.ctrl & 0x04:
                self.v = (self.v + 32) & 0x7FFF
            else:
                self.v = (self.v + 1) & 0x7FFF

    def read_vram(self, addr):
        """Read from PPU VRAM"""
        addr = addr & 0x3FFF

        if addr < 0x2000:
            # Pattern tables - handled by cartridge
            return self.memory.ppu_read(addr)
        elif addr < 0x3F00:
            # Name tables
            return self.vram[addr]
        else:
            # Palette RAM
            addr = addr & 0x1F
            if addr == 0x10:
                addr = 0x00
            elif addr == 0x14:
                addr = 0x04
            elif addr == 0x18:
                addr = 0x08
            elif addr == 0x1C:
                addr = 0x0C
            return self.palette_ram[addr]

    def write_vram(self, addr, value):
        """Write to PPU VRAM"""
        addr = addr & 0x3FFF

        if addr < 0x2000:
            # Pattern tables - handled by cartridge
            self.memory.ppu_write(addr, value)
        elif addr < 0x3F00:
            # Name tables
            self.vram[addr] = value
        else:
            # Palette RAM
            addr = addr & 0x1F
            if addr == 0x10:
                addr = 0x00
            elif addr == 0x14:
                addr = 0x04
            elif addr == 0x18:
                addr = 0x08
            elif addr == 0x1C:
                addr = 0x0C
            self.palette_ram[addr] = value

    def step(self):
        """Execute one PPU cycle"""
        # Pre-render scanline
        if self.scanline == 261:
            if self.cycle == 1:
                self.status &= 0x9F  # Clear VBlank and sprite 0 hit
                self.sprite_zero_hit = False
                self.sprite_overflow = False

            if self.cycle == 339 and self.odd_frame and (self.mask & 0x18):
                self.cycle = 0
                self.scanline = 0
                self.frame += 1
                self.odd_frame = not self.odd_frame
                return

        # Visible scanlines
        elif 0 <= self.scanline <= 239:
            if self.cycle == 0:
                pass  # Idle cycle
            elif 1 <= self.cycle <= 256:
                self.render_pixel()
                if self.cycle == 256:
                    self.increment_y()
            elif self.cycle == 257:
                self.copy_x()
            elif 321 <= self.cycle <= 336:
                self.fetch_tile_data()

        # Post-render scanline
        elif self.scanline == 240:
            pass  # Do nothing

        # VBlank scanlines
        elif 241 <= self.scanline <= 260:
            if self.scanline == 241 and self.cycle == 1:
                self.status |= 0x80  # Set VBlank flag
                if self.ctrl & 0x80:  # NMI enabled
                    self.memory.cpu.nmi = True

        # Increment cycle and scanline
        self.cycle += 1
        if self.cycle > 340:
            self.cycle = 0
            self.scanline += 1
            if self.scanline > 261:
                self.scanline = 0
                self.frame += 1
                self.odd_frame = not self.odd_frame

    def render_pixel(self):
        """Render a single pixel"""
        x = self.cycle - 1
        y = self.scanline

        if x >= 256 or y >= 240:
            return

        # Get background pixel
        bg_pixel = 0
        bg_palette = 0

        if self.mask & 0x08:  # Background rendering enabled
            if x >= 8 or (self.mask & 0x02):  # Show background in leftmost 8 pixels
                shift = 15 - self.x
                bg_pixel = ((self.bg_shift_pattern_high >> shift) & 1) << 1 | (
                    (self.bg_shift_pattern_low >> shift) & 1
                )
                bg_palette = ((self.bg_shift_attrib_high >> shift) & 1) << 1 | (
                    (self.bg_shift_attrib_low >> shift) & 1
                )

        # Get sprite pixel
        sprite_pixel = 0
        sprite_palette = 0
        sprite_priority = 0
        sprite_zero = False

        if self.mask & 0x10:  # Sprite rendering enabled
            for i in range(self.sprite_count):
                offset = x - self.sprite_positions[i]
                if 0 <= offset < 8:
                    if x >= 8 or (
                        self.mask & 0x04
                    ):  # Show sprites in leftmost 8 pixels
                        sprite_pixel = (self.sprite_patterns[i] >> (7 - offset)) & 0x03
                        if sprite_pixel != 0:
                            sprite_palette = (self.sprite_indices[i] & 0x03) + 4
                            sprite_priority = (self.sprite_indices[i] >> 5) & 1
                            sprite_zero = i == 0
                            break

        # Determine final pixel
        if bg_pixel == 0 and sprite_pixel == 0:
            # Both transparent - use backdrop color
            color_index = self.palette_ram[0]
        elif bg_pixel == 0 and sprite_pixel > 0:
            # Background transparent, sprite opaque
            color_index = self.palette_ram[sprite_palette * 4 + sprite_pixel]
        elif bg_pixel > 0 and sprite_pixel == 0:
            # Background opaque, sprite transparent
            color_index = self.palette_ram[bg_palette * 4 + bg_pixel]
        else:
            # Both opaque - check priority
            if sprite_zero and x < 255:
                self.sprite_zero_hit = True
                self.status |= 0x40

            if sprite_priority == 0:
                color_index = self.palette_ram[sprite_palette * 4 + sprite_pixel]
            else:
                color_index = self.palette_ram[bg_palette * 4 + bg_pixel]

        # Convert to RGB and store
        color_index = color_index & 0x3F
        self.screen[y][x] = self.palette[color_index][:]

        # Shift background shift registers
        self.bg_shift_pattern_low <<= 1
        self.bg_shift_pattern_high <<= 1
        self.bg_shift_attrib_low <<= 1
        self.bg_shift_attrib_high <<= 1

    def fetch_tile_data(self):
        """Fetch tile data for background rendering"""
        if not (self.mask & 0x08):  # Background rendering disabled
            return

        cycle_in_tile = (self.cycle - 1) % 8

        if cycle_in_tile == 0:
            # Reload shift registers
            self.bg_shift_pattern_low = (
                self.bg_shift_pattern_low & 0xFF00
            ) | self.bg_low_byte
            self.bg_shift_pattern_high = (
                self.bg_shift_pattern_high & 0xFF00
            ) | self.bg_high_byte

            attrib_low = 0xFF if self.at_byte & 1 else 0x00
            attrib_high = 0xFF if self.at_byte & 2 else 0x00
            self.bg_shift_attrib_low = (self.bg_shift_attrib_low & 0xFF00) | attrib_low
            self.bg_shift_attrib_high = (
                self.bg_shift_attrib_high & 0xFF00
            ) | attrib_high

        if cycle_in_tile == 1:
            # Fetch name table byte
            self.nt_byte = self.read_vram(0x2000 | (self.v & 0x0FFF))
        elif cycle_in_tile == 3:
            # Fetch attribute table byte
            addr = (
                0x23C0
                | (self.v & 0x0C00)
                | ((self.v >> 4) & 0x38)
                | ((self.v >> 2) & 0x07)
            )
            self.at_byte = self.read_vram(addr)
            if (self.v >> 1) & 1:
                self.at_byte >>= 2
            if (self.v >> 6) & 1:
                self.at_byte >>= 4
            self.at_byte &= 3
        elif cycle_in_tile == 5:
            # Fetch pattern table low byte
            fine_y = (self.v >> 12) & 7
            table = (self.ctrl >> 4) & 1
            addr = table * 0x1000 + self.nt_byte * 16 + fine_y
            self.bg_low_byte = self.read_vram(addr)
        elif cycle_in_tile == 7:
            # Fetch pattern table high byte
            fine_y = (self.v >> 12) & 7
            table = (self.ctrl >> 4) & 1
            addr = table * 0x1000 + self.nt_byte * 16 + fine_y + 8
            self.bg_high_byte = self.read_vram(addr)

            # Increment horizontal position
            if (self.v & 0x001F) == 31:
                self.v &= 0xFFE0
                self.v ^= 0x0400
            else:
                self.v += 1

    def increment_y(self):
        """Increment Y position in VRAM address"""
        if (self.v & 0x7000) != 0x7000:
            self.v += 0x1000
        else:
            self.v &= 0x8FFF
            y = (self.v & 0x03E0) >> 5
            if y == 29:
                y = 0
                self.v ^= 0x0800
            elif y == 31:
                y = 0
            else:
                y += 1
            self.v = (self.v & 0xFC1F) | (y << 5)

    def copy_x(self):
        """Copy X position from temporary to current VRAM address"""
        self.v = (self.v & 0xFBE0) | (self.t & 0x041F)

    def copy_y(self):
        """Copy Y position from temporary to current VRAM address"""
        self.v = (self.v & 0x841F) | (self.t & 0x7BE0)

    def evaluate_sprites(self):
        """Evaluate sprites for current scanline"""
        self.sprite_count = 0
        sprite_height = 16 if self.ctrl & 0x20 else 8

        for i in range(64):
            oam_addr = i * 4
            y = self.oam[oam_addr]

            if self.scanline >= y and self.scanline < y + sprite_height:
                if self.sprite_count < 8:
                    # Copy sprite data
                    self.sprite_positions[self.sprite_count] = self.oam[oam_addr + 3]
                    self.sprite_indices[self.sprite_count] = self.oam[oam_addr + 2]

                    # Fetch sprite pattern
                    tile = self.oam[oam_addr + 1]
                    attrib = self.oam[oam_addr + 2]
                    sprite_y = self.scanline - y

                    if attrib & 0x80:  # Vertical flip
                        sprite_y = sprite_height - 1 - sprite_y

                    if sprite_height == 16:
                        table = tile & 1
                        tile = tile & 0xFE
                        if sprite_y > 7:
                            tile += 1
                            sprite_y -= 8
                    else:
                        table = (self.ctrl >> 3) & 1

                    addr = table * 0x1000 + tile * 16 + sprite_y
                    low = self.read_vram(addr)
                    high = self.read_vram(addr + 8)

                    # Combine pattern bytes
                    pattern = 0
                    for bit in range(8):
                        pixel = ((high >> (7 - bit)) & 1) << 1 | (
                            (low >> (7 - bit)) & 1
                        )
                        if attrib & 0x40:  # Horizontal flip
                            pattern |= pixel << (bit * 2)
                        else:
                            pattern |= pixel << ((7 - bit) * 2)

                    self.sprite_patterns[self.sprite_count] = pattern
                    self.sprite_count += 1
                else:
                    # Sprite overflow
                    self.sprite_overflow = True
                    self.status |= 0x20
                    break
