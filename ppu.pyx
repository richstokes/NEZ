# cython: boundscheck=False, wraparound=False, cdivision=True, language_level=3
"""
NES PPU (Picture Processing Unit) Emulator — Cython accelerated.
Drop-in replacement for ppu.py.
"""
from memory cimport Memory
cdef unsigned int[64] NES_PALETTE
NES_PALETTE = [
    0xFF666666, 0xFF002A88, 0xFF1412A7, 0xFF3B00A4,
    0xFF5C007E, 0xFF6E0040, 0xFF6C0600, 0xFF561D00,
    0xFF333500, 0xFF0B4800, 0xFF005200, 0xFF004F08,
    0xFF00404D, 0xFF000000, 0xFF000000, 0xFF000000,
    0xFFADADAD, 0xFF155FD9, 0xFF4240FF, 0xFF7527FE,
    0xFFA01ACC, 0xFFB71E7B, 0xFFB53120, 0xFF994E00,
    0xFF6B6D00, 0xFF388700, 0xFF0C9300, 0xFF008F32,
    0xFF007C8D, 0xFF000000, 0xFF000000, 0xFF000000,
    0xFFFFFEFF, 0xFF64B0FF, 0xFF9290FF, 0xFFC676FF,
    0xFFF36AFF, 0xFFFE6ECC, 0xFFFE8170, 0xFFEA9E22,
    0xFFBCBE00, 0xFF88D800, 0xFF5CE430, 0xFF45E082,
    0xFF48CDDE, 0xFF4F4F4F, 0xFF000000, 0xFF000000,
    0xFFFFFEFF, 0xFFC0DFFF, 0xFFD3D2FF, 0xFFE8C8FF,
    0xFFFBC2FF, 0xFFFEC4EA, 0xFFFECCC5, 0xFFF7D8A5,
    0xFFE4E594, 0xFFCFEF96, 0xFFBDF4AB, 0xFFB3F3CC,
    0xFFB5EBF2, 0xFFB8B8B8, 0xFF000000, 0xFF000000,
]

cdef inline int _reverse_byte(int b):
    b = ((b & 0xF0) >> 4) | ((b & 0x0F) << 4)
    b = ((b & 0xCC) >> 2) | ((b & 0x33) << 2)
    b = ((b & 0xAA) >> 1) | ((b & 0x55) << 1)
    return b


