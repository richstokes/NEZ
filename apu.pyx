# cython: boundscheck=False, wraparound=False, cdivision=True, language_level=3
"""
NES Audio Processing Unit (APU) — Cython accelerated.
Drop-in replacement for apu.py.
"""

try:
    import sdl2
    SDL2_AVAILABLE = True
except ImportError:
    SDL2_AVAILABLE = False

import ctypes
import struct


# ───── Divider ─────
cdef class Divider:
    cdef public int period, counter, step, limit, from_val
    cdef public bint loop

    def __init__(self):
        self.period = 0
        self.counter = 0
        self.step = 0
        self.limit = 0
        self.from_val = 0
        self.loop = True

    cdef bint clock_c(self):
        if self.counter <= 0:
            self.counter = self.period
            if self.step >= self.limit:
                self.step = self.from_val if self.loop else self.limit
            else:
                self.step += 1
            return True
        else:
            self.counter -= 1
            return False

    def clock(self):
        return self.clock_c()


# ───── Envelope ─────
cdef class Envelope:
    cdef public int period, step
    cdef public bint loop, start
    cdef public Divider divider

    def __init__(self):
        self.period = 0
        self.step = 15
        self.loop = False
        self.start = False
        self.divider = Divider()

    cdef void clock_c(self):
        if self.start:
            self.start = False
            self.step = 15
            self.divider.period = self.period
            self.divider.counter = self.period
        elif self.divider.clock_c():
            if self.step > 0:
                self.step -= 1
            elif self.loop:
                self.step = 15

    def clock(self):
        self.clock_c()


# ───── Sweep ─────
cdef class Sweep:
    cdef public bint enabled, negate, reload
    cdef public int period, shift
    cdef public Divider divider

    def __init__(self):
        self.enabled = False
        self.period = 0
        self.negate = False
        self.shift = 0
        self.reload = False
        self.divider = Divider()

    cdef int target_period_c(self, PulseChannel pulse):
        cdef int change = pulse.timer.period >> self.shift
        if self.negate:
            if pulse.channel == 1:
                return pulse.timer.period - change - 1
            else:
                return pulse.timer.period - change
        else:
            return pulse.timer.period + change

    cdef void clock_c(self, PulseChannel pulse):
        if self.divider.clock_c():
            if self.enabled and self.shift > 0 and not pulse.muted:
                target = self.target_period_c(pulse)
                if 8 <= target <= 0x7FF and pulse.timer.period >= 8:
                    pulse.timer.period = target

        if self.reload:
            self.divider.period = self.period
            self.divider.counter = self.period
            self.reload = False

    def clock(self, pulse):
        self.clock_c(pulse)

    def target_period(self, pulse):
        return self.target_period_c(pulse)


# ───── PulseChannel ─────
# Duty cycle tables as module-level C arrays
cdef int DUTY_0[8]
cdef int DUTY_1[8]
cdef int DUTY_2[8]
cdef int DUTY_3[8]
DUTY_0[:] = [0, 1, 0, 0, 0, 0, 0, 0]
DUTY_1[:] = [0, 1, 1, 0, 0, 0, 0, 0]
DUTY_2[:] = [0, 1, 1, 1, 1, 0, 0, 0]
DUTY_3[:] = [1, 0, 0, 1, 1, 1, 1, 1]

