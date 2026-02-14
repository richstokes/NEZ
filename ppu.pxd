# cython: language_level=3
from memory cimport Memory

cdef class PPU:
    cdef public Memory memory
    cdef public str region
    cdef public int ctrl, mask, status, oam_addr, oam_data, scroll, addr, data
    cdef public int v, t, x, w
    cdef public int scanline, cycle, frame
    cdef public bint odd_frame
    cdef public int nt_byte, at_byte, bg_low_byte, bg_high_byte
    cdef public int bg_shift_pattern_low, bg_shift_pattern_high
    cdef public int bg_shift_attrib_low, bg_shift_attrib_high
    cdef public int bg_next_tile_id, bg_next_tile_attr, bg_next_tile_lsb, bg_next_tile_msb
    cdef public int sprite_count
    cdef public int sprite_eval_phase, sprite_eval_index, secondary_index
    cdef public int sprite_fetch_cycle, eval_scanline_target
    cdef public int pending_sprite_count
    cdef public bint sprite_zero_hit, sprite_overflow
    cdef public bint render, rendering_enabled, use_new_sprite_pipeline
    cdef public int buffer, bus
    cdef public int BUS_DECAY_TIME
    cdef public int VISIBLE_SCANLINES, VISIBLE_DOTS, DOTS_PER_SCANLINE, END_DOT
    cdef public int SCANLINES_PER_FRAME
    cdef public int SPRITE_TABLE, BG_TABLE
    cdef public int SHOW_BG_8, SHOW_SPRITE_8, SHOW_BG, SHOW_SPRITE, LONG_SPRITE
    cdef public int SPRITE_0_HIT, V_BLANK, GENERATE_NMI
    cdef public int COARSE_X, COARSE_Y, FINE_Y, HORIZONTAL_BITS, VERTICAL_BITS
    cdef public list vram, palette_ram, oam, screen
    cdef public list nes_palette
    cdef public list bus_decay_timer
    cdef public list secondary_oam
    cdef public list prep_sprite_indices, prep_sprite_x, prep_sprite_attr
    cdef public list prep_sprite_tile, prep_sprite_row_low, prep_sprite_row_high
    cdef public list sprite_shift_low, sprite_shift_high
    cdef public list sprite_latch_attr, sprite_latch_x
    cdef public list sprite_is_sprite0
    cdef public list _sprite_pattern_buffer_low, _sprite_pattern_buffer_high
    cdef public list pending_sprite_indices, pending_sprite_attr
    cdef public list pending_sprite_x, pending_sprite_is_sprite0
    cdef public object cpu

    cdef int _read_vram(self, int addr)
    cdef void _write_vram(self, int addr, int value)
    cdef void _render_pixel_c(self)
    cdef int _render_background_c(self)
    cdef int _render_sprites_c(self, int bg_pixel)
    cdef void _sprite_pipeline_step_c(self)
    cdef void _increment_x_c(self)
    cdef void _increment_y_c(self)
    cdef void _copy_x_c(self)
    cdef void _copy_y_c(self)
    cdef void _fetch_background_data_c(self)
    cpdef void step(self)
