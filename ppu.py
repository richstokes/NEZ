"""
NES PPU (Picture Processing Unit) Emulator
Handles graphics rendering for the NES
"""

from utils import debug_print


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

        # Background rendering data
        self.nt_byte = 0  # Name table byte
        self.at_byte = 0  # Attribute table byte
        self.bg_low_byte = 0  # Background pattern low byte
        self.bg_high_byte = 0  # Background pattern high byte

        # Background shift registers (16-bit for proper scrolling)
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
        self.oam_cache = [0] * 8  # Cache for sprites on current scanline
        self.oam_cache_len = 0

        # Flags
        self.sprite_zero_hit = False
        self.sprite_overflow = False

        # Output buffer (256x240 pixels, 32-bit ARGB values)
        self.screen = [0] * (256 * 240)

        # Performance optimization: render flag like reference
        self.render = False

        # Optimized rendering: only render when needed
        self.rendering_enabled = True

        # NES color palette (32-bit ARGB values converted to ABGR for SDL compatibility)
        # Reference implementation uses to_pixel_format() to convert ARGB->ABGR
        nes_palette_argb = [
            0xFF666666,
            0xFF002A88,
            0xFF1412A7,
            0xFF3B00A4,
            0xFF5C007E,
            0xFF6E0040,
            0xFF6C0600,
            0xFF561D00,
            0xFF333500,
            0xFF0B4800,
            0xFF005200,
            0xFF004F08,
            0xFF00404D,
            0xFF000000,
            0xFF000000,
            0xFF000000,
            0xFFADADAD,
            0xFF155FD9,
            0xFF4240FF,
            0xFF7527FE,
            0xFFA01ACC,
            0xFFB71E7B,
            0xFFB53120,
            0xFF994E00,
            0xFF6B6D00,
            0xFF388700,
            0xFF0C9300,
            0xFF008F32,
            0xFF007C8D,
            0xFF000000,
            0xFF000000,
            0xFF000000,
            0xFFFFFEFF,
            0xFF64B0FF,
            0xFF9290FF,
            0xFFC676FF,
            0xFFF36AFF,
            0xFFFE6ECC,
            0xFFFE8170,
            0xFFEA9E22,
            0xFFBCBE00,
            0xFF88D800,
            0xFF5CE430,
            0xFF45E082,
            0xFF48CDDE,
            0xFF4F4F4F,
            0xFF000000,
            0xFF000000,
            0xFFFFFEFF,
            0xFFC0DFFF,
            0xFFD3D2FF,
            0xFFE8C8FF,
            0xFFFBC2FF,
            0xFFFEC4EA,
            0xFFFECCC5,
            0xFFF7D8A5,
            0xFFE4E594,
            0xFFCFEF96,
            0xFFBDF4AB,
            0xFFB3F3CC,
            0xFFB5EBF2,
            0xFFB8B8B8,
            0xFF000000,
            0xFF000000,
        ]

        # Convert ARGB to ABGR format like reference implementation
        self.nes_palette = []
        for color in nes_palette_argb:
            # Convert ARGB (0xAARRGGBB) to ABGR (0xAABBGGRR)
            a = (color >> 24) & 0xFF
            r = (color >> 16) & 0xFF
            g = (color >> 8) & 0xFF
            b = color & 0xFF
            abgr = (a << 24) | (b << 16) | (g << 8) | r
            self.nes_palette.append(abgr)

        # Initialize palette RAM to mirror the reference implementation
        # Two-stage lookup: palette_ram[index] -> nes_palette[result]

        # PPU timing constants
        self.VISIBLE_SCANLINES = 240
        self.VISIBLE_DOTS = 256
        self.DOTS_PER_SCANLINE = 341
        self.SCANLINES_PER_FRAME = 262  # NTSC
        self.END_DOT = 340

        # PPU control flags
        self.BG_TABLE = 1 << 4
        self.SPRITE_TABLE = 1 << 3
        self.SHOW_BG_8 = 1 << 1
        self.SHOW_SPRITE_8 = 1 << 2
        self.SHOW_BG = 1 << 3
        self.SHOW_SPRITE = 1 << 4
        self.LONG_SPRITE = 1 << 5
        self.SPRITE_0_HIT = 1 << 6
        self.V_BLANK = 1 << 7
        self.GENERATE_NMI = 1 << 7

        # Address bit masks
        self.COARSE_X = 0x1F
        self.COARSE_Y = 0x3E0
        self.FINE_Y = 0x7000
        self.HORIZONTAL_BITS = 0x41F
        self.VERTICAL_BITS = 0x7BE0

        self.buffer = 0  # PPU data buffer
        self.bus = 0  # PPU open bus

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
        self.scanline = 261  # Start in pre-render scanline
        self.cycle = 0
        self.frame = 0
        self.odd_frame = False

        # Clear memory
        self.vram = [0] * 0x4000
        self.palette_ram = [0] * 0x20
        self.oam = [0] * 0x100

        self.buffer = 0
        self.bus = 0

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
        self.bus = value

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
            # Handle mirroring
            addr = (addr & 0xEFFF) - 0x2000
            # Simple horizontal mirroring for now
            if addr >= 0x800:
                addr = addr % 0x800
            return self.vram[0x2000 + addr]
        else:
            # Palette RAM
            addr = (addr - 0x3F00) % 0x20
            # Handle palette mirroring
            if addr % 4 == 0:
                # Backdrop colors are mirrored
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
            addr = (addr & 0xEFFF) - 0x2000
            # Simple horizontal mirroring for now
            if addr >= 0x800:
                addr = addr % 0x800
            self.vram[0x2000 + addr] = value
        else:
            # Palette RAM
            addr = (addr - 0x3F00) % 0x20
            # Handle palette mirroring
            if addr % 4 == 0:
                self.palette_ram[addr] = value
                # Mirror backdrop colors
                self.palette_ram[addr ^ 0x10] = value
            else:
                self.palette_ram[addr] = value

    def step(self):
        """Execute one PPU cycle"""
        # Visible scanlines (0-239)
        if self.scanline < self.VISIBLE_SCANLINES:
            if self.cycle > 0 and self.cycle <= self.VISIBLE_DOTS:
                # Render pixel if rendering is enabled
                if self.mask & (self.SHOW_BG | self.SHOW_SPRITE):
                    self.render_pixel()

                # Handle horizontal scrolling - based on reference implementation
                # Calculate fine_x like reference: ((ppu->x + x) % 8)
                x = self.cycle - 1
                fine_x = (self.x + x) % 8
                if fine_x == 7 and (self.mask & self.SHOW_BG):
                    if (self.v & self.COARSE_X) == 31:
                        self.v &= ~self.COARSE_X
                        self.v ^= 0x400  # Switch horizontal nametable
                    else:
                        self.v += 1

            # Increment Y at end of visible area
            elif self.cycle == self.VISIBLE_DOTS + 1 and (self.mask & self.SHOW_BG):
                self.increment_y()

            # Copy X from temp at start of next scanline prep
            elif self.cycle == self.VISIBLE_DOTS + 2 and (
                self.mask & (self.SHOW_BG | self.SHOW_SPRITE)
            ):
                self.copy_x()

            # Sprite evaluation for next scanline
            elif self.cycle == 1:
                if self.mask & self.SHOW_SPRITE:
                    self.evaluate_sprites()

        # Post-render scanline (240) - do nothing
        elif self.scanline == self.VISIBLE_SCANLINES:
            pass

        # VBlank scanlines (241-260)
        elif 241 <= self.scanline <= 260:
            if self.scanline == 241 and self.cycle == 1:
                self.status |= self.V_BLANK  # Set VBlank flag

        # Pre-render scanline (261)
        else:
            if self.cycle == 1:
                # Clear VBlank and sprite 0 hit
                self.status &= ~(self.V_BLANK | self.SPRITE_0_HIT)
                self.sprite_zero_hit = False
                self.sprite_overflow = False

            # Copy Y position from temp register during pre-render
            elif 280 <= self.cycle <= 304 and (
                self.mask & (self.SHOW_BG | self.SHOW_SPRITE)
            ):
                self.copy_y()

            # Copy X position
            elif self.cycle == self.VISIBLE_DOTS + 2 and (
                self.mask & (self.SHOW_BG | self.SHOW_SPRITE)
            ):
                self.copy_x()

            # Skip cycle on odd frames if rendering is enabled
            elif (
                self.cycle == self.END_DOT - 1
                and self.frame & 1
                and (self.mask & (self.SHOW_BG | self.SHOW_SPRITE))
            ):
                self.cycle += 1

        # Increment dots and scanlines (match reference implementation exactly)
        self.cycle += 1
        if self.cycle >= self.DOTS_PER_SCANLINE:
            self.cycle = 0
            self.scanline += 1
            if self.scanline >= self.SCANLINES_PER_FRAME:
                self.scanline = 0
                self.odd_frame = not self.odd_frame
                # Signal frame completion when we wrap back to scanline 0
                self.render = True
                self.frame += 1

    def _increment_scanline_cycle(self):
        """Optimized scanline/cycle increment - DEPRECATED"""
        # This method is no longer used since we inline the logic above
        pass

    def render_pixel(self):
        """Render a single pixel - based on reference implementation"""
        x = self.cycle - 1
        y = self.scanline

        if x >= 256 or y >= 240:
            return

        # Get background pixel
        bg_pixel = 0
        bg_palette = 0

        if self.mask & self.SHOW_BG:
            if x >= 8 or (
                self.mask & self.SHOW_BG_8
            ):  # Show background in leftmost 8 pixels
                bg_pixel = self.render_background()
                bg_palette = bg_pixel >> 2
                bg_pixel &= 0x3

        # Get sprite pixel
        sprite_pixel = 0
        sprite_palette = 0
        sprite_priority = 0
        sprite_zero = False

        if self.mask & self.SHOW_SPRITE:
            if x >= 8 or (
                self.mask & self.SHOW_SPRITE_8
            ):  # Show sprites in leftmost 8 pixels
                sprite_info = self.render_sprites(bg_pixel)
                if sprite_info:
                    sprite_pixel = sprite_info & 0x3
                    sprite_palette = (sprite_info >> 2) & 0x3
                    sprite_priority = (sprite_info >> 5) & 1
                    sprite_zero = (sprite_info >> 6) & 1

        # Determine final pixel color
        palette_addr = 0

        if bg_pixel == 0 and sprite_pixel == 0:
            # Both transparent - use backdrop color
            palette_addr = 0
        elif bg_pixel == 0 and sprite_pixel > 0:
            # Background transparent, sprite opaque
            palette_addr = 0x10 + sprite_palette * 4 + sprite_pixel
        elif bg_pixel > 0 and sprite_pixel == 0:
            # Background opaque, sprite transparent
            palette_addr = bg_palette * 4 + bg_pixel
        else:
            # Both opaque - check priority and sprite 0 hit
            if sprite_zero and x < 255:
                self.status |= self.SPRITE_0_HIT

            if sprite_priority == 0:
                palette_addr = 0x10 + sprite_palette * 4 + sprite_pixel
            else:
                palette_addr = bg_palette * 4 + bg_pixel

        # Get final color from palette (two-stage lookup like reference)
        color_index = self.palette_ram[palette_addr] & 0x3F
        color = self.nes_palette[color_index]

        # Store pixel in screen buffer
        self.screen[y * 256 + x] = color

    def render_background(self):
        """Render background pixel - based on reference implementation"""
        x = self.cycle - 1
        fine_x = (self.x + x) % 8

        if not (self.mask & self.SHOW_BG_8) and x < 8:
            return 0

        # Calculate tile address
        tile_addr = 0x2000 | (self.v & 0xFFF)

        # Calculate attribute address
        attr_addr = (
            0x23C0 | (self.v & 0x0C00) | ((self.v >> 4) & 0x38) | ((self.v >> 2) & 0x07)
        )

        # Get tile index from nametable
        tile_index = self.read_vram(tile_addr)

        # Calculate pattern address
        pattern_addr = tile_index * 16 + ((self.v >> 12) & 0x7)
        if self.ctrl & self.BG_TABLE:
            pattern_addr |= 0x1000

        # Get pattern data
        pattern_low = self.read_vram(pattern_addr) >> (7 - fine_x)
        pattern_high = self.read_vram(pattern_addr + 8) >> (7 - fine_x)

        pixel = (pattern_low & 1) | ((pattern_high & 1) << 1)

        if not pixel:
            return 0

        # Get attribute data
        attr = self.read_vram(attr_addr)
        palette = (attr >> ((self.v >> 4) & 4 | self.v & 2)) & 0x3

        return pixel | (palette << 2)

    def render_sprites(self, bg_pixel):
        """Render sprite pixel - based on reference implementation"""
        x = self.cycle - 1
        y = self.scanline

        sprite_height = 16 if self.ctrl & self.LONG_SPRITE else 8

        # Iterate through sprites in priority order (index 0 = highest priority)
        for j in range(self.oam_cache_len):
            sprite_idx = self.oam_cache[j]
            sprite_x = self.oam[sprite_idx + 3]

            # Check if pixel is within sprite's horizontal range
            if x < sprite_x or x >= sprite_x + 8:
                continue

            sprite_y = (
                self.oam[sprite_idx] + 1
            )  # Sprites are offset by 1 scanline like reference
            tile = self.oam[sprite_idx + 1]
            attr = self.oam[sprite_idx + 2]

            x_offset = x - sprite_x
            y_offset = y - sprite_y

            # Handle sprite flipping (match reference implementation exactly)
            if not (attr & 0x40):  # FLIP_HORIZONTAL bit - if NOT set, flip X
                x_offset = 7 - x_offset
            if attr & 0x80:  # FLIP_VERTICAL bit - if set, flip Y
                y_offset = sprite_height - 1 - y_offset

            # Calculate tile address based on sprite height
            if sprite_height == 16:
                # 8x16 sprites (tile LSB determines pattern table)
                y_offset = (y_offset & 7) | ((y_offset & 8) << 1)
                tile_addr = (tile >> 1) * 32 + y_offset
                tile_addr |= (tile & 1) << 12
            else:
                # 8x8 sprites (SPRITE_TABLE bit determines pattern table)
                tile_addr = tile * 16 + y_offset
                if self.ctrl & self.SPRITE_TABLE:
                    tile_addr += 0x1000

            # Get pattern data
            pattern_low = (self.read_vram(tile_addr) >> x_offset) & 1
            pattern_high = (self.read_vram(tile_addr + 8) >> x_offset) & 1

            pixel = pattern_low | (pattern_high << 1)

            if not pixel:
                continue  # Transparent pixel

            palette = attr & 0x3
            priority = (
                attr >> 5
            ) & 1  # 0 = in front of background, 1 = behind background
            sprite_zero = j == 0  # First sprite in OAM cache is sprite 0

            # Check sprite 0 hit (only if both background and sprite 0 are opaque)
            if (
                sprite_zero
                and bg_pixel
                and pixel
                and x < 255
                and not (self.status & self.SPRITE_0_HIT)
            ):
                self.status |= self.SPRITE_0_HIT

            # Return sprite info packed into single value
            return pixel | (palette << 2) | (priority << 5) | (sprite_zero << 6)

        return 0  # No sprite found

    def increment_y(self):
        """Increment Y position in VRAM address - based on reference implementation"""
        if (self.v & self.FINE_Y) != self.FINE_Y:
            self.v += 0x1000
        else:
            self.v &= ~self.FINE_Y
            coarse_y = (self.v & self.COARSE_Y) >> 5

            if coarse_y == 29:
                coarse_y = 0
                self.v ^= 0x800  # Toggle vertical nametable
            elif coarse_y == 31:
                coarse_y = 0
            else:
                coarse_y += 1

            self.v = (self.v & ~self.COARSE_Y) | (coarse_y << 5)

    def copy_x(self):
        """Copy X position from temporary to current VRAM address"""
        self.v = (self.v & ~self.HORIZONTAL_BITS) | (self.t & self.HORIZONTAL_BITS)

    def copy_y(self):
        """Copy Y position from temporary to current VRAM address"""
        self.v = (self.v & ~self.VERTICAL_BITS) | (self.t & self.VERTICAL_BITS)

    def evaluate_sprites(self):
        """Evaluate sprites for current scanline - based on reference implementation"""
        # Clear sprite cache
        self.oam_cache = [0] * 8
        self.oam_cache_len = 0
        self.sprite_overflow = False

        sprite_height = 16 if self.ctrl & self.LONG_SPRITE else 8
        current_scanline = self.scanline

        # Scan all 64 sprites (starting from OAM address for hardware accuracy)
        sprites_found = 0
        for i in range(64):
            sprite_y = self.oam[i * 4]

            # Check if sprite is on current scanline (match reference exactly)
            diff = current_scanline - sprite_y
            if 0 <= diff < sprite_height:
                if sprites_found < 8:
                    self.oam_cache[sprites_found] = i * 4
                    sprites_found += 1
                else:
                    # Sprite overflow - set flag
                    self.sprite_overflow = True
                    self.status |= 0x20  # Set sprite overflow flag
                    break

        self.oam_cache_len = sprites_found
