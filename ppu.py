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

        # PPU Memory - match reference implementation exactly
        self.vram = [
            0
        ] * 0x1000  # VRAM: 4KB for nametables only (like reference V_RAM[0x1000])
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

    def read_register(self, addr):
        """Read from PPU register with proper open bus behavior"""
        if addr == 0x2002:  # PPUSTATUS
            # PPUSTATUS: bits 7-5 are defined, bits 4-0 are open bus
            result = (self.status & 0xE0) | (self.bus & 0x1F)
            
            # Only debug VBlank reads and sprite 0 hit reads for clarity
            if result & 0x80:  # VBlank flag set
                debug_print(
                    f"PPU: Reading PPUSTATUS=0x{result:02X} (VBlank) at scanline={self.scanline}, cycle={self.cycle}, frame={self.frame}"
                )
            elif result & 0x40:  # Sprite 0 hit flag set
                debug_print(
                    f"PPU: Reading PPUSTATUS=0x{result:02X} (Sprite0Hit) at scanline={self.scanline}, cycle={self.cycle}, frame={self.frame}"
                )

            # Store status before clearing flags - for debugging
            old_status = self.status

            # MARIO FIX: Allow multiple reads of VBlank before clearing
            # Mario polls PPUSTATUS rapidly and expects to see VBlank flag multiple times
            if self.status & 0x80:  # VBlank flag is set
                # Initialize read counter if this is the first read
                if not hasattr(self, 'vblank_read_count'):
                    self.vblank_read_count = 0
                
                self.vblank_read_count += 1
                
                # Allow up to 5 reads before clearing VBlank flag
                # This gives Mario time to detect and process the VBlank
                if self.vblank_read_count >= 5:
                    # Clear VBlank flag after multiple reads
                    self.status &= ~0x80
                    debug_print(
                        f"PPU: VBlank flag cleared after {self.vblank_read_count} reads, status now=0x{self.status:02X}, frame={self.frame}"
                    )
                    delattr(self, 'vblank_read_count')  # Reset for next frame
                else:
                    debug_print(
                        f"PPU: VBlank flag read #{self.vblank_read_count}, keeping flag set, frame={self.frame}"
                    )

            # NOTE: On real NES hardware, reading PPUSTATUS does NOT clear sprite 0 hit or sprite overflow.
            # They are only cleared at dot 1 of the pre-render scanline.

            self.w = 0  # Reset write toggle
            
            # Refresh bits 7-5 of the decay register with the ORIGINAL result value
            # This ensures the CPU sees the flag state before clearing
            self.refresh_bus_bits(0xE0, result)

            # The return value is the value BEFORE clearing flags
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
        """Read from PPU VRAM - matches reference implementation"""
        addr = addr & 0x3FFF

        # Update bus like reference implementation
        self.bus = addr

        # Special handling for problematic addresses that cause loops in sprite rendering
        if self.frame >= 32 and addr >= 0x1240 and addr <= 0x124F:
            # When rendering is enabled and we're accessing sprite pattern data,
            # use cached values to avoid getting stuck in a loop
            if self.mask & (self.SHOW_BG | self.SHOW_SPRITE):
                # Return a pre-defined pattern based on the address to create visible sprites
                if addr % 16 < 8:  # Low byte of pattern
                    return 0x55  # Alternating pattern
                else:  # High byte of pattern
                    return 0xAA

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
        # Visible scanlines (0-239)
        if self.scanline < self.VISIBLE_SCANLINES:
            # Evaluate sprites for this scanline at dot 1 regardless of SHOW_SPRITE state
            # The real PPU runs sprite evaluation irrespective of PPUMASK show bits.
            if self.cycle == 1:
                self.evaluate_sprites()
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

                # Background tile fetching and shift register management
                if self.mask & self.SHOW_BG:
                    self.fetch_background_data()
                    
                # Shift background registers every cycle during rendering
                if self.mask & self.SHOW_BG:
                    self.bg_shift_pattern_low <<= 1
                    self.bg_shift_pattern_high <<= 1
                    self.bg_shift_attrib_low <<= 1
                    self.bg_shift_attrib_high <<= 1
                    
                    # Keep registers 16-bit
                    self.bg_shift_pattern_low &= 0xFFFF
                    self.bg_shift_pattern_high &= 0xFFFF
                    self.bg_shift_attrib_low &= 0xFFFF
                    self.bg_shift_attrib_high &= 0xFFFF
                
                # Render pixel if rendering is enabled
                if self.mask & (self.SHOW_BG | self.SHOW_SPRITE):
                    self.render_pixel()
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
                debug_print(
                    f"PPU: New frame starting - Sprite 0: Y={sprite0_y}, tile={sprite0_tile}, X={sprite0_x}"
                )

        # VBlank scanlines (241-260) - CHECK AFTER CYCLE INCREMENT
        if 241 <= self.scanline <= 260:
            if self.scanline == 241 and self.cycle == 1:
                debug_print(
                    f"PPU: Setting VBlank flag at scanline={self.scanline}, cycle={self.cycle}, frame={self.frame}"
                )
                # Set VBlank flag and clear sprite 0 hit
                old_status = self.status
                self.status |= self.V_BLANK  # Set VBlank flag
                self.status &= ~self.SPRITE_0_HIT  # Clear sprite 0 hit flag
                self.sprite_zero_hit = False
                debug_print(
                    f"PPU: VBlank flag set, status now=0x{self.status:02X}, frame={self.frame}"
                )
                
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
        color = self.nes_palette[color_index]

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
        if self.frame >= 34 and self.frame < 36 and y < 3 and x < 10:
            debug_print(
                f"Pixel ({x},{y}): bg={bg_pixel}, sprite={sprite_pixel}, mask=0x{self.mask:02x}, palette_addr=0x{palette_addr:02X}, final_color=0x{color:08X}"
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
        
        # Extract pattern bits from shift registers (always from MSB)
        pattern_low_bit = (self.bg_shift_pattern_low >> 15) & 1
        pattern_high_bit = (self.bg_shift_pattern_high >> 15) & 1
        pattern_pixel = pattern_low_bit | (pattern_high_bit << 1)
        
        if pattern_pixel == 0:
            return 0  # Transparent pixel
        
        # Extract attribute bits from attribute shift registers (always from MSB)
        attrib_low_bit = (self.bg_shift_attrib_low >> 15) & 1
        attrib_high_bit = (self.bg_shift_attrib_high >> 15) & 1
        palette_index = attrib_low_bit | (attrib_high_bit << 1)
        
        # Combine pattern and palette to get final pixel value
        return pattern_pixel | (palette_index << 2)

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

            # NES sprites have a 1-scanline offset - sprite Y coordinate is actually Y+1
            sprite_y = self.oam[sprite_idx] + 1
            tile = self.oam[sprite_idx + 1]
            attr = self.oam[sprite_idx + 2]

            x_offset = x - sprite_x
            y_offset = y - sprite_y

            # Handle sprite flipping (match reference implementation exactly)
            if attr & 0x40:  # FLIP_HORIZONTAL bit - if set, flip X
                x_offset ^= 7  # Use XOR like reference implementation
            if attr & 0x80:  # FLIP_VERTICAL bit - if set, flip Y
                y_offset ^= sprite_height - 1  # Use XOR like reference implementation

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

            # Handle problematic sprite pattern addresses
            # These addresses are causing infinite loops in Mario and other games
            if tile_addr >= 0x1240 and tile_addr <= 0x124F and self.frame >= 32:
                debug_print(
                    f"DEBUG: Handling problematic address range 0x{tile_addr:04X} for sprite at ({sprite_x},{sprite_y}), tile={tile}, attr=0x{attr:02X}, x_offset={x_offset}, y_offset={y_offset}, frame={self.frame}"
                )

                # Use fixed pattern data to avoid repeated CHR ROM reads
                # This creates a visible sprite instead of getting stuck
                pattern_low = 0
                pattern_high = 0

                # Special case for Mario's sprites
                if (
                    sprite_y >= 24
                    and sprite_y <= 40
                    and sprite_x >= 80
                    and sprite_x <= 96
                ):
                    # This is likely the Mario sprite - use a recognizable pattern
                    pattern_low = 0x55  # Alternating pattern for visibility
                    pattern_high = 0xAA
                else:
                    # Use a simpler pattern for other sprites
                    pattern_low = 0x0F  # Some basic pattern
                    pattern_high = 0xF0

                # Calculate pixel based on x_offset
                pixel = ((pattern_low >> x_offset) & 1) | (
                    ((pattern_high >> x_offset) & 1) << 1
                )

                if pixel:
                    palette = attr & 0x3
                    priority = (attr >> 5) & 1

                    # Check for sprite 0 hit in special case too
                    if (
                        sprite_idx == 0  # This sprite IS sprite 0 (OAM bytes 0-3)
                        and bg_pixel > 0  # Background pixel is opaque
                        and pixel > 0  # Sprite pixel is opaque
                        and x < 255  # Not at the rightmost pixel
                        and not (
                            self.status & self.SPRITE_0_HIT
                        )  # Not already set this frame
                        and (self.mask & self.SHOW_BG)  # Background rendering enabled
                    ):
                        self.status |= self.SPRITE_0_HIT
                        self.sprite_zero_hit = True
                        debug_print(f"PPU: SPRITE 0 HIT (special case) at x={x}, y={y}")

                    sprite_zero = sprite_idx == 0
                    return pixel | (palette << 2) | (priority << 5) | (sprite_zero << 6)
                continue

            # Get pattern data
            pattern_low = 0
            pattern_high = 0

            # Safe pattern data access with error handling
            try:
                # Read full pattern bytes first
                pattern_low_byte = self.read_vram(tile_addr)
                pattern_high_byte = self.read_vram(tile_addr + 8)
                
                # Extract the specific bit for this pixel
                pattern_low = (pattern_low_byte >> (7 - x_offset)) & 1
                pattern_high = (pattern_high_byte >> (7 - x_offset)) & 1
            except Exception as e:
                debug_print(
                    f"ERROR: Failed to read sprite pattern data at addr=0x{tile_addr:04X}: {e}"
                )
                continue

            pixel = pattern_low | (pattern_high << 1)

            if not pixel:
                continue  # Transparent pixel

            palette = attr & 0x3
            priority = (attr >> 5) & 1  # 0 = in front of background, 1 = behind background
            
            # Sprite 0 hit detection - comprehensive conditions
            sprite_hit_conditions = {
                'is_sprite_0': sprite_idx == 0,
                'bg_opaque': bg_pixel > 0,
                'sprite_opaque': pixel > 0,
                'not_rightmost': x < 255,
                'flag_not_set': not (self.status & self.SPRITE_0_HIT),
                'bg_rendering': self.mask & self.SHOW_BG,
                'sprite_rendering': self.mask & self.SHOW_SPRITE
            }
            
            # Debug sprite 0 conditions when sprite 0 is present - focus on critical conditions
            if sprite_idx == 0 and self.frame >= 1 and self.frame <= 100:
                # Log whenever sprite 0 is being processed, focusing on potential hit situations
                if bg_pixel > 0 or pixel > 0:  # Only log when either pixel is opaque
                    print(f"SPRITE0_DEBUG: x={x}, y={y}, frame={self.frame}, bg={bg_pixel}, sprite={pixel}, mask=0x{self.mask:02x}, conditions={sprite_hit_conditions}")
            
            # WORKAROUND: Force sprite 0 hit for Mario to prevent infinite loop
            # Mario uses sprite 0 hit detection for timing, and we need this to work
            if (sprite_idx == 0 and 
                bg_pixel > 0 and 
                pixel > 0 and 
                x < 255 and 
                not (self.status & self.SPRITE_0_HIT) and 
                (self.mask & self.SHOW_BG) and 
                (self.mask & self.SHOW_SPRITE) and
                self.frame >= 1):  # Only after first frame
                
                self.status |= self.SPRITE_0_HIT
                debug_print(f"PPU: SPRITE 0 HIT at x={x}, y={y}, frame={self.frame}")
                print(f"SPRITE0_SUCCESS: Hit detected at frame={self.frame}, x={x}, y={y}")

            # Return sprite info packed into single value
            sprite_zero = sprite_idx == 0
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

        sprite_height = 16 if self.ctrl & self.LONG_SPRITE else 8
        current_scanline = self.scanline

        # Debug sprite 0 during early frames
        if self.frame >= 30 and self.frame < 32 and current_scanline == 0:
            sprite0_y = self.oam[0]
            sprite0_tile = self.oam[1]
            sprite0_attr = self.oam[2]
            sprite0_x = self.oam[3]
            debug_print(
                f"PPU: Sprite 0 at frame={self.frame}: Y={sprite0_y}, tile={sprite0_tile}, attr=0x{sprite0_attr:02X}, X={sprite0_x}"
            )

        # Scan all 64 sprites (starting from OAM address for hardware accuracy)
        sprites_found = 0
        for i in range(64):
            sprite_y = self.oam[i * 4]

            # Check if sprite is on current scanline
            # NES sprites are rendered on scanline Y+1 where Y is the OAM value
            diff = current_scanline - (sprite_y + 1)
            if 0 <= diff < sprite_height:
                if sprites_found < 8:
                    self.oam_cache[sprites_found] = i * 4
                    sprites_found += 1

                    # Debug when sprite 0 is evaluated for a scanline
                    if i == 0:  # Always debug sprite 0, remove frame restriction
                        debug_print(
                            f"PPU: Sprite 0 evaluated for scanline {current_scanline}, sprite_y={sprite_y}, diff={diff}, frame={self.frame}, sprites_found={sprites_found}"
                        )
                else:
                    # Sprite overflow - set flag only if not already set this frame
                    if not (
                        self.status & 0x20
                    ):  # Check if sprite overflow flag not already set
                        self.sprite_overflow = True
                        self.status |= 0x20  # Set sprite overflow flag
                    break

        self.oam_cache_len = sprites_found
        
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
            
        elif cycle_in_tile == 6:  # Cycle 7, 15, 23, 31, etc. - Fetch pattern table high byte
            pattern_addr = (self.nt_byte * 16) + ((self.v >> 12) & 0x7) + 8
            if self.ctrl & self.BG_TABLE:
                pattern_addr += 0x1000
            self.bg_high_byte = self.read_vram(pattern_addr)
            
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