cdef class PulseChannel:
    cdef public int channel, length_counter, duty, duty_step
    cdef public bint enabled, length_halt, constant_volume, muted
    cdef public Divider timer
    cdef public Envelope envelope
    cdef public Sweep sweep

    # Keep class-level for Python compatibility
    DUTY_CYCLES = [
        [0, 1, 0, 0, 0, 0, 0, 0],
        [0, 1, 1, 0, 0, 0, 0, 0],
        [0, 1, 1, 1, 1, 0, 0, 0],
        [1, 0, 0, 1, 1, 1, 1, 1],
    ]

    def __init__(self, int channel_num):
        self.channel = channel_num
        self.enabled = False
        self.length_counter = 0
        self.length_halt = False
        self.timer = Divider()
        self.timer.limit = 7
        self.timer.loop = True
        self.duty = 0
        self.duty_step = 0
        self.envelope = Envelope()
        self.constant_volume = False
        self.sweep = Sweep()
        self.muted = False

    cdef void clock_timer_c(self):
        if self.timer.clock_c():
            self.duty_step = (self.duty_step + 1) & 7

    cdef void clock_envelope_c(self):
        self.envelope.clock_c()

    cdef void clock_sweep_c(self):
        self.sweep.clock_c(self)
        self.update_mute_c()

    cdef void clock_length_c(self):
        if not self.length_halt and self.length_counter > 0:
            self.length_counter -= 1

    cdef void update_mute_c(self):
        cdef int target
        if self.timer.period < 8:
            self.muted = True
        else:
            target = self.sweep.target_period_c(self)
            self.muted = target > 0x7FF

    cdef int output_c(self):
        cdef int duty_out
        if not self.enabled or self.length_counter == 0 or self.muted:
            return 0
        # Use C arrays for duty lookup
        if self.duty == 0:
            duty_out = DUTY_0[self.duty_step]
        elif self.duty == 1:
            duty_out = DUTY_1[self.duty_step]
        elif self.duty == 2:
            duty_out = DUTY_2[self.duty_step]
        else:
            duty_out = DUTY_3[self.duty_step]
        if duty_out == 0:
            return 0
        if self.constant_volume:
            return self.envelope.period
        else:
            return self.envelope.step

    def clock_timer(self):
        self.clock_timer_c()

    def clock_envelope(self):
        self.clock_envelope_c()

    def clock_sweep(self):
        self.clock_sweep_c()

    def clock_length(self):
        self.clock_length_c()

    def update_mute(self):
        self.update_mute_c()

    def output(self):
        return self.output_c()


# ───── TriangleChannel ─────
cdef int TRIANGLE_SEQ[32]
TRIANGLE_SEQ[:] = [15,14,13,12,11,10,9,8,7,6,5,4,3,2,1,0,
                   0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15]

cdef class TriangleChannel:
    cdef public int length_counter, linear_counter, linear_reload, sequence_step
    cdef public bint enabled, length_halt, linear_reload_flag
    cdef public Divider timer

    TRIANGLE_SEQUENCE = [15,14,13,12,11,10,9,8,7,6,5,4,3,2,1,0,
                         0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15]

    def __init__(self):
        self.enabled = False
        self.length_counter = 0
        self.length_halt = False
        self.linear_counter = 0
        self.linear_reload = 0
        self.linear_reload_flag = False
        self.timer = Divider()
        self.timer.limit = 31
        self.timer.loop = True
        self.sequence_step = 0

    cdef void clock_timer_c(self):
        if self.linear_counter > 0 and self.length_counter > 0:
            if self.timer.clock_c():
                self.sequence_step = (self.sequence_step + 1) & 31

    cdef void clock_linear_c(self):
        if self.linear_reload_flag:
            self.linear_counter = self.linear_reload
        elif self.linear_counter > 0:
            self.linear_counter -= 1
        if not self.length_halt:
            self.linear_reload_flag = False

    cdef void clock_length_c(self):
        if not self.length_halt and self.length_counter > 0:
            self.length_counter -= 1

    cdef int output_c(self):
        if (not self.enabled or self.length_counter == 0 or
                self.timer.period < 2 or self.linear_counter == 0):
            return 0
        return TRIANGLE_SEQ[self.sequence_step]

    def clock_timer(self):
        self.clock_timer_c()

    def clock_linear(self):
        self.clock_linear_c()

    def clock_length(self):
        self.clock_length_c()

    def output(self):
        return self.output_c()