cdef class PPU:
    # Attribute declarations are in ppu.pxd

    def __init__(self, memory, region='NTSC'):
        self.memory = memory
        self.region = region

        self.ctrl = 0; self.mask = 0; self.status = 0
        self.oam_addr = 0; self.oam_data = 0; self.scroll = 0
        self.addr = 0; self.data = 0
        self.v = 0; self.t = 0; self.x = 0; self.w = 0
        self.vram = [0] * 0x4000
        self.palette_ram = [0] * 0x20
        self.oam = [0] * 0x100

        self.scanline = 0; self.cycle = 0; self.frame = 0
        self.odd_frame = False
        self.nt_byte = 0; self.at_byte = 0
        self.bg_low_byte = 0; self.bg_high_byte = 0
        self.bg_shift_pattern_low = 0; self.bg_shift_pattern_high = 0
        self.bg_shift_attrib_low = 0; self.bg_shift_attrib_high = 0
        self.bg_next_tile_id = 0; self.bg_next_tile_attr = 0
        self.bg_next_tile_lsb = 0; self.bg_next_tile_msb = 0

        self.sprite_count = 0
        self.secondary_oam = [0xFF] * 32
        self.prep_sprite_indices = [0] * 8
        self.prep_sprite_x = [0] * 8
        self.prep_sprite_attr = [0] * 8
        self.prep_sprite_tile = [0] * 8
        self.prep_sprite_row_low = [0] * 8
        self.prep_sprite_row_high = [0] * 8
        self.sprite_shift_low = [0] * 8
        self.sprite_shift_high = [0] * 8
        self.sprite_latch_attr = [0] * 8
        self.sprite_latch_x = [0] * 8
        self.sprite_is_sprite0 = [False] * 8

        self.sprite_zero_hit = False
        self.sprite_overflow = False
        self.screen = [0] * (256 * 240)
        self.render = False
        self.rendering_enabled = True

        self.nes_palette = list(NES_PALETTE)

        self.VISIBLE_SCANLINES = 240
        self.VISIBLE_DOTS = 256
        self.DOTS_PER_SCANLINE = 341
        self.END_DOT = 340
        self.SCANLINES_PER_FRAME = 311 if region == 'PAL' else 262

        self.SPRITE_TABLE = 1 << 3
        self.BG_TABLE = 1 << 4
        self.SHOW_BG_8 = 1 << 1
        self.SHOW_SPRITE_8 = 1 << 2
        self.SHOW_BG = 1 << 3
        self.SHOW_SPRITE = 1 << 4
        self.LONG_SPRITE = 1 << 5
        self.SPRITE_0_HIT = 1 << 6
        self.V_BLANK = 1 << 7
        self.GENERATE_NMI = 1 << 7
        self.COARSE_X = 0x1F
        self.COARSE_Y = 0x3E0
        self.FINE_Y = 0x7000
        self.HORIZONTAL_BITS = 0x41F
        self.VERTICAL_BITS = 0x7BE0

        self.buffer = 0
        self.bus = 0
        self.bus_decay_timer = [0] * 8
        self.BUS_DECAY_TIME = 600000

        self.sprite_eval_phase = 0
        self.sprite_eval_index = 0
        self.secondary_index = 0
        self.sprite_fetch_cycle = 0
        self.eval_scanline_target = 0
        self._sprite_pattern_buffer_low = [0] * 8
        self._sprite_pattern_buffer_high = [0] * 8
        self.pending_sprite_count = 0
        self.pending_sprite_indices = [0] * 8
        self.pending_sprite_attr = [0] * 8
        self.pending_sprite_x = [0] * 8
        self.pending_sprite_is_sprite0 = [False] * 8
        self.use_new_sprite_pipeline = True

    def reset(self):
        self.ctrl = 0; self.mask = 0
        self.status = 0x20
        self.oam_addr = 0
        self.v = 0; self.t = 0; self.x = 0; self.w = 0
        self.scanline = 240; self.cycle = 0; self.frame = 0
        self.odd_frame = False
        self.vram = [0] * 0x4000
        self.palette_ram = [0] * 0x20
        self.oam = [0] * 0x100
        self.buffer = 0; self.bus = 0
        self.bus_decay_timer = [0] * 8

    # ---- register I/O (called from Memory, must be Python-visible) ----

    def read_register(self, int addr):
        cdef int result, pv
        if addr == 0x2002:
            result = (self.status & 0xE0) | (self.bus & 0x1F)
            self.status &= ~0x80
            self.w = 0
            self.refresh_bus_bits(0xE0, result)
            return result
        elif addr == 0x2004:
            result = self.oam[self.oam_addr]
            self.refresh_bus_bits(0xFF, result)
            return result
        elif addr == 0x2007:
            result = self.buffer
            if self.v < 0x3F00:
                self.buffer = self._read_vram(self.v)
                self.refresh_bus_bits(0xFF, result)
            else:
                self.buffer = self._read_vram(self.v - 0x1000)
                pv = self._read_vram(self.v)
                result = (self.bus & 0xC0) | (pv & 0x3F)
                self.refresh_bus_bits(0x3F, result)
            if self.ctrl & 0x04:
                self.v = (self.v + 32) & 0x7FFF
            else:
                self.v = (self.v + 1) & 0x7FFF
            return result
        return self.bus

    def write_register(self, int addr, int value):
        cdef int old_ctrl
        self.refresh_bus_bits(0xFF, value)
        if addr == 0x2000:
            old_ctrl = self.ctrl
            self.ctrl = value
            self.t = (self.t & 0xF3FF) | ((value & 0x03) << 10)
            if (not (old_ctrl & 0x80)) and (value & 0x80) and (self.status & 0x80):
                if hasattr(self.memory, "nes") and hasattr(self.memory.nes, "trigger_nmi"):
                    self.memory.nes.trigger_nmi()
        elif addr == 0x2001:
            self.mask = value
        elif addr == 0x2003:
            self.oam_addr = value
        elif addr == 0x2004:
            self.oam[self.oam_addr] = value
            self.oam_addr = (self.oam_addr + 1) & 0xFF
        elif addr == 0x2005:
            if self.w == 0:
                self.t = (self.t & 0xFFE0) | (value >> 3)
                self.x = value & 0x07
                self.w = 1
            else:
                self.t = (self.t & 0x8FFF) | ((value & 0x07) << 12)
                self.t = (self.t & 0xFC1F) | ((value & 0xF8) << 2)
                self.w = 0
        elif addr == 0x2006:
            if self.w == 0:
                self.t = (self.t & 0x80FF) | ((value & 0x3F) << 8)
                self.w = 1
            else:
                self.t = (self.t & 0xFF00) | value
                self.v = self.t
                self.w = 0
        elif addr == 0x2007:
            self._write_vram(self.v, value)
            if self.ctrl & 0x04:
                self.v = (self.v + 32) & 0x7FFF
            else:
                self.v = (self.v + 1) & 0x7FFF

    # ---- VRAM access (cdef = C-speed internal, def = Python wrapper) ----

    cdef int _read_vram(self, int addr):
        cdef int nt_idx, off
        addr = addr & 0x3FFF
        if addr < 0x2000:
            self.bus = self.memory.ppu_read(addr)
            return self.bus
        elif addr < 0x3F00:
            addr = (addr & 0xEFFF) - 0x2000
            nt_idx = addr // 0x400
            off = addr & 0x3FF
            if hasattr(self.memory, "cartridge") and self.memory.cartridge:
                self.bus = self.vram[self.memory.cartridge.name_table_map[nt_idx] + off]
            else:
                if addr >= 0x800:
                    addr = addr % 0x800
                self.bus = self.vram[addr]
            return self.bus
        else:
            addr = (addr - 0x3F00) % 0x20
            if addr % 4 == 0:
                if addr == 0x10: addr = 0x00
                elif addr == 0x14: addr = 0x04
                elif addr == 0x18: addr = 0x08
                elif addr == 0x1C: addr = 0x0C
            return self.palette_ram[addr]

    def read_vram(self, addr):
        return self._read_vram(addr)

    cdef void _write_vram(self, int addr, int value):
        cdef int nt_idx, off
        addr = addr & 0x3FFF
        self.bus = value
        if addr < 0x2000:
            self.memory.ppu_write(addr, value)
        elif addr < 0x3F00:
            addr = (addr & 0xEFFF) - 0x2000
            nt_idx = addr // 0x400
            off = addr & 0x3FF
            if hasattr(self.memory, "cartridge") and self.memory.cartridge:
                self.vram[self.memory.cartridge.name_table_map[nt_idx] + off] = value
            else:
                if addr >= 0x800:
                    addr = addr % 0x800
                self.vram[addr] = value
        else:
            addr = (addr - 0x3F00) % 0x20
            if addr % 4 == 0:
                self.palette_ram[addr] = value
                self.palette_ram[addr ^ 0x10] = value
            else:
                self.palette_ram[addr] = value

    def write_vram(self, addr, value):
        self._write_vram(addr, value)

    # ---- hot inner loop: step() ----

    cpdef void step(self):
        cdef int sl, cyc, px, mask, show_bg

        if self.use_new_sprite_pipeline:
            self._sprite_pipeline_step_c()

        sl = self.scanline
        cyc = self.cycle
        mask = self.mask
        show_bg = mask & 0x08  # SHOW_BG

        if sl < 240:
            if cyc > 0 and cyc <= 256:
                if show_bg:
                    self._fetch_background_data_c()
                if mask & 0x18:  # SHOW_BG | SHOW_SPRITE
                    self._render_pixel_c()
                else:
                    px = cyc - 1
                    self.screen[sl * 256 + px] = self.nes_palette[self.palette_ram[0] & 0x3F]
                if show_bg:
                    self.bg_shift_pattern_low = (self.bg_shift_pattern_low << 1) & 0xFFFF
                    self.bg_shift_pattern_high = (self.bg_shift_pattern_high << 1) & 0xFFFF
                    self.bg_shift_attrib_low = (self.bg_shift_attrib_low << 1) & 0xFFFF
                    self.bg_shift_attrib_high = (self.bg_shift_attrib_high << 1) & 0xFFFF
                if (cyc & 7) == 0 and show_bg:
                    self._increment_x_c()

            if (not self.use_new_sprite_pipeline) and cyc == 257:
                target = sl + 1
                if target == 240:
                    pass
                elif target == 261:
                    self.prepare_sprites(0)
                elif target < 240:
                    self.prepare_sprites(target)
            elif cyc == 256 and show_bg:
                self._increment_y_c()
            elif cyc == 257 and (mask & 0x18):
                self._copy_x_c()
            elif 321 <= cyc <= 336 and show_bg:
                self._fetch_background_data_c()
                self.bg_shift_pattern_low = (self.bg_shift_pattern_low << 1) & 0xFFFF
                self.bg_shift_pattern_high = (self.bg_shift_pattern_high << 1) & 0xFFFF
                self.bg_shift_attrib_low = (self.bg_shift_attrib_low << 1) & 0xFFFF
                self.bg_shift_attrib_high = (self.bg_shift_attrib_high << 1) & 0xFFFF
                if cyc == 328 or cyc == 336:
                    self._increment_x_c()

        # Post-render (240) — nothing

        # Advance cycle / scanline
        self.cycle = cyc + 1
        if self.cycle >= 341:
            self.cycle = 0
            self.scanline = sl + 1
            if self.scanline > 261:
                self.scanline = 0
                self.frame += 1
                self.render = True

        # VBlank
        if 241 <= self.scanline <= 260:
            if self.scanline == 241 and self.cycle == 1:
                old_status = self.status
                self.status |= 0x80
                if (self.status & 0x80) and not (old_status & 0x80):
                    if self.ctrl & 0x80:
                        if hasattr(self.memory, "nes") and hasattr(self.memory.nes, "trigger_nmi"):
                            self.memory.nes.trigger_nmi()
        elif self.scanline == 261:
            if self.cycle == 1:
                self.status &= ~0x80
                self.status &= ~0x40
                self.status &= ~0x20
            elif 280 <= self.cycle <= 304 and (mask & 0x18):
                self._copy_y_c()
            elif self.cycle == 256 and show_bg:
                self._increment_y_c()
            elif self.cycle == 257 and (mask & 0x18):
                self._copy_x_c()
            elif 321 <= self.cycle <= 336 and show_bg:
                self._fetch_background_data_c()
                self.bg_shift_pattern_low = (self.bg_shift_pattern_low << 1) & 0xFFFF
                self.bg_shift_pattern_high = (self.bg_shift_pattern_high << 1) & 0xFFFF
                self.bg_shift_attrib_low = (self.bg_shift_attrib_low << 1) & 0xFFFF
                self.bg_shift_attrib_high = (self.bg_shift_attrib_high << 1) & 0xFFFF
                if self.cycle == 328 or self.cycle == 336:
                    self._increment_x_c()
            elif (self.cycle == 339 and (self.frame & 1)
                  and (mask & 0x18)
                  and self.region == 'NTSC'):
                self.cycle += 1

    def step_n(self, int n):
        cdef int i
        for i in range(n):
            self.step()

    # ---- pixel rendering (C-speed) ----

    cdef void _render_pixel_c(self):
        cdef int px, y, bg_pixel, bg_palette, sprite_pixel, sprite_palette
        cdef int sprite_priority, palette_addr, color_index
        cdef unsigned int color
        cdef int sprite_info, r, g, b
        cdef bint sprite_zero
        cdef int mask = self.mask

        px = self.cycle - 1
        y = self.scanline
        if px >= 256 or y >= 240:
            return

        bg_pixel = 0; bg_palette = 0
        if mask & 0x08:
            if px >= 8 or (mask & 0x02):
                bg_pixel = self._render_background_c()
                bg_palette = bg_pixel >> 2
                bg_pixel = bg_pixel & 0x3

        sprite_pixel = 0; sprite_palette = 0; sprite_priority = 0; sprite_zero = False
        if mask & 0x10:
            # Always tick sprite shift registers (hardware clocks them every cycle);
            # left-column mask only suppresses the *output*.
            sprite_info = self._render_sprites_c(bg_pixel)
            if sprite_info and (px >= 8 or (mask & 0x04)):
                sprite_pixel = sprite_info & 0x3
                sprite_palette = (sprite_info >> 2) & 0x3
                sprite_priority = (sprite_info >> 5) & 1
                sprite_zero = (sprite_info >> 6) & 1

        palette_addr = 0
        if bg_pixel == 0 and sprite_pixel == 0:
            palette_addr = 0
        elif bg_pixel == 0:
            palette_addr = 0x10 + sprite_palette * 4 + sprite_pixel
        elif sprite_pixel == 0:
            palette_addr = bg_palette * 4 + bg_pixel
        else:
            if sprite_priority == 0:
                palette_addr = 0x10 + sprite_palette * 4 + sprite_pixel
            else:
                palette_addr = bg_palette * 4 + bg_pixel

        color_index = self.palette_ram[palette_addr] & 0x3F
        if mask & 0x01:
            color_index &= 0x30
        color = self.nes_palette[color_index]
        if mask & 0xE0:
            r = (color >> 16) & 0xFF
            g = (color >> 8) & 0xFF
            b = color & 0xFF
            if mask & 0x20:
                g = (g * 3) >> 2; b = (b * 3) >> 2
            if mask & 0x40:
                r = (r * 3) >> 2; b = (b * 3) >> 2
            if mask & 0x80:
                r = (r * 3) >> 2; g = (g * 3) >> 2
            color = (color & <unsigned int>0xFF000000) | (<unsigned int>r << 16) | (<unsigned int>g << 8) | <unsigned int>b

        self.screen[y * 256 + px] = color

    def render_pixel(self):
        self._render_pixel_c()

    cdef int _render_background_c(self):
        cdef int px, fine_x, tap, lo, hi, pixel, al, ah, pal
        if not (self.mask & 0x08):
            return 0
        px = self.cycle - 1
        if px < 8 and not (self.mask & 0x02):
            return 0
        fine_x = self.x & 0x7
        tap = 15 - fine_x
        lo = (self.bg_shift_pattern_low >> tap) & 1
        hi = (self.bg_shift_pattern_high >> tap) & 1
        pixel = lo | (hi << 1)
        if pixel == 0:
            return 0
        al = (self.bg_shift_attrib_low >> tap) & 1
        ah = (self.bg_shift_attrib_high >> tap) & 1
        pal = al | (ah << 1)
        return pixel | (pal << 2)

    def render_background(self):
        return self._render_background_c()

    cdef int _render_sprites_c(self, int bg_pixel):
        cdef int i, attr, pixel_low, pixel_high, pixel, palette, priority, px
        cdef bint is_sprite0
        cdef int mask = self.mask
        cdef int result = 0

        if not (mask & 0x10) or self.sprite_count == 0:
            return 0
        px = self.cycle - 1
        # Process ALL sprites every cycle (real NES clocks all shift registers
        # in parallel). Only record the first (highest-priority) opaque pixel.
        for i in range(self.sprite_count):
            if self.sprite_latch_x[i] > 0:
                self.sprite_latch_x[i] -= 1
                continue
            attr = self.sprite_latch_attr[i]
            pixel_low = (self.sprite_shift_low[i] >> 7) & 1
            pixel_high = (self.sprite_shift_high[i] >> 7) & 1
            self.sprite_shift_low[i] = (self.sprite_shift_low[i] << 1) & 0xFF
            self.sprite_shift_high[i] = (self.sprite_shift_high[i] << 1) & 0xFF
            pixel = pixel_low | (pixel_high << 1)
            if pixel == 0:
                continue
            if result == 0:
                palette = attr & 0x3
                priority = (attr >> 5) & 1
                is_sprite0 = self.sprite_is_sprite0[i]
                if (is_sprite0 and bg_pixel > 0 and px < 255
                    and (mask & 0x08) and (mask & 0x10)
                    and not (self.status & 0x40)
                    and not (px < 8 and not (mask & 0x02))
                    and not (px < 8 and not (mask & 0x04))):
                    self.status |= 0x40
                    self.sprite_zero_hit = True
                result = pixel | (palette << 2) | (priority << 5) | ((<int>is_sprite0) << 6)
        return result

    def render_sprites(self, bg_pixel):
        return self._render_sprites_c(bg_pixel)

    # ---- sprite pipeline (C-speed) ----

    cdef void _sprite_pipeline_step_c(self):
        cdef int sl, cyc, sprite_height, target_scanline, i, base, y, start, end
        cdef int idx, row, attr, tile, base_tile, table, tile_half, tile_index
        cdef int fine_y, pattern_addr, low, high

        sl = self.scanline
        cyc = self.cycle
        if sl >= 240 and sl != 261:
            return

        sprite_height = 16 if (self.ctrl & 0x20) else 8
        target_scanline = 0 if sl == 261 else sl + 1
        if target_scanline >= 240:
            if 1 <= cyc <= 64:
                if cyc == 1:
                    for i in range(32):
                        self.secondary_oam[i] = 0xFF
                    self.pending_sprite_count = 0
            return

        if 1 <= cyc <= 64:
            if cyc == 1:
                for i in range(32):
                    self.secondary_oam[i] = 0xFF
                self.pending_sprite_count = 0
            return

        if 65 <= cyc <= 256:
            if cyc == 65:
                self.sprite_eval_index = 0
                self.pending_sprite_count = 0
                self.sprite_overflow = False
            # Check sprites every 3 cycles
            if (cyc - 65) % 3 == 0 and self.pending_sprite_count < 8 and self.sprite_eval_index < 64:
                i = self.sprite_eval_index
                base = i * 4
                y = self.oam[base]
                start = y + 1
                end = start + sprite_height - 1
                if start <= target_scanline <= end:
                    self.pending_sprite_indices[self.pending_sprite_count] = i
                    self.pending_sprite_attr[self.pending_sprite_count] = self.oam[base + 2]
                    self.pending_sprite_x[self.pending_sprite_count] = self.oam[base + 3]
                    self.pending_sprite_is_sprite0[self.pending_sprite_count] = (i == 0)
                    self.pending_sprite_count += 1
                self.sprite_eval_index += 1
            # Continue checking for overflow after we have 8 sprites
            elif (cyc - 65) % 3 == 0 and self.pending_sprite_count >= 8 and self.sprite_eval_index < 64:
                i = self.sprite_eval_index
                base = i * 4
                y = self.oam[base]
                start = y + 1
                end = start + sprite_height - 1
                if start <= target_scanline <= end:
                    self.status |= 0x20
                    self.sprite_overflow = True
                self.sprite_eval_index += 1
            return

        if 257 <= cyc <= 320:
            if cyc == 257:
                for slot in range(self.pending_sprite_count):
                    idx = self.pending_sprite_indices[slot]
                    base = idx * 4
                    y = self.oam[base]
                    row = target_scanline - (y + 1)
                    attr = self.pending_sprite_attr[slot]
                    if attr & 0x80:
                        row = (sprite_height - 1) - row
                    tile = self.oam[base + 1]
                    if sprite_height == 16:
                        base_tile = tile & 0xFE
                        table = tile & 1
                        tile_half = 0 if row < 8 else 1
                        tile_index = base_tile + tile_half
                        fine_y = row & 7
                        pattern_addr = tile_index * 16 + fine_y + (table * 0x1000)
                    else:
                        pattern_addr = tile * 16 + row
                        if self.ctrl & 0x08:
                            pattern_addr += 0x1000
                    low = self._read_vram(pattern_addr)
                    high = self._read_vram(pattern_addr + 8)
                    if attr & 0x40:
                        low = _reverse_byte(low)
                        high = _reverse_byte(high)
                    self._sprite_pattern_buffer_low[slot] = low
                    self._sprite_pattern_buffer_high[slot] = high
            return

        if cyc == 0:
            if sl < 240:
                self.sprite_count = self.pending_sprite_count
                for i in range(self.sprite_count):
                    self.prep_sprite_indices[i] = self.pending_sprite_indices[i]
                    self.sprite_shift_low[i] = self._sprite_pattern_buffer_low[i]
                    self.sprite_shift_high[i] = self._sprite_pattern_buffer_high[i]
                    self.sprite_latch_attr[i] = self.pending_sprite_attr[i]
                    self.sprite_latch_x[i] = self.pending_sprite_x[i]
                    self.sprite_is_sprite0[i] = self.pending_sprite_is_sprite0[i]

    # Keep Python-visible name
    def _sprite_pipeline_step(self):
        self._sprite_pipeline_step_c()

    # ---- scroll helpers (C-speed) ----

    cdef void _increment_x_c(self):
        if (self.v & 0x1F) == 31:
            self.v &= ~0x1F
            self.v ^= 0x400
        else:
            self.v += 1

    def increment_x(self):
        self._increment_x_c()

    cdef void _increment_y_c(self):
        cdef int coarse_y
        if (self.v & 0x7000) != 0x7000:
            self.v += 0x1000
        else:
            self.v &= ~0x7000
            coarse_y = (self.v & 0x3E0) >> 5
            if coarse_y == 29:
                coarse_y = 0; self.v ^= 0x800
            elif coarse_y == 31:
                coarse_y = 0
            else:
                coarse_y += 1
            self.v = (self.v & ~0x3E0) | (coarse_y << 5)

    def increment_y(self):
        self._increment_y_c()

    cdef void _copy_x_c(self):
        self.v = (self.v & ~0x41F) | (self.t & 0x41F)

    def copy_x(self):
        self._copy_x_c()

    cdef void _copy_y_c(self):
        self.v = (self.v & ~0x7BE0) | (self.t & 0x7BE0)

    def copy_y(self):
        self._copy_y_c()

    # ---- background fetch (C-speed) ----

    cdef void _fetch_background_data_c(self):
        cdef int cit, tile_addr, attr_addr, pattern_addr, attr_bits
        cdef int attr_low, attr_high
        cit = (self.cycle - 1) % 8
        if cit == 0:
            tile_addr = 0x2000 | (self.v & 0xFFF)
            self.nt_byte = self._read_vram(tile_addr)
        elif cit == 2:
            attr_addr = 0x23C0 | (self.v & 0x0C00) | ((self.v >> 4) & 0x38) | ((self.v >> 2) & 0x07)
            self.at_byte = self._read_vram(attr_addr)
        elif cit == 4:
            pattern_addr = (self.nt_byte * 16) + ((self.v >> 12) & 0x7)
            if self.ctrl & 0x10:
                pattern_addr += 0x1000
            self.bg_low_byte = self._read_vram(pattern_addr)
        elif cit == 6:
            pattern_addr = (self.nt_byte * 16) + ((self.v >> 12) & 0x7) + 8
            if self.ctrl & 0x10:
                pattern_addr += 0x1000
            self.bg_high_byte = self._read_vram(pattern_addr)
        elif cit == 7:
            self.bg_shift_pattern_low = (self.bg_shift_pattern_low & 0xFF00) | self.bg_low_byte
            self.bg_shift_pattern_high = (self.bg_shift_pattern_high & 0xFF00) | self.bg_high_byte
            attr_bits = (self.at_byte >> ((self.v >> 4) & 4 | self.v & 2)) & 0x3
            attr_low = 0xFF if (attr_bits & 1) else 0
            attr_high = 0xFF if (attr_bits & 2) else 0
            self.bg_shift_attrib_low = (self.bg_shift_attrib_low & 0xFF00) | attr_low
            self.bg_shift_attrib_high = (self.bg_shift_attrib_high & 0xFF00) | attr_high

    def fetch_background_data(self):
        self._fetch_background_data_c()

    # ---- bus decay (not hot, keep as Python) ----

    def refresh_bus_bits(self, int bits_mask, int value):
        cdef int bit
        for bit in range(8):
            if bits_mask & (1 << bit):
                self.bus = (self.bus & ~(1 << bit)) | (value & (1 << bit))
                self.bus_decay_timer[bit] = self.BUS_DECAY_TIME

    def update_bus_decay(self, int cpu_cycles_elapsed):
        cdef int bit
        for bit in range(8):
            if self.bus_decay_timer[bit] > 0:
                self.bus_decay_timer[bit] -= cpu_cycles_elapsed
                if self.bus_decay_timer[bit] <= 0:
                    self.bus &= ~(1 << bit)
                    self.bus_decay_timer[bit] = 0

    # ---- legacy sprite preparation ----

    def prepare_sprites(self, int target_scanline):
        cdef int sprite_height, count, i, base, y, tile, attr, x_pos
        cdef int start, end, row, base_tile, table, tile_half, tile_index
        cdef int fine_y, pattern_addr, low, high
        cdef bint overflow
        sprite_height = 16 if self.ctrl & 0x20 else 8
        count = 0; overflow = False
        for i in range(64):
            base = i * 4
            y = self.oam[base]; tile = self.oam[base+1]
            attr = self.oam[base+2]; x_pos = self.oam[base+3]
            start = y + 1; end = start + sprite_height - 1
            if target_scanline < start or target_scanline > end:
                continue
            if count < 8:
                row = target_scanline - start
                if attr & 0x80:
                    row = (sprite_height - 1) - row
                if sprite_height == 16:
                    base_tile = tile & 0xFE; table = tile & 1
                    tile_half = 0 if row < 8 else 1
                    tile_index = base_tile + tile_half
                    fine_y = row & 7
                    pattern_addr = tile_index * 16 + fine_y + (table * 0x1000)
                else:
                    pattern_addr = tile * 16 + row
                    if self.ctrl & 0x08:
                        pattern_addr += 0x1000
                low = self._read_vram(pattern_addr)
                high = self._read_vram(pattern_addr + 8)
                if attr & 0x40:
                    low = _reverse_byte(low)
                    high = _reverse_byte(high)
                self.prep_sprite_indices[count] = i
                self.sprite_shift_low[count] = low
                self.sprite_shift_high[count] = high
                self.sprite_latch_attr[count] = attr
                self.sprite_latch_x[count] = x_pos
                self.sprite_is_sprite0[count] = (i == 0)
                count += 1
            else:
                overflow = True; break
        self.sprite_count = count
        if overflow:
            self.status |= 0x20
        else:
            self.status &= ~0x20

    @staticmethod
    def reverse_byte(b):
        return _reverse_byte(b)
