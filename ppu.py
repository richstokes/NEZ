"""
NES PPU (Picture Processing Unit) Emulator
Handles graphics rendering for the NES
"""

from utils import debug_print


class PPU:
    def __init__(self, memory, region='NTSC'):
        self.memory = memory
        self.region = region  # Store region for timing decisions

        # PPU registers
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

        # PPU Memory - allocate full 0x4000 space up front (pattern tables + nametables + mirrors)
        # Some code (reset) reinitializes to 0x4000; keeping sizes consistent avoids index issues.
        self.vram = [0] * 0x4000
        self.palette_ram = [0] * 0x20  # Palette memory
        self.oam = [0] * 0x100  # Object Attribute Memory (sprites)

        # Rendering state
        self.scanline = 0
        self.cycle = 0
        self.frame = 0
        self.odd_frame = False

        # Background rendering data - tile data for current fetch
        self.nt_byte = 0  # Name table byte
        self.at_byte = 0  # Attribute table byte
        self.bg_low_byte = 0  # Background pattern low byte
        self.bg_high_byte = 0  # Background pattern high byte

        # Background shift registers (16-bit for proper scrolling)
        self.bg_shift_pattern_low = 0
        self.bg_shift_pattern_high = 0
        self.bg_shift_attrib_low = 0
        self.bg_shift_attrib_high = 0
        
        # Background latches for next tile
        self.bg_next_tile_id = 0
        self.bg_next_tile_attr = 0
        self.bg_next_tile_lsb = 0
        self.bg_next_tile_msb = 0

        # Sprite rendering (refactored to use secondary OAM + shift registers)
        self.sprite_count = 0  # Number of active sprites on current scanline
        # Secondary OAM for sprite selection of NEXT scanline (up to 8 sprites * 4 bytes)
        self.secondary_oam = [0xFF] * 32
        # Latched sprite data for current scanline
        self.prep_sprite_indices = [0] * 8
        self.prep_sprite_x = [0] * 8
        self.prep_sprite_attr = [0] * 8
        self.prep_sprite_tile = [0] * 8
        self.prep_sprite_row_low = [0] * 8
        self.prep_sprite_row_high = [0] * 8
        # Active shift registers & counters
        self.sprite_shift_low = [0] * 8
        self.sprite_shift_high = [0] * 8
        self.sprite_latch_attr = [0] * 8
        self.sprite_latch_x = [0] * 8  # X counters delay shifting until zero
        self.sprite_is_sprite0 = [False] * 8

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
        self.END_DOT = 340
        
        # Region-specific scanlines - CRITICAL FIX!
        if region == 'PAL':
            self.SCANLINES_PER_FRAME = 311  # PAL
        else:
            self.SCANLINES_PER_FRAME = 262  # NTSC - FIXED: Must be 262 to include VBlank scanlines!

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
        
        # PPU open bus with decay functionality
        self.bus = 0  # PPU open bus value
        self.bus_decay_timer = [0] * 8  # Decay timer for each bit (in CPU cycles)
        self.BUS_DECAY_TIME = 600000  # ~600ms in CPU cycles (at 1.79MHz)

        # Sprite evaluation cycle-accurate state (new)
        self.sprite_eval_phase = 0  # 0=idle,1=clear secondary,2=scan primary
        self.sprite_eval_index = 0  # Primary OAM index (0..63)
        self.secondary_index = 0    # Secondary OAM byte pointer (0..31)
        self.sprite_fetch_cycle = 0 # Cycle within pattern fetch window 257-320
        self.eval_scanline_target = 0  # Scanline being prepared (next scanline)
        self._sprite_pattern_buffer_low = [0] * 8
        self._sprite_pattern_buffer_high = [0] * 8
        # Pending sprite data (staged for next scanline before commit)
        self.pending_sprite_count = 0
        self.pending_sprite_indices = [0] * 8
        self.pending_sprite_attr = [0] * 8
        self.pending_sprite_x = [0] * 8
        self.pending_sprite_is_sprite0 = [False] * 8
        # Enable new cycle-accurate evaluation pipeline
        self.use_new_sprite_pipeline = True
        # Experimental toggles for debugging vs reference behaviour
        self.sprite_row_experiment = True  # Try alternate row calc (start = y instead of y+1)
        self._sprite_alt_row_hits = 0
        # Background shift timing experiment: when True, shift BG registers AFTER
        # rendering pixel (closer to real hardware sequence: fetch -> render -> shift)
        # Legacy behavior (False) shifts BEFORE rendering the pixel.
        self.bg_shift_post_render = True

        # One-time logging flags for first writes
        self._logged_ppuctrl_first = False
        self._logged_ppumask_first = False

        # Limit logging of VRAM address/data writes per frame
        self.vram_write_log_count = 0

    def reset(self):
        """Reset PPU to initial state"""
        self.ctrl = 0
        self.mask = 0
        self.status = 0x20  # Start with VBlank flag clear, sprite overflow set (for compatibility)
        self.oam_addr = 0
        self.v = 0
        self.t = 0
        self.x = 0
        self.w = 0
        self.scanline = 240  # Start in post-render scanline so we go through VBlank properly
        self.cycle = 0
        self.frame = 0
        self.odd_frame = False

        # Clear memory
        self.vram = [0] * 0x4000
        self.palette_ram = [0] * 0x20
        self.oam = [0] * 0x100

        self.buffer = 0
        self.bus = 0
        self.bus_decay_timer = [0] * 8  # Reset decay timers
        self.vram_write_log_count = 0

    def read_register(self, addr):
        """Read from PPU register with proper open bus behavior"""
        if addr == 0x2002:  # PPUSTATUS
            # PPUSTATUS: bits 7-5 are defined, bits 4-0 are open bus
            result = (self.status & 0xE0) | (self.bus & 0x1F)

            # Reading PPUSTATUS returns current flags then immediately clears VBlank (bit7) only.
            # Sprite 0 hit (bit6) and overflow (bit5) persist until pre-render line dot 1.
            if result & 0x80:
                debug_print(
                    f"PPU: Read PPUSTATUS=0x{result:02X} (VBlank set) scanline={self.scanline} cycle={self.cycle} frame={self.frame}"
                )
            elif result & 0x40:
                debug_print(
                    f"PPU: Read PPUSTATUS=0x{result:02X} (Sprite0Hit) scanline={self.scanline} cycle={self.cycle} frame={self.frame}"
                )

            # Clear VBlank bit (bit7) immediately per hardware behavior
            self.status &= ~0x80
            self.w = 0

            # Refresh bits 7-5 from original value (open bus decay simulation for defined bits)
            self.refresh_bus_bits(0xE0, result)
            return result
            
        elif addr == 0x2004:  # OAMDATA - no open bus bits
            result = self.oam[self.oam_addr]
            self.refresh_bus_bits(0xFF, result)  # All bits refresh the decay register
            return result
            
        elif addr == 0x2007:  # PPUDATA
            result = self.buffer
            if self.v < 0x3F00:
                # Non-palette reads - no open bus bits
                self.buffer = self.read_vram(self.v)
                self.refresh_bus_bits(0xFF, result)  # All bits refresh the decay register
            else:
                # Palette reads - bits 7-6 are open bus
                self.buffer = self.read_vram(self.v - 0x1000)
                palette_value = self.read_vram(self.v)
                result = (self.bus & 0xC0) | (palette_value & 0x3F)
                # Only bits 5-0 refresh the decay register for palette reads
                self.refresh_bus_bits(0x3F, result)

            # Increment VRAM address
            if self.ctrl & 0x04:
                self.v = (self.v + 32) & 0x7FFF
            else:
                self.v = (self.v + 1) & 0x7FFF

            return result
            
        # Write-only registers return open bus
        elif addr in [0x2000, 0x2001, 0x2003, 0x2005, 0x2006]:
            # These registers are write-only and return the open bus value
            # They don't refresh any bits of the decay register
            return self.bus
            
        # Unmapped addresses also return open bus
        return self.bus

    def write_register(self, addr, value):
        """Write to PPU register"""
        # All write operations refresh all bits of the bus
        self.refresh_bus_bits(0xFF, value)

        if addr == 0x2000:  # PPUCTRL
            old_ctrl = self.ctrl
            self.ctrl = value
            self.t = (self.t & 0xF3FF) | ((value & 0x03) << 10)
            # Debug PPUCTRL writes, especially background pattern table selection
            if (old_ctrl & self.BG_TABLE) != (value & self.BG_TABLE):
                bg_table = (
                    "1 (0x1000-0x1FFF)"
                    if (value & self.BG_TABLE)
                    else "0 (0x0000-0x0FFF)"
                )
                debug_print(
                    f"PPU: PPUCTRL background pattern table changed to {bg_table}, ctrl=0x{value:02X}, frame={self.frame}"
                )
            if self.frame < 10:
                sp_table = "1 (0x1000)" if (value & self.SPRITE_TABLE) else "0 (0x0000)"
                nmi = 'on' if (value & 0x80) else 'off'
                debug_print(f"PPU: WRITE $2000=0x{value:02X} (BGtbl={(value>>4)&1} SPRtbl={(value>>3)&1} NMI={nmi}) frame={self.frame} scanline={self.scanline} cycle={self.cycle}")
            else:
                # Persistent logging of sprite/background table changes after early init if bits change
                changed_bits = (old_ctrl ^ value) & (self.BG_TABLE | self.SPRITE_TABLE | 0x80)
                if changed_bits:
                    debug_print(
                        f"PPU: WRITE $2000=0x{value:02X} (BGtbl={(value>>4)&1} SPRtbl={(value>>3)&1} NMI={'1' if (value & 0x80) else '0'}) frame={self.frame} sl={self.scanline} cyc={self.cycle} (changed bits)"
                    )
            if not self._logged_ppuctrl_first:
                self._logged_ppuctrl_first = True
                debug_print(f"PPU: FIRST $2000 write value=0x{value:02X} BGtable={(value>>4)&1} SPRtable={(value>>3)&1} NMI={'1' if (value & 0x80) else '0'}")
        elif addr == 0x2001:  # PPUMASK
            old_mask = self.mask
            debug_print(
                f"PPU: Writing mask register: old={self.mask:02x}, new={value:02x}"
            )
            self.mask = value
            # Debug when rendering is enabled/disabled
            if (old_mask & (self.SHOW_BG | self.SHOW_SPRITE)) != (
                value & (self.SHOW_BG | self.SHOW_SPRITE)
            ):
                if value & (self.SHOW_BG | self.SHOW_SPRITE):
                    debug_print(
                        f"PPU: RENDERING ENABLED at frame {self.frame}, mask=0x{value:02X}"
                    )
                else:
                    debug_print(
                        f"PPU: RENDERING DISABLED at frame {self.frame}, mask=0x{value:02X}"
                    )
            if self.frame < 10:
                bg_on = bool(value & self.SHOW_BG)
                spr_on = bool(value & self.SHOW_SPRITE)
                debug_print(f"PPU: WRITE $2001=0x{value:02X} (BG={'on' if bg_on else 'off'} SPR={'on' if spr_on else 'off'}) frame={self.frame} scanline={self.scanline} cycle={self.cycle}")
            if not self._logged_ppumask_first:
                self._logged_ppumask_first = True
                debug_print(f"PPU: FIRST $2001 write value=0x{value:02X}")
        elif addr == 0x2003:  # OAMADDR
            self.oam_addr = value
        elif addr == 0x2004:  # OAMDATA
            self.oam[self.oam_addr] = value
            # Debug sprite 0 writes during early frames
            if self.oam_addr <= 3 and self.frame >= 0 and self.frame < 50:
                sprite_part = ["Y", "Tile", "Attr", "X"][self.oam_addr]
                debug_print(
                    f"PPU: Sprite 0 {sprite_part}={value} written to OAM[{self.oam_addr}], frame={self.frame}"
                )
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
                if self.vram_write_log_count < 64:
                    debug_print(f"PPU: $2006 write high value=0x{value:02X}, t=0x{self.t:04X}")
                    self.vram_write_log_count += 1
            else:
                self.t = (self.t & 0xFF00) | value
                self.v = self.t
                self.w = 0
                if self.vram_write_log_count < 64:
                    debug_print(f"PPU: $2006 write low value=0x{value:02X}, v=0x{self.v:04X}")
                    self.vram_write_log_count += 1
        elif addr == 0x2007:  # PPUDATA
            addr_for_log = self.v
            self.write_vram(self.v, value)

            if self.vram_write_log_count < 64:
                debug_print(f"PPU: $2007 write addr=0x{addr_for_log:04X}, value=0x{value:02X}")
                self.vram_write_log_count += 1

            # Increment VRAM address
            if self.ctrl & 0x04:
                self.v = (self.v + 32) & 0x7FFF
            else:
                self.v = (self.v + 1) & 0x7FFF

    def read_vram(self, addr):
        """Read from PPU VRAM - matches reference implementation"""
        addr = addr & 0x3FFF

        # Update bus like reference implementation
        self.bus = addr


        if addr < 0x2000:
            # Pattern tables - handled by cartridge (CHR ROM/RAM)
            self.bus = self.memory.ppu_read(addr)
            return self.bus
        elif addr < 0x3F00:
            # Name tables - use proper mapping like reference implementation
            # Reference: address = (address & 0xefff) - 0x2000;
            # Reference: ppu->V_RAM[ppu->mapper->name_table_map[address / 0x400] + (address & 0x3ff)]
            addr = (addr & 0xEFFF) - 0x2000
            nametable_index = addr // 0x400  # Which nametable (0-3)
            offset_in_table = addr & 0x3FF  # Offset within that nametable

            # Get mapping from cartridge
            if hasattr(self.memory, "cartridge") and self.memory.cartridge:
                mapped_offset = self.memory.cartridge.name_table_map[nametable_index]
                self.bus = self.vram[mapped_offset + offset_in_table]
            else:
                # Fallback to simple horizontal mirroring
                if addr >= 0x800:
                    addr = addr % 0x800
                self.bus = self.vram[addr]
            return self.bus
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
        """Write to PPU VRAM - matches reference implementation"""
        addr = addr & 0x3FFF

        # Update bus like reference implementation
        self.bus = value

        if addr < 0x2000:
            # Pattern tables - handled by cartridge (CHR ROM/RAM)
            self.memory.ppu_write(addr, value)
        elif addr < 0x3F00:
            # Name tables - use proper mapping like reference implementation
            addr = (addr & 0xEFFF) - 0x2000
            nametable_index = addr // 0x400  # Which nametable (0-3)
            offset_in_table = addr & 0x3FF  # Offset within that nametable

            # Debug VRAM writes during early frames
            if self.frame >= 0 and self.frame < 50 and value != 0:
                debug_print(
                    f"VRAM Write: addr=0x{addr + 0x2000:04X}, nt={nametable_index}, offset=0x{offset_in_table:03X}, value=0x{value:02X}, frame={self.frame}"
                )

            # Get mapping from cartridge
            if hasattr(self.memory, "cartridge") and self.memory.cartridge:
                mapped_offset = self.memory.cartridge.name_table_map[nametable_index]
                self.vram[mapped_offset + offset_in_table] = value
            else:
                # Fallback to simple horizontal mirroring
                if addr >= 0x800:
                    addr = addr % 0x800
                self.vram[addr] = value
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
        # New sprite pipeline phases (runs one scanline ahead) based on current scanline/cycle before rendering fetches.
        if self.use_new_sprite_pipeline:
            self._sprite_pipeline_step()
        # Visible scanlines (0-239)
        if self.scanline < self.VISIBLE_SCANLINES:
            # Sprite evaluation now happens at cycle 257 for NEXT scanline via prepare_sprites
            if self.cycle > 0 and self.cycle <= self.VISIBLE_DOTS:
                # Debug: Check rendering conditions
                if (
                    self.frame >= 70
                    and self.frame <= 72
                    and self.scanline == 0
                    and self.cycle == 1
                ):
                    debug_print(
                        f"PPU step: frame={self.frame}, scanline={self.scanline}, cycle={self.cycle}, mask=0x{self.mask:02x}"
                    )
                    debug_print(
                        f"PPU step: SHOW_BG={self.SHOW_BG}, SHOW_SPRITE={self.SHOW_SPRITE}, mask&check={self.mask & (self.SHOW_BG | self.SHOW_SPRITE)}"
                    )

                # Background tile fetching (may reload upper 8 bits when cycle_in_tile==7)
                if self.mask & self.SHOW_BG:
                    self.fetch_background_data()

                # Render pixel BEFORE shifting if experiment enabled
                if not self.bg_shift_post_render:
                    # Legacy behavior: shift before rendering
                    if self.mask & self.SHOW_BG:
                        self.bg_shift_pattern_low <<= 1
                        self.bg_shift_pattern_high <<= 1
                        self.bg_shift_attrib_low <<= 1
                        self.bg_shift_attrib_high <<= 1
                        self.bg_shift_pattern_low &= 0xFFFF
                        self.bg_shift_pattern_high &= 0xFFFF
                        self.bg_shift_attrib_low &= 0xFFFF
                        self.bg_shift_attrib_high &= 0xFFFF
                
                # Render pixel if rendering is enabled
                if self.mask & (self.SHOW_BG | self.SHOW_SPRITE):
                    self.render_pixel()
                # Post-render shift (new experiment)
                if self.bg_shift_post_render and (self.mask & self.SHOW_BG):
                    self.bg_shift_pattern_low <<= 1
                    self.bg_shift_pattern_high <<= 1
                    self.bg_shift_attrib_low <<= 1
                    self.bg_shift_attrib_high <<= 1
                    self.bg_shift_pattern_low &= 0xFFFF
                    self.bg_shift_pattern_high &= 0xFFFF
                    self.bg_shift_attrib_low &= 0xFFFF
                    self.bg_shift_attrib_high &= 0xFFFF
                else:
                    # Debug: Why isn't rendering enabled?
                    if (
                        self.frame >= 70
                        and self.frame <= 72
                        and self.scanline == 0
                        and self.cycle == 1
                    ):
                        debug_print(
                            f"PPU step: Rendering NOT enabled, mask=0x{self.mask:02x}, required={(self.SHOW_BG | self.SHOW_SPRITE):02x}"
                        )

                # Handle horizontal scrolling - NES timing: increment coarse X at cycles 8,16,...,256 (when (cycle % 8)==0)
                if (self.cycle % 8) == 0 and (self.mask & self.SHOW_BG):
                    self.increment_x()
            # Legacy path: If not using new pipeline, still prepare at 257
            if (not self.use_new_sprite_pipeline) and self.cycle == 257:
                target = self.scanline + 1
                if target == self.VISIBLE_SCANLINES:
                    pass
                elif target == 261:
                    self.prepare_sprites(0)
                elif target < self.VISIBLE_SCANLINES:
                    self.prepare_sprites(target)

            # Increment Y at end of visible area
            elif self.cycle == self.VISIBLE_DOTS + 1 and (self.mask & self.SHOW_BG):
                self.increment_y()

            # Copy X from temp at start of next scanline prep
            elif self.cycle == self.VISIBLE_DOTS + 2 and (
                self.mask & (self.SHOW_BG | self.SHOW_SPRITE)
            ):
                self.copy_x()


        # Post-render scanline (240) - do nothing
        elif self.scanline == self.VISIBLE_SCANLINES:
            pass

        # Increment dots and scanlines FIRST
        prev_scanline = self.scanline
        prev_cycle = self.cycle

        self.cycle += 1
        if self.cycle >= self.DOTS_PER_SCANLINE:
            self.cycle = 0
            self.scanline += 1
            # NTSC: scanlines 0-261 (262 total), where scanlines 241-260 are VBlank
            # Only reset to 0 when we go past the last scanline (261)
            if self.scanline > 261:  # FIXED: Use > 261 instead of >= 262
                self.scanline = 0
                self.frame += 1
                # CRITICAL: Set render flag to true to exit the frame loop
                self.render = True
                debug_print(f"PPU: Frame {self.frame} complete, signaling render=True")

                # Clear sprite zero tracking flag for new frame
                if hasattr(self, '_sprite_zero_set_this_frame'):
                    delattr(self, '_sprite_zero_set_this_frame')

                # Debug information to track the frame transition
                sprite0_y = self.oam[0]
                sprite0_tile = self.oam[1]
                sprite0_x = self.oam[3]
                # Enhanced per-frame summary (no hacks). Include ctrl/mask/status & pattern table selections.
                ctrl = self.ctrl
                mask = self.mask
                status = self.status
                bg_tbl = 1 if (ctrl & self.BG_TABLE) else 0
                spr_tbl = 1 if (ctrl & self.SPRITE_TABLE) else 0
                long_sprite = 1 if (ctrl & self.LONG_SPRITE) else 0
                show_bg = 1 if (mask & self.SHOW_BG) else 0
                show_spr = 1 if (mask & self.SHOW_SPRITE) else 0
                debug_print(
                    f"PPU: New frame start f={self.frame} Sprite0(Y={sprite0_y} Tile=0x{sprite0_tile:02X} X={sprite0_x}) CTRL=0x{ctrl:02X}(BGtbl={bg_tbl} SPRtbl={spr_tbl} 8x16={long_sprite}) MASK=0x{mask:02X}(BG={show_bg} SPR={show_spr}) STATUS=0x{status:02X}"
                )
                # Reset per-frame VRAM write logging limit
                self.vram_write_log_count = 0
                # Prepare sprites for first scanline (0) of new frame
                if not self.use_new_sprite_pipeline:
                    self.prepare_sprites(0)

        # VBlank scanlines (241-260) - CHECK AFTER CYCLE INCREMENT
        if 241 <= self.scanline <= 260:
            if self.scanline == 241 and self.cycle == 1:
                debug_print(
                    f"PPU: Setting VBlank flag at scanline={self.scanline}, cycle={self.cycle}, frame={self.frame}"
                )
                # Set VBlank flag ONLY here (sprite0 hit should NOT be cleared until pre-render line 261, cycle 1)
                old_status = self.status
                self.status |= self.V_BLANK  # Set VBlank flag
                # DO NOT clear SPRITE_0_HIT here (hardware keeps it latched through VBlank)
                debug_print(f"PPU: VBlank flag set (sprite0 hit preserved), old=0x{old_status:02X} new=0x{self.status:02X} frame={self.frame}")
                
                # Mark that VBlank has been set this frame (for debugging)
                self.vblank_set_this_frame = True

                # Check for VBlank NMI transition immediately (before CPU can read status)
                if (self.status & 0x80) and not (old_status & 0x80):
                    if self.ctrl & 0x80:  # NMI enabled
                        debug_print(
                            f"PPU: VBlank NMI triggered immediately! CTRL={self.ctrl:02x}, frame={self.frame}"
                        )
                        # Trigger NMI through the memory system to the NES
                        if hasattr(self.memory, "nes") and hasattr(
                            self.memory.nes, "trigger_nmi"
                        ):
                            self.memory.nes.trigger_nmi()
                        else:
                            debug_print(
                                "PPU: Warning - cannot trigger NMI, no NES reference found"
                            )

        # Pre-render scanline (261) - CHECK AFTER CYCLE INCREMENT
        elif self.scanline == 261:
            if self.cycle == 1:
                # Clear VBlank, Sprite 0 hit, and Sprite Overflow at start of pre-render scanline
                old_status = self.status
                self.status &= ~self.V_BLANK
                if self.status & self.SPRITE_0_HIT:
                    debug_print(f"PPU: Sprite0 hit CLEAR (pre-render) frame={self.frame} old_status=0x{old_status:02X}")
                self.status &= ~self.SPRITE_0_HIT
                self.status &= ~0x20  # Clear sprite overflow
                debug_print(
                    f"PPU: Pre-render clearing flags (VBlank, Sprite0Hit, Overflow), old_status=0x{old_status:02X}, new_status=0x{self.status:02X}, frame={self.frame}"
                )
                
                # Reset VBlank read counter for next frame
                if hasattr(self, 'vblank_read_count'):
                    delattr(self, 'vblank_read_count')

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

            # Skip cycle on odd frames if rendering is enabled (NTSC ONLY)
            elif (
                self.cycle == self.END_DOT - 1
                and self.frame & 1
                and (self.mask & (self.SHOW_BG | self.SHOW_SPRITE))
                and self.region == 'NTSC'  # Only skip for NTSC, not PAL
            ):
                self.cycle += 1

        # Check for oscillation (repeating the same position)
        if prev_scanline == self.scanline and prev_cycle == self.cycle:
            debug_print(
                f"PPU WARNING: Potential oscillation detected at scanline={self.scanline}, cycle={self.cycle}, frame={self.frame}"
            )
            # Force increment to break potential infinite loop
            self.cycle += 1

    def render_pixel(self):
        """Render a single pixel - based on reference implementation"""
        # ALWAYS debug - to confirm this function is called
        if self.frame > 30 and self.scanline == 0 and self.cycle <= 3:
            debug_print(
                f"render_pixel: frame={self.frame}, scanline={self.scanline}, cycle={self.cycle}"
            )

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

        # Background probe around sprite0 test window (temporary diagnostics)
        if (self.frame % 4 == 0) and (28 <= y <= 33) and (80 <= x <= 100):
            debug_print(f"BG PIXEL PROBE: frame={self.frame} sl={y} x={x} bg_before_final={bg_pixel}")

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
            # Both opaque - check priority
            # Sprite 0 hit detection is handled in render_sprites method
            if sprite_priority == 0:
                palette_addr = 0x10 + sprite_palette * 4 + sprite_pixel
            else:
                palette_addr = bg_palette * 4 + bg_pixel

        # Get final color from palette (two-stage lookup like reference)
        color_index = self.palette_ram[palette_addr] & 0x3F
        # Apply grayscale (PPUMASK bit0) - force upper two bits preserved, lower bits masked to 0x30 boundaries? NES: grayscale masks palette index to 0x30 steps by clearing bits 0-1-2? Actually bit0 of PPUMASK forces color emphasis to use only grayscale by AND with 0x30 and OR with bottom? We'll approximate by masking out color bits (retain universal background)."""
        if self.mask & 0x01:  # Grayscale
            color_index &= 0x30 | (color_index & 0x0F)  # simple approximation
        color = self.nes_palette[color_index]
        # Color emphasis bits 5-7 of PPUMASK adjust RGB output (approximate)
        if self.mask & 0xE0:
            r = (color & 0xFF)
            g = (color >> 8) & 0xFF
            b = (color >> 16) & 0xFF
            if self.mask & 0x20:  # Emphasize red
                r = min(255, int(r * 1.1))
            if self.mask & 0x40:  # Emphasize green
                g = min(255, int(g * 1.1))
            if self.mask & 0x80:  # Emphasize blue
                b = min(255, int(b * 1.1))
            color = (color & 0xFF000000) | (b << 16) | (g << 8) | r
        # Debug output for first few pixels to see what's being rendered
        if self.frame >= 34 and self.frame < 36 and y < 3 and x < 10:
            debug_print(
                f"Pixel ({x},{y}): bg={bg_pixel}, sprite={sprite_pixel}, mask=0x{self.mask:02x}, palette_addr=0x{palette_addr:02X}, final_color=0x{color:08X}"
            )

        # Additional debug to confirm render_pixel is being called
        if self.frame == 71 and y == 0 and x == 0:
            debug_print(
                f"render_pixel called at frame {self.frame}, mask=0x{self.mask:02x}, bg_enabled={bool(self.mask & self.SHOW_BG)}, sprite_enabled={bool(self.mask & self.SHOW_SPRITE)}"
            )

        # Debug output for first few pixels to see what's being rendered
        # Focused probe: region where sprite0 overlap expected (approx x 88-94, y 30-32)
        if (self.frame >= 31) and (30 <= y <= 32) and (88 <= x <= 94) and (self.frame % 29 == 2):
            debug_print(
                f"PPU PROBE: frame={self.frame} x={x} y={y} bg_pixel={bg_pixel} sprite_pixel={sprite_pixel} fineX={self.x} v=0x{self.v:04X} shift_low=0x{self.bg_shift_pattern_low:04X} shift_high=0x{self.bg_shift_pattern_high:04X} attr_low=0x{self.bg_shift_attrib_low:04X} attr_high=0x{self.bg_shift_attrib_high:04X}"
            )
        # Relaxed probe: always log a couple early frames (31-36) without modulus filter
        if (31 <= self.frame <= 36) and (30 <= y <= 32) and (88 <= x <= 94):
            debug_print(
                f"PPU PROBE2: frame={self.frame} x={x} y={y} bg_pixel={bg_pixel} sprite_pixel={sprite_pixel} fineX={self.x} v=0x{self.v:04X} shift_low=0x{self.bg_shift_pattern_low:04X} shift_high=0x{self.bg_shift_pattern_high:04X} attr_low=0x{self.bg_shift_attrib_low:04X} attr_high=0x{self.bg_shift_attrib_high:04X}"
            )

        # Store pixel in screen buffer
        self.screen[y * 256 + x] = color

    def render_background(self):
        """Render background pixel using shift registers - proper NES PPU implementation"""
        if not (self.mask & self.SHOW_BG):
            return 0
            
        x = self.cycle - 1
        
        # Check left 8 pixels clipping
        if x < 8 and not (self.mask & self.SHOW_BG_8):
            return 0
        
        # CRITICAL FIX: Extract from the MSB (bit 15) of the shift registers
        # The NES PPU always extracts from bit 15 and shifts the registers left each cycle
        # Fine X scroll determines how much to offset the extraction
        
        # Use fine X scroll to select bit (hardware extracts MSB then shifts; emulate by offsetting read)
        fine_x = self.x & 0x7
        tap_index = 15 - fine_x  # Which bit we are sampling this cycle
        pattern_low_bit = (self.bg_shift_pattern_low >> tap_index) & 1
        pattern_high_bit = (self.bg_shift_pattern_high >> tap_index) & 1
        pattern_pixel = pattern_low_bit | (pattern_high_bit << 1)

        if pattern_pixel == 0:
            # Extra diagnostic: if raw shift registers have any non-zero high bits about to scroll out while pixel ends up 0
            if (24 <= self.scanline <= 50) and (70 <= x <= 140) and (28 <= self.frame <= 90):
                raw_low = self.bg_shift_pattern_low
                raw_high = self.bg_shift_pattern_high
                # Determine upcoming 4 bits (current tap and next three) for visibility
                window_mask = 0
                for i in range(4):
                    idx = tap_index - i
                    if 0 <= idx <= 15:
                        window_mask |= 1 << idx
                upcoming_low = (raw_low & window_mask) >> max(tap_index-3,0)
                upcoming_high = (raw_high & window_mask) >> max(tap_index-3,0)
                if (raw_low | raw_high) & 0xFFFF:
                    debug_print(
                        f"BG ZERO DIAG: f={self.frame} sl={self.scanline} x={x} cyc={self.cycle} fineX={fine_x} tap={tap_index} low=0x{raw_low:04X} high=0x{raw_high:04X} upLow=0x{upcoming_low:X} upHigh=0x{upcoming_high:X} atL=0x{self.bg_shift_attrib_low:04X} atH=0x{self.bg_shift_attrib_high:04X} v=0x{self.v:04X}"
                    )
            return 0
        else:
            # Optional positive diagnostic to correlate when BG actually non-zero near sprite0 region
            if (24 <= self.scanline <= 50) and (70 <= x <= 140) and (28 <= self.frame <= 90) and (self.frame % 8 == 0):
                debug_print(
                    f"BG NONZERO: f={self.frame} sl={self.scanline} x={x} cyc={self.cycle} fineX={fine_x} tap={tap_index} pix={pattern_pixel} low=0x{self.bg_shift_pattern_low:04X} high=0x{self.bg_shift_pattern_high:04X} v=0x{self.v:04X}"
                )
        attrib_low_bit = (self.bg_shift_attrib_low >> (15 - fine_x)) & 1
        attrib_high_bit = (self.bg_shift_attrib_high >> (15 - fine_x)) & 1
        palette_index = attrib_low_bit | (attrib_high_bit << 1)

        return pattern_pixel | (palette_index << 2)

    def render_sprites(self, bg_pixel):
        """Render sprite pixel using prepared shift registers and x counters."""
        if not (self.mask & self.SHOW_SPRITE) or self.sprite_count == 0:
            return 0
        x = self.cycle - 1
        bg_pix = bg_pixel
        for i in range(self.sprite_count):
            if self.sprite_latch_x[i] > 0:
                self.sprite_latch_x[i] -= 1
                continue
            attr = self.sprite_latch_attr[i]
            # Always shift left; horizontal flip handled during preprocessing when pattern bytes loaded
            pixel_low = (self.sprite_shift_low[i] >> 7) & 1
            pixel_high = (self.sprite_shift_high[i] >> 7) & 1
            self.sprite_shift_low[i] = (self.sprite_shift_low[i] << 1) & 0xFF
            self.sprite_shift_high[i] = (self.sprite_shift_high[i] << 1) & 0xFF
            pixel = pixel_low | (pixel_high << 1)
            if pixel == 0:
                continue
            palette = attr & 0x3
            priority = (attr >> 5) & 1
            is_sprite0 = self.sprite_is_sprite0[i]
            # Sprite0 hit
            overlap_conditions = (
                is_sprite0
                and pixel > 0
                and bg_pix > 0
                and x < 255
                and (self.mask & self.SHOW_BG)
                and (self.mask & self.SHOW_SPRITE)
                and not (self.status & self.SPRITE_0_HIT)
                and not (x < 8 and not (self.mask & self.SHOW_BG_8))
                and not (x < 8 and not (self.mask & self.SHOW_SPRITE_8))
            )
            # General sprite0 pixel probe (even if BG transparent) to confirm sprite rendering output
            if is_sprite0 and pixel > 0 and (0 <= self.scanline < 240) and (0 <= x < 256) and (self.frame % 4 == 0):
                debug_print(f"SPR0 PIXEL PROBE: frame={self.frame} sl={self.scanline} x={x} sprPix={pixel} bgPix={bg_pix} attr=0x{attr:02X}")
            # Overlap probe before setting hit - broaden region to catch any potential overlap
            if is_sprite0 and pixel > 0 and bg_pix > 0 and (0 <= self.scanline < 240) and (0 <= x < 256) and not (self.status & self.SPRITE_0_HIT):
                debug_print(f"SPR0 OVERLAP PROBE: frame={self.frame} sl={self.scanline} x={x} sprPix={pixel} bgPix={bg_pix} cond={'yes' if overlap_conditions else 'no'} attr=0x{attr:02X}")
            if overlap_conditions:
                self.status |= self.SPRITE_0_HIT
                self.sprite_zero_hit = True
                debug_print(
                    f"PPU: Sprite0 hit SET frame={self.frame} x={x} y={self.scanline} spr_pixel={pixel} bg_pixel={bg_pix} attr=0x{attr:02X}"
                )
            # Forced hit experiment: if we see sprite0 pixel in typical title overlap band but bgPix==0, optionally set hit to test freeze logic
            elif is_sprite0 and pixel > 0 and (28 <= self.scanline <= 33) and (80 <= x <= 100) and (self.mask & self.SHOW_BG) and (self.mask & self.SHOW_SPRITE) and not (self.status & self.SPRITE_0_HIT):
                # DO NOT set by default; toggle flag for targeted test
                if hasattr(self, 'force_sprite0_hit_test') and self.force_sprite0_hit_test:
                    self.status |= self.SPRITE_0_HIT
                    debug_print(f"FORCED SPR0 HIT: frame={self.frame} sl={self.scanline} x={x} sprPix={pixel} bgPix={bg_pix}")
            return pixel | (palette << 2) | (priority << 5) | (is_sprite0 << 6)
        return 0

    def _sprite_pipeline_step(self):
        """Cycle-accurate-ish sprite evaluation and pattern fetch pipeline.
        Operates one scanline ahead: building data for NEXT visible scanline while current scanline is being rendered.
        Phases (approximation):
          Cycles 1-64:   Clear secondary OAM (write 0xFF)
          Cycles 65-256: Evaluate primary OAM, copy up to 8 sprites
          Cycles 257-320: Fetch pattern bytes for selected sprites (4 bytes each logically) -> here simplified to 2 bytes per sprite row
          Cycle 321+:    Idle. At cycle 0 of the NEXT scanline commit buffers into active shift registers.
        This keeps existing shift-register render logic intact.
        """
        # Only active during visible scanlines and pre-render because we prep next line
        sl = self.scanline
        cyc = self.cycle
        if sl >= 240 and sl != 261:
            return  # Skip during post-render + vblank except pre-render

        sprite_height = 16 if (self.ctrl & self.LONG_SPRITE) else 8

        # Determine target scanline we are preparing
        # During visible scanline N we prepare N+1; during pre-render (261) we prepare 0
        if sl == 261:
            target_scanline = 0
        else:
            target_scanline = sl + 1
        preparing_visible = (target_scanline < 240)

        # PHASE 1: Clear secondary OAM cycles 1-64
        if 1 <= cyc <= 64:
            # Each 2 cycles clears one byte in hardware; we approximate clearing all gradually
            if cyc == 1:
                for i in range(32):
                    self.secondary_oam[i] = 0xFF
                self.pending_sprite_count = 0
                debug_print(f"PPU SPR-EVAL: Clear secondary OAM for target sl={target_scanline} frame={self.frame}")
            return

        # Stop if target not visible (we don't need pattern fetch or evaluation for scanline 240+)
        if not preparing_visible:
            return

        # PHASE 2: Primary OAM evaluation cycles 65-256
        if 65 <= cyc <= 256:
            # Each 2 cycles reads a sprite byte in real hardware; we approximate scanning sprites incrementally every 8 cycles per entry
            # We'll emulate one sprite candidate per 8 cycles for rough timing correlation
            if cyc == 65:
                self.sprite_eval_index = 0
                self.pending_sprite_count = 0
                self.sprite_overflow = False
            # Decide if we process a sprite this cycle group
            if (cyc - 65) % 8 == 0 and self.pending_sprite_count < 8 and self.sprite_eval_index < 64:
                i = self.sprite_eval_index
                base = i * 4
                y = self.oam[base]
                start = y + 1
                end = start + sprite_height - 1
                if start <= target_scanline <= end:
                    # Copy sprite into secondary OAM/pending arrays
                    self.pending_sprite_indices[self.pending_sprite_count] = i
                    self.pending_sprite_attr[self.pending_sprite_count] = self.oam[base + 2]
                    self.pending_sprite_x[self.pending_sprite_count] = self.oam[base + 3]
                    self.pending_sprite_is_sprite0[self.pending_sprite_count] = (i == 0)
                    self.pending_sprite_count += 1
                self.sprite_eval_index += 1
            # If we already have 8 sprites, set overflow flag if additional in range appear later
            elif (cyc - 65) % 8 == 0 and self.pending_sprite_count >= 8 and self.sprite_eval_index < 64:
                i = self.sprite_eval_index
                base = i * 4
                y = self.oam[base]
                start = y + 1
                end = start + sprite_height - 1
                if start <= target_scanline <= end:
                    self.status |= 0x20  # Overflow flag
                    self.sprite_overflow = True
                self.sprite_eval_index += 1
            return

        # PHASE 3: Pattern fetch cycles 257-320
        if 257 <= cyc <= 320:
            # Allocate pattern buffers once at cycle 257
            if cyc == 257:
                # Pre-fetch pattern bytes for each selected sprite row
                for slot in range(self.pending_sprite_count):
                    idx = self.pending_sprite_indices[slot]
                    base = idx * 4
                    y = self.oam[base]
                    # Row calculation: classic formula row = target_scanline - (y+1)
                    base_row = target_scanline - (y + 1)
                    if self.sprite_row_experiment:
                        # Alternate: treat sprite Y as top line directly (row = target - y)
                        alt_row = target_scanline - y
                        # Accept row if either formulation within sprite height
                        if 0 <= alt_row < sprite_height and not (0 <= base_row < sprite_height):
                            row = alt_row
                            self._sprite_alt_row_hits += 1
                        else:
                            row = base_row
                    else:
                        row = base_row
                    attr = self.pending_sprite_attr[slot]
                    if attr & 0x80:  # vertical flip
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
                        if self.ctrl & self.SPRITE_TABLE:
                            pattern_addr += 0x1000
                    try:
                        low = self.read_vram(pattern_addr)
                        high = self.read_vram(pattern_addr + 8)
                    except Exception:
                        low = 0
                        high = 0
                    if attr & 0x40:  # hflip
                        low = self.reverse_byte(low)
                        high = self.reverse_byte(high)
                    self._sprite_pattern_buffer_low[slot] = low
                    self._sprite_pattern_buffer_high[slot] = high
                    # Targeted debug for sprite0 pattern row capture (title screen freeze analysis)
                    if idx == 0 and (0 <= target_scanline <= 80):
                        debug_print(f"SPR0 PATFETCH: frame={self.frame} tgt_sl={target_scanline} row={row} tile=0x{tile:02X} low=0x{low:02X} high=0x{high:02X} attr=0x{attr:02X}")
                return
            return

        # COMMIT at cycle 0 of next scanline (after increment) - handled when cycle resets to 0 (previous scanline end)
        # We'll perform commit at cycle 0 before any pixel of new scanline is rendered
        if cyc == 0:  # start of a new scanline (after increment in main loop)
            # When entering a visible scanline, transfer pending data to active registers
            if sl < 240 and preparing_visible:
                self.sprite_count = self.pending_sprite_count
                for i in range(self.sprite_count):
                    self.prep_sprite_indices[i] = self.pending_sprite_indices[i]
                    self.sprite_shift_low[i] = self._sprite_pattern_buffer_low[i]
                    self.sprite_shift_high[i] = self._sprite_pattern_buffer_high[i]
                    self.sprite_latch_attr[i] = self.pending_sprite_attr[i]
                    self.sprite_latch_x[i] = self.pending_sprite_x[i]
                    self.sprite_is_sprite0[i] = self.pending_sprite_is_sprite0[i]
                # Log sprite0 commit specifics early frames of freeze region (no frame modulus now)
                if self.sprite_count and self.prep_sprite_indices[0] == 0 and (0 <= sl <= 120):
                    debug_print(f"SPR0 COMMIT: frame={self.frame} sl={sl} x={self.sprite_latch_x[0]} attr=0x{self.sprite_latch_attr[0]:02X} low=0x{self.sprite_shift_low[0]:02X} high=0x{self.sprite_shift_high[0]:02X} altRowHits={self._sprite_alt_row_hits}")
                # If sprite0 tile is still 0xFF log an OAM snapshot occasionally
                if self.sprite_count and self.oam[1] == 0xFF and (sl % 8 == 0) and (self.frame % 16 == 0):
                    oam_first32 = ' '.join(f"{b:02X}" for b in self.oam[:32])
                    debug_print(f"SPR0 OAM SNAPSHOT frame={self.frame} sl={sl} first32={oam_first32}")
                if self.frame % 47 == 0 and self.sprite_count and sl < 240:
                    debug_print(f"PPU SPR-COMMIT: sl={sl} loaded {self.sprite_count} sprites indices={self.prep_sprite_indices[:self.sprite_count]} frame={self.frame}")
            return

    def prepare_sprites(self, target_scanline):
        """Legacy sprite preparation (single-scanline bulk). Retained as fallback when use_new_sprite_pipeline=False."""
        sprite_height = 16 if self.ctrl & self.LONG_SPRITE else 8
        count = 0
        overflow = False
        for i in range(64):
            base = i * 4
            y = self.oam[base]
            tile = self.oam[base + 1]
            attr = self.oam[base + 2]
            x_pos = self.oam[base + 3]
            start = y + 1
            end = start + sprite_height - 1
            if target_scanline < start or target_scanline > end:
                continue
            if count < 8:
                row = target_scanline - start
                if attr & 0x80:  # vertical flip (handle before addressing) row = (height-1) - row
                    row = (sprite_height - 1) - row
                # Compute pattern address
                if sprite_height == 16:
                    base_tile = tile & 0xFE
                    table = tile & 1
                    tile_half = 0 if row < 8 else 1
                    tile_index = base_tile + tile_half
                    fine_y = row & 7
                    pattern_addr = tile_index * 16 + fine_y + (table * 0x1000)
                else:
                    pattern_addr = tile * 16 + row
                    if self.ctrl & self.SPRITE_TABLE:
                        pattern_addr += 0x1000
                try:
                    low = self.read_vram(pattern_addr)
                    high = self.read_vram(pattern_addr + 8)
                except Exception:
                    low = 0
                    high = 0
                # Horizontal flip preprocessing: reverse bit order if needed so we always shift left later
                if attr & 0x40:
                    low = self.reverse_byte(low)
                    high = self.reverse_byte(high)
                self.prep_sprite_indices[count] = i
                self.sprite_shift_low[count] = low
                self.sprite_shift_high[count] = high
                self.sprite_latch_attr[count] = attr
                self.sprite_latch_x[count] = x_pos
                self.sprite_is_sprite0[count] = (i == 0)
                count += 1
            else:
                overflow = True
                break
        self.sprite_count = count
        if overflow:
            self.status |= 0x20
        else:
            self.status &= ~0x20
        if (self.frame % 30 == 0) and count and target_scanline < 240:
            debug_print(
                f"PPU: Prepared {count} sprites for scanline {target_scanline} indices={self.prep_sprite_indices[:count]}"
            )

    @staticmethod
    def reverse_byte(b: int) -> int:
        """Reverse bit order in a byte (e.g., %00000101 -> %10100000)."""
        b = ((b & 0xF0) >> 4) | ((b & 0x0F) << 4)
        b = ((b & 0xCC) >> 2) | ((b & 0x33) << 2)
        b = ((b & 0xAA) >> 1) | ((b & 0x55) << 1)
        return b

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

    def increment_x(self):
        """Increment coarse X component of v like real PPU"""
        if (self.v & self.COARSE_X) == 31:
            # Wrap coarse X and switch horizontal nametable
            self.v &= ~self.COARSE_X
            self.v ^= 0x400
        else:
            self.v += 1

    # Old evaluate_sprites removed (replaced by prepare_sprites at cycle 257 logic)
        
    def refresh_bus_bits(self, bits_mask, value):
        """Refresh specific bits of the decay register"""
        for bit in range(8):
            if bits_mask & (1 << bit):
                # This bit is being refreshed with a new value
                self.bus = (self.bus & ~(1 << bit)) | (value & (1 << bit))
                # Reset the decay timer for this bit
                self.bus_decay_timer[bit] = self.BUS_DECAY_TIME
                
    def update_bus_decay(self, cpu_cycles_elapsed):
        """Update the decay timers and clear decayed bits"""
        for bit in range(8):
            if self.bus_decay_timer[bit] > 0:
                self.bus_decay_timer[bit] -= cpu_cycles_elapsed
                if self.bus_decay_timer[bit] <= 0:
                    # This bit has decayed to 0
                    self.bus &= ~(1 << bit)
                    self.bus_decay_timer[bit] = 0
                    
    def fetch_background_data(self):
        """Fetch background tile data based on current PPU cycle - NES accurate timing"""
        cycle_in_tile = (self.cycle - 1) % 8
        
        if cycle_in_tile == 0:  # Cycle 1, 9, 17, 25, etc. - Fetch nametable byte
            tile_addr = 0x2000 | (self.v & 0xFFF)
            self.nt_byte = self.read_vram(tile_addr)
            
        elif cycle_in_tile == 2:  # Cycle 3, 11, 19, 27, etc. - Fetch attribute byte
            attr_addr = 0x23C0 | (self.v & 0x0C00) | ((self.v >> 4) & 0x38) | ((self.v >> 2) & 0x07)
            self.at_byte = self.read_vram(attr_addr)
            
        elif cycle_in_tile == 4:  # Cycle 5, 13, 21, 29, etc. - Fetch pattern table low byte
            pattern_addr = (self.nt_byte * 16) + ((self.v >> 12) & 0x7)
            if self.ctrl & self.BG_TABLE:
                pattern_addr += 0x1000
            self.bg_low_byte = self.read_vram(pattern_addr)
            # Extra debug near sprite0 region (scanlines ~24-40) every 32 frames
            if (24 <= self.scanline <= 40) and (80 <= (self.cycle-1) <= 104) and (self.frame % 32 == 0):
                debug_print(f"PPU BG fetch low: frame={self.frame} sl={self.scanline} cyc={self.cycle} nt=0x{self.nt_byte:02X} patt_addr=0x{pattern_addr:04X} low=0x{self.bg_low_byte:02X} v=0x{self.v:04X}")
            # Fallback broad logging once sprite table forced (diagnostic mode) for correlation
            if hasattr(self, '_dumped_tile_ff') and self.frame in (41,42) and (self.cycle-1) < 256 and self.scanline < 50 and (self.cycle % 64 == 5):
                debug_print(f"PPU BG fetch low (broad): frame={self.frame} sl={self.scanline} cyc={self.cycle} nt=0x{self.nt_byte:02X} patt_addr=0x{pattern_addr:04X} low=0x{self.bg_low_byte:02X} v=0x{self.v:04X}")
            
        elif cycle_in_tile == 6:  # Cycle 7, 15, 23, 31, etc. - Fetch pattern table high byte
            pattern_addr = (self.nt_byte * 16) + ((self.v >> 12) & 0x7) + 8
            if self.ctrl & self.BG_TABLE:
                pattern_addr += 0x1000
            self.bg_high_byte = self.read_vram(pattern_addr)
            if (24 <= self.scanline <= 40) and (80 <= (self.cycle-1) <= 104) and (self.frame % 32 == 0):
                debug_print(f"PPU BG fetch high: frame={self.frame} sl={self.scanline} cyc={self.cycle} nt=0x{self.nt_byte:02X} patt_addr=0x{pattern_addr:04X} high=0x{self.bg_high_byte:02X} v=0x{self.v:04X}")
            if hasattr(self, '_dumped_tile_ff') and self.frame in (41,42) and (self.cycle-1) < 256 and self.scanline < 50 and (self.cycle % 64 == 7):
                debug_print(f"PPU BG fetch high (broad): frame={self.frame} sl={self.scanline} cyc={self.cycle} nt=0x{self.nt_byte:02X} patt_addr=0x{pattern_addr:04X} high=0x{self.bg_high_byte:02X} v=0x{self.v:04X}")
            
        elif cycle_in_tile == 7:  # Cycle 8, 16, 24, 32, etc. - Load shift registers
            # CRITICAL FIX: Load the UPPER 8 bits of shift registers with new tile data
            # The NES PPU loads new data into bits 15-8, then shifts it down each cycle
            self.bg_shift_pattern_low = (self.bg_shift_pattern_low & 0x00FF) | (self.bg_low_byte << 8)
            self.bg_shift_pattern_high = (self.bg_shift_pattern_high & 0x00FF) | (self.bg_high_byte << 8)
            
            # Expand attribute bits to fill 8 pixels
            # Extract the 2-bit palette for this tile
            attr_bits = (self.at_byte >> ((self.v >> 4) & 4 | self.v & 2)) & 0x3
            attr_low = 0xFF if (attr_bits & 1) else 0
            attr_high = 0xFF if (attr_bits & 2) else 0
            
            # CRITICAL FIX: Load attribute data into UPPER 8 bits too
            self.bg_shift_attrib_low = (self.bg_shift_attrib_low & 0x00FF) | (attr_low << 8)
            self.bg_shift_attrib_high = (self.bg_shift_attrib_high & 0x00FF) | (attr_high << 8)