# ───── NoiseChannel ─────
cdef int NOISE_NTSC[16]
cdef int NOISE_PAL[16]
NOISE_NTSC[:] = [4,8,16,32,64,96,128,160,202,254,380,508,762,1016,2034,4068]
NOISE_PAL[:] = [4,8,14,30,60,88,118,148,188,236,354,472,708,944,1890,3778]

cdef class NoiseChannel:
    cdef public int length_counter, shift_register
    cdef public bint enabled, length_halt, constant_volume, mode, pal_mode
    cdef public Divider timer
    cdef public Envelope envelope

    NOISE_PERIODS_NTSC = [4,8,16,32,64,96,128,160,202,254,380,508,762,1016,2034,4068]
    NOISE_PERIODS_PAL = [4,8,14,30,60,88,118,148,188,236,354,472,708,944,1890,3778]

    def __init__(self, bint pal_mode=False):
        self.enabled = False
        self.length_counter = 0
        self.length_halt = False
        self.pal_mode = pal_mode
        self.timer = Divider()
        self.envelope = Envelope()
        self.constant_volume = False
        self.shift_register = 1
        self.mode = False

    cdef void clock_timer_c(self):
        cdef int feedback
        if self.timer.clock_c():
            if self.mode:
                feedback = (self.shift_register & 1) ^ ((self.shift_register >> 6) & 1)
            else:
                feedback = (self.shift_register & 1) ^ ((self.shift_register >> 1) & 1)
            self.shift_register >>= 1
            self.shift_register |= feedback << 14

    cdef void clock_envelope_c(self):
        self.envelope.clock_c()

    cdef void clock_length_c(self):
        if not self.length_halt and self.length_counter > 0:
            self.length_counter -= 1

    cdef int output_c(self):
        if not self.enabled or self.length_counter == 0 or (self.shift_register & 1):
            return 0
        if self.constant_volume:
            return self.envelope.period
        else:
            return self.envelope.step

    def clock_timer(self):
        self.clock_timer_c()

    def clock_envelope(self):
        self.clock_envelope_c()

    def clock_length(self):
        self.clock_length_c()

    def set_period(self, int index):
        if self.pal_mode:
            self.timer.period = NOISE_PAL[index & 0xF]
        else:
            self.timer.period = NOISE_NTSC[index & 0xF]
        self.timer.counter = self.timer.period

    def output(self):
        return self.output_c()


# ───── DMCChannel ─────
cdef int DMC_NTSC[16]
cdef int DMC_PAL_T[16]
DMC_NTSC[:] = [428,380,340,320,286,254,226,214,190,160,142,128,106,84,72,54]
DMC_PAL_T[:] = [398,354,316,298,276,236,210,198,176,148,132,118,98,78,66,50]

cdef class DMCChannel:
    cdef public bint enabled, irq_enable, irq_flag, loop, silence, sample_buffer_empty, pal_mode
    cdef public int output_level, shift_register, bits_remaining
    cdef public int sample_address, sample_length, current_address, bytes_remaining, sample_buffer
    cdef public Divider timer
    cdef public object memory

    DMC_PERIODS_NTSC = [428,380,340,320,286,254,226,214,190,160,142,128,106,84,72,54]
    DMC_PERIODS_PAL = [398,354,316,298,276,236,210,198,176,148,132,118,98,78,66,50]

    def __init__(self, bint pal_mode=False, memory=None):
        self.enabled = False
        self.pal_mode = pal_mode
        self.memory = memory
        self.irq_enable = False
        self.irq_flag = False
        self.loop = False
        self.timer = Divider()
        self.output_level = 0
        self.shift_register = 0
        self.bits_remaining = 0
        self.silence = True
        self.sample_address = 0xC000
        self.sample_length = 1
        self.current_address = 0xC000
        self.bytes_remaining = 0
        self.sample_buffer = 0
        self.sample_buffer_empty = True

    cdef void clock_output_c(self):
        if self.bits_remaining == 0:
            self.bits_remaining = 8
            if self.sample_buffer_empty:
                self.silence = True
            else:
                self.silence = False
                self.shift_register = self.sample_buffer
                self.sample_buffer_empty = True
                self.fill_sample_buffer()

        if not self.silence:
            if self.shift_register & 1:
                if self.output_level <= 125:
                    self.output_level += 2
            else:
                if self.output_level >= 2:
                    self.output_level -= 2

        self.shift_register >>= 1
        self.bits_remaining -= 1

    cdef void clock_timer_c(self):
        if self.timer.clock_c():
            self.clock_output_c()

    def clock_timer(self):
        self.clock_timer_c()

    def clock_output(self):
        self.clock_output_c()

    def fill_sample_buffer(self):
        if self.sample_buffer_empty and self.bytes_remaining > 0:
            if self.memory:
                if hasattr(self.memory, "nes") and hasattr(self.memory.nes, "cpu"):
                    if hasattr(self.memory.nes.cpu, "add_dma_cycles"):
                        self.memory.nes.cpu.add_dma_cycles(3)

                self.sample_buffer = self.memory.read(self.current_address)
                self.sample_buffer_empty = False

                self.current_address += 1
                if self.current_address > 0xFFFF:
                    self.current_address = 0x8000

                self.bytes_remaining -= 1

                if self.bytes_remaining == 0:
                    if self.loop:
                        self.restart()
                    elif self.irq_enable:
                        if not self.irq_flag:
                            self.irq_flag = True
                            if hasattr(self.memory, "nes") and hasattr(self.memory.nes, "cpu"):
                                if hasattr(self.memory.nes.cpu, "trigger_interrupt"):
                                    self.memory.nes.cpu.trigger_interrupt("IRQ")

    def restart(self):
        self.current_address = self.sample_address
        self.bytes_remaining = self.sample_length

    def set_period(self, int index):
        if self.pal_mode:
            self.timer.period = DMC_PAL_T[index & 0xF] - 1
        else:
            self.timer.period = DMC_NTSC[index & 0xF] - 1
        self.timer.counter = self.timer.period

    def output(self):
        return self.output_level


# ───── FrameSequencer ─────
cdef class FrameSequencer:
    cdef public int mode, step, cycles
    cdef public bint irq_inhibit, irq_flag, reset_sequencer, pal_mode

    def __init__(self, bint pal_mode=False):
        self.mode = 0
        self.irq_inhibit = False
        self.irq_flag = False
        self.step = 0
        self.cycles = 0
        self.reset_sequencer = False
        self.pal_mode = pal_mode

    cdef void clock_quarter_frame_c(self, APU apu):
        apu.pulse1.clock_envelope_c()
        apu.pulse2.clock_envelope_c()
        apu.noise.clock_envelope_c()
        apu.triangle.clock_linear_c()

    cdef void clock_half_frame_c(self, APU apu):
        apu.pulse1.clock_length_c()
        apu.pulse1.clock_sweep_c()
        apu.pulse2.clock_length_c()
        apu.pulse2.clock_sweep_c()
        apu.triangle.clock_length_c()
        apu.noise.clock_length_c()

    cdef void clock_c(self, APU apu):
        cdef int c
        if self.reset_sequencer:
            self.reset_sequencer = False
            if self.mode == 1:
                self.clock_quarter_frame_c(apu)
                self.clock_half_frame_c(apu)
            self.cycles = 0
            return

        c = self.cycles
        if self.pal_mode:
            if self.mode == 0:  # 4-step PAL
                if c == 8313:
                    self.clock_quarter_frame_c(apu)
                elif c == 16627:
                    self.clock_quarter_frame_c(apu)
                    self.clock_half_frame_c(apu)
                elif c == 24939:
                    self.clock_quarter_frame_c(apu)
                elif c == 33252:
                    pass
                elif c == 33253:
                    self.clock_quarter_frame_c(apu)
                    self.clock_half_frame_c(apu)
                    if not self.irq_inhibit:
                        if not self.irq_flag:
                            self.irq_flag = True
                            if hasattr(apu.nes, "cpu") and hasattr(apu.nes.cpu, "trigger_interrupt"):
                                apu.nes.cpu.trigger_interrupt("IRQ")
                    self.cycles = 0
                    return
            else:  # 5-step PAL
                if c == 8313:
                    self.clock_quarter_frame_c(apu)
                elif c == 16627:
                    self.clock_quarter_frame_c(apu)
                    self.clock_half_frame_c(apu)
                elif c == 24939:
                    self.clock_quarter_frame_c(apu)
                elif c == 33253:
                    pass
                elif c == 41565:
                    self.clock_quarter_frame_c(apu)
                    self.clock_half_frame_c(apu)
                    self.cycles = 0
                    return
        else:
            if self.mode == 0:  # 4-step NTSC
                if c == 7457:
                    self.clock_quarter_frame_c(apu)
                elif c == 14913:
                    self.clock_quarter_frame_c(apu)
                    self.clock_half_frame_c(apu)
                elif c == 22371:
                    self.clock_quarter_frame_c(apu)
                elif c == 29828:
                    pass
                elif c == 29829:
                    self.clock_quarter_frame_c(apu)
                    self.clock_half_frame_c(apu)
                    if not self.irq_inhibit:
                        if not self.irq_flag:
                            self.irq_flag = True
                            if hasattr(apu.nes, "cpu") and hasattr(apu.nes.cpu, "trigger_interrupt"):
                                apu.nes.cpu.trigger_interrupt("IRQ")
                    self.cycles = 0
                    return
            else:  # 5-step NTSC
                if c == 7457:
                    self.clock_quarter_frame_c(apu)
                elif c == 14913:
                    self.clock_quarter_frame_c(apu)
                    self.clock_half_frame_c(apu)
                elif c == 22371:
                    self.clock_quarter_frame_c(apu)
                elif c == 29829:
                    pass
                elif c == 37281:
                    self.clock_quarter_frame_c(apu)
                    self.clock_half_frame_c(apu)
                    self.cycles = 0
                    return
        self.cycles = c + 1

    def clock(self, apu):
        self.clock_c(apu)

    def clock_quarter_frame(self, apu):
        self.clock_quarter_frame_c(apu)

    def clock_half_frame(self, apu):
        self.clock_half_frame_c(apu)


# ───── APU ─────
cdef int LENGTH_TABLE[32]
LENGTH_TABLE[:] = [10,254,20,2,40,4,80,6,160,8,60,10,14,12,26,14,
                   12,16,24,18,48,20,96,22,192,24,72,26,16,28,32,30]

cdef class APU:
    cdef public object nes
    cdef public bint pal_mode
    cdef public PulseChannel pulse1, pulse2
    cdef public TriangleChannel triangle
    cdef public NoiseChannel noise
    cdef public DMCChannel dmc
    cdef public FrameSequencer frame_sequencer
    cdef public int _cpu_cycle_parity
    cdef public int sample_rate
    cdef public list audio_buffer
    cdef public object audio_stream
    cdef public double cycles_per_sample, cycle_accumulator
    cdef public list pulse_table, tnd_table
    cdef public bint audio_enabled
    cdef public int frame_sample_count

    LENGTH_COUNTER_TABLE = [10,254,20,2,40,4,80,6,160,8,60,10,14,12,26,14,
                            12,16,24,18,48,20,96,22,192,24,72,26,16,28,32,30]

    def __init__(self, nes, bint pal_mode=False):
        self.nes = nes
        self.pal_mode = pal_mode

        self.pulse1 = PulseChannel(1)
        self.pulse2 = PulseChannel(2)
        self.triangle = TriangleChannel()
        self.noise = NoiseChannel(pal_mode)
        self.dmc = DMCChannel(pal_mode, nes.memory)

        self.frame_sequencer = FrameSequencer(pal_mode)

        self._cpu_cycle_parity = 0

        self.sample_rate = 48000
        self.audio_buffer = []
        self.audio_stream = None
        self.audio_enabled = False
        self.frame_sample_count = 0
        self.cycles_per_sample = (1662607.0 if pal_mode else 1789773.0) / self.sample_rate
        self.cycle_accumulator = 0.0

        self.pulse_table = self._create_pulse_table()
        self.tnd_table = self._create_tnd_table()

        self._init_audio()

    def _create_pulse_table(self):
        table = [0.0] * 31
        cdef int i
        for i in range(1, 31):
            table[i] = 95.52 / (8128.0 / i + 100)
        return table

    def _create_tnd_table(self):
        table = [0.0] * 203
        cdef int i
        for i in range(1, 203):
            table[i] = 163.67 / (24329.0 / i + 100)
        return table

    def _init_audio(self):
        pass

    def init_audio_stream(self, audio_stream):
        self.audio_stream = audio_stream
        if self.audio_stream and self.audio_stream != 0:
            self.sample_rate = 48000
            self.frame_sample_count = self.sample_rate // (50 if self.pal_mode else 60)
            if self.audio_buffer is None:
                self.audio_buffer = []
            self.audio_enabled = True
            print(f"APU: Audio initialized with stream {self.audio_stream}")
            cpu_clock = 1662607.0 if self.pal_mode else 1789773.0
            self.cycles_per_sample = cpu_clock / self.sample_rate

    cdef void _generate_sample_c(self):
        cdef int p1, p2, tri_out, noise_out, dmc_out
        cdef int pulse_sum, tnd_sum, sample
        cdef double pulse_sample, tnd_sample, output

        p1 = self.pulse1.output_c()
        p2 = self.pulse2.output_c()
        tri_out = self.triangle.output_c()
        noise_out = self.noise.output_c()
        dmc_out = self.dmc.output_level

        pulse_sum = p1 + p2
        tnd_sum = 3 * tri_out + 2 * noise_out + dmc_out

        if pulse_sum > 30:
            pulse_sum = 30
        if tnd_sum > 202:
            tnd_sum = 202

        pulse_sample = <double>(<list>self.pulse_table)[pulse_sum]
        tnd_sample = <double>(<list>self.tnd_table)[tnd_sum]

        output = pulse_sample + tnd_sample

        sample = <int>(output * 32000)
        if sample < -32768:
            sample = -32768
        elif sample > 32767:
            sample = 32767

        (<list>self.audio_buffer).append(sample)

        if len(<list>self.audio_buffer) >= 1024:
            self._queue_audio()

    cpdef void step(self):
        self._cpu_cycle_parity ^= 1

        self.triangle.clock_timer_c()
        self.dmc.clock_timer_c()

        if self._cpu_cycle_parity:
            self.pulse1.clock_timer_c()
            self.pulse2.clock_timer_c()
            self.noise.clock_timer_c()

        self.frame_sequencer.clock_c(self)

        self.cycle_accumulator += 1.0
        if self.cycle_accumulator >= self.cycles_per_sample:
            self.cycle_accumulator -= self.cycles_per_sample
            self._generate_sample_c()

    def step_n(self, int n):
        cdef int parity = self._cpu_cycle_parity
        cdef double cps = self.cycles_per_sample
        cdef double acc = self.cycle_accumulator
        cdef int i
        for i in range(n):
            parity ^= 1
            self.triangle.clock_timer_c()
            self.dmc.clock_timer_c()
            if parity:
                self.pulse1.clock_timer_c()
                self.pulse2.clock_timer_c()
                self.noise.clock_timer_c()
            self.frame_sequencer.clock_c(self)
            acc += 1.0
            if acc >= cps:
                acc -= cps
                self._generate_sample_c()
        self._cpu_cycle_parity = parity
        self.cycle_accumulator = acc

    def _queue_audio(self):
        if (not hasattr(self, "audio_stream") or not self.audio_stream or
                not hasattr(self, "audio_buffer") or not self.audio_buffer):
            return

        if not SDL2_AVAILABLE:
            self.audio_buffer.clear()
            return

        try:
            audio_data = struct.pack(f"{len(self.audio_buffer)}h", *self.audio_buffer)
            result = sdl2.SDL_QueueAudio(self.audio_stream, audio_data, len(audio_data))
            if result != 0:
                error = sdl2.SDL_GetError() if SDL2_AVAILABLE else b'unknown'
                print(f"APU: SDL_QueueAudio failed: {error}")
                sdl2.SDL_ClearError()
        except Exception as e:
            print(f"APU: Error in _queue_audio: {e}")
            if SDL2_AVAILABLE:
                sdl2.SDL_ClearError()

        self.audio_buffer.clear()

    def read_status(self):
        cdef int status = 0
        if self.pulse1.length_counter > 0:
            status |= 0x01
        if self.pulse2.length_counter > 0:
            status |= 0x02
        if self.triangle.length_counter > 0:
            status |= 0x04
        if self.noise.length_counter > 0:
            status |= 0x08
        if self.dmc.bytes_remaining > 0:
            status |= 0x10
        if self.frame_sequencer.irq_flag:
            status |= 0x40
        if self.dmc.irq_flag:
            status |= 0x80

        self.frame_sequencer.irq_flag = False
        self.dmc.irq_flag = False
        return status

    def write_register(self, int addr, int value):
        if addr == 0x4000:
            self.pulse1.duty = (value >> 6) & 3
            self.pulse1.length_halt = <bint>(value & 0x20)
            self.pulse1.envelope.loop = <bint>(value & 0x20)
            self.pulse1.constant_volume = <bint>(value & 0x10)
            self.pulse1.envelope.period = value & 0x0F
            self.pulse1.envelope.divider.period = self.pulse1.envelope.period

        elif addr == 0x4001:
            self.pulse1.sweep.enabled = <bint>(value & 0x80)
            self.pulse1.sweep.period = (value >> 4) & 7
            self.pulse1.sweep.negate = <bint>(value & 0x08)
            self.pulse1.sweep.shift = value & 7
            self.pulse1.sweep.reload = True
            self.pulse1.sweep.divider.period = self.pulse1.sweep.period

        elif addr == 0x4002:
            self.pulse1.timer.period = (self.pulse1.timer.period & 0x700) | value
            self.pulse1.update_mute_c()

        elif addr == 0x4003:
            self.pulse1.timer.period = (self.pulse1.timer.period & 0xFF) | ((value & 7) << 8)
            if self.pulse1.enabled:
                self.pulse1.length_counter = LENGTH_TABLE[value >> 3]
            self.pulse1.envelope.step = 15
            self.pulse1.envelope.start = True
            self.pulse1.duty_step = 0
            self.pulse1.update_mute_c()

        elif addr == 0x4004:
            self.pulse2.duty = (value >> 6) & 3
            self.pulse2.length_halt = <bint>(value & 0x20)
            self.pulse2.envelope.loop = <bint>(value & 0x20)
            self.pulse2.constant_volume = <bint>(value & 0x10)
            self.pulse2.envelope.period = value & 0x0F
            self.pulse2.envelope.divider.period = self.pulse2.envelope.period

        elif addr == 0x4005:
            self.pulse2.sweep.enabled = <bint>(value & 0x80)
            self.pulse2.sweep.period = (value >> 4) & 7
            self.pulse2.sweep.negate = <bint>(value & 0x08)
            self.pulse2.sweep.shift = value & 7
            self.pulse2.sweep.reload = True
            self.pulse2.sweep.divider.period = self.pulse2.sweep.period

        elif addr == 0x4006:
            self.pulse2.timer.period = (self.pulse2.timer.period & 0x700) | value
            self.pulse2.update_mute_c()

        elif addr == 0x4007:
            self.pulse2.timer.period = (self.pulse2.timer.period & 0xFF) | ((value & 7) << 8)
            if self.pulse2.enabled:
                self.pulse2.length_counter = LENGTH_TABLE[value >> 3]
            self.pulse2.envelope.step = 15
            self.pulse2.envelope.start = True
            self.pulse2.duty_step = 0
            self.pulse2.update_mute_c()

        elif addr == 0x4008:
            self.triangle.length_halt = <bint>(value & 0x80)
            self.triangle.linear_reload = value & 0x7F

        elif addr == 0x400A:
            self.triangle.timer.period = (self.triangle.timer.period & 0x700) | value

        elif addr == 0x400B:
            self.triangle.timer.period = (self.triangle.timer.period & 0xFF) | ((value & 7) << 8)
            if self.triangle.enabled:
                self.triangle.length_counter = LENGTH_TABLE[value >> 3]
            self.triangle.linear_reload_flag = True

        elif addr == 0x400C:
            self.noise.length_halt = <bint>(value & 0x20)
            self.noise.envelope.loop = <bint>(value & 0x20)
            self.noise.constant_volume = <bint>(value & 0x10)
            self.noise.envelope.period = value & 0x0F
            self.noise.envelope.divider.period = self.noise.envelope.period

        elif addr == 0x400E:
            self.noise.mode = <bint>(value & 0x80)
            self.noise.set_period(value & 0x0F)

        elif addr == 0x400F:
            if self.noise.enabled:
                self.noise.length_counter = LENGTH_TABLE[value >> 3]
            self.noise.envelope.step = 15
            self.noise.envelope.start = True

        elif addr == 0x4010:
            self.dmc.irq_enable = <bint>(value & 0x80)
            self.dmc.loop = <bint>(value & 0x40)
            self.dmc.set_period(value & 0x0F)
            if not self.dmc.irq_enable:
                self.dmc.irq_flag = False

        elif addr == 0x4011:
            self.dmc.output_level = value & 0x7F

        elif addr == 0x4012:
            self.dmc.sample_address = 0xC000 | (value << 6)

        elif addr == 0x4013:
            self.dmc.sample_length = (value << 4) | 1

        elif addr == 0x4015:
            self.pulse1.enabled = <bint>(value & 0x01)
            self.pulse2.enabled = <bint>(value & 0x02)
            self.triangle.enabled = <bint>(value & 0x04)
            self.noise.enabled = <bint>(value & 0x08)
            self.dmc.enabled = <bint>(value & 0x10)

            if not self.pulse1.enabled:
                self.pulse1.length_counter = 0
            if not self.pulse2.enabled:
                self.pulse2.length_counter = 0
            if not self.triangle.enabled:
                self.triangle.length_counter = 0
            if not self.noise.enabled:
                self.noise.length_counter = 0

            if self.dmc.enabled:
                if self.dmc.bytes_remaining == 0:
                    self.dmc.restart()
                    self.dmc.fill_sample_buffer()
            else:
                self.dmc.bytes_remaining = 0
                self.dmc.irq_flag = False

        elif addr == 0x4017:
            self.frame_sequencer.mode = (value >> 7) & 1
            self.frame_sequencer.irq_inhibit = <bint>(value & 0x40)
            if self.frame_sequencer.irq_inhibit:
                self.frame_sequencer.irq_flag = False
            self.frame_sequencer.reset_sequencer = True

    def reset(self):
        self.write_register(0x4015, 0)
        self.frame_sequencer.cycles = 0
        self.cycle_accumulator = 0.0
        self._cpu_cycle_parity = 0
        self.audio_buffer.clear()

    def set_region(self, bint pal_mode):
        self.pal_mode = pal_mode
        self.noise.pal_mode = pal_mode
        self.dmc.pal_mode = pal_mode
        self.frame_sequencer.pal_mode = pal_mode
        cdef double cpu_clock = 1662607.0 if pal_mode else 1789773.0
        self.cycles_per_sample = cpu_clock / self.sample_rate
