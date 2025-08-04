"""
NES Audio Processing Unit (APU) Implementation
Implements the 2A03 APU with support for:
- 2 Pulse channels
- 1 Triangle channel
- 1 Noise channel
- Delta Modulation Channel (DMC)
- Frame sequencer
- Audio output via SDL2
"""

import sdl2
import ctypes
import struct


class Divider:
    """Timer/Divider implementation used throughout the APU"""

    def __init__(self):
        self.period = 0
        self.counter = 0
        self.step = 0
        self.limit = 0
        self.from_val = 0
        self.loop = True

    def clock(self):
        """Clock the divider, returns True when it reaches zero"""
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


class Envelope:
    """Envelope generator for pulse and noise channels"""

    def __init__(self):
        self.period = 0
        self.step = 15
        self.loop = False
        self.start = False
        self.divider = Divider()

    def clock(self):
        """Clock the envelope"""
        if self.start:
            self.start = False
            self.step = 15
            self.divider.counter = self.period
        elif self.divider.clock():
            if self.step > 0:
                self.step -= 1
            elif self.loop:
                self.step = 15


class Sweep:
    """Sweep unit for pulse channels"""

    def __init__(self):
        self.enabled = False
        self.period = 0
        self.negate = False
        self.shift = 0
        self.reload = False
        self.divider = Divider()

    def clock(self, pulse):
        """Clock the sweep unit"""
        if self.divider.clock():
            if self.enabled and self.shift > 0 and not pulse.muted:
                target_period = self.target_period(pulse)
                if target_period <= 0x7FF and pulse.timer.period >= 8:
                    pulse.timer.period = target_period

        if self.reload:
            self.divider.counter = self.period
            self.reload = False

    def target_period(self, pulse):
        """Calculate target period for sweep"""
        change = pulse.timer.period >> self.shift
        if self.negate:
            # Pulse 1 uses ones' complement, pulse 2 uses twos' complement
            if pulse.channel == 1:
                return pulse.timer.period - change - 1
            else:
                return pulse.timer.period - change
        else:
            return pulse.timer.period + change


class PulseChannel:
    """NES Pulse channel implementation"""

    # Duty cycle lookup table
    DUTY_CYCLES = [
        [0, 1, 0, 0, 0, 0, 0, 0],  # 12.5%
        [0, 1, 1, 0, 0, 0, 0, 0],  # 25%
        [0, 1, 1, 1, 1, 0, 0, 0],  # 50%
        [1, 0, 0, 1, 1, 1, 1, 1],  # 25% (negated)
    ]

    def __init__(self, channel_num):
        self.channel = channel_num
        self.enabled = False
        self.length_counter = 0
        self.length_halt = False

        # Timer
        self.timer = Divider()
        self.timer.limit = 7
        self.timer.loop = True

        # Duty
        self.duty = 0
        self.duty_step = 0

        # Envelope
        self.envelope = Envelope()
        self.constant_volume = False

        # Sweep
        self.sweep = Sweep()

        # State
        self.muted = False

    def clock_timer(self):
        """Clock the pulse timer"""
        if self.timer.clock():
            self.duty_step = (self.duty_step + 1) % 8

    def clock_envelope(self):
        """Clock the envelope"""
        self.envelope.clock()

    def clock_sweep(self):
        """Clock the sweep unit"""
        self.sweep.clock(self)
        self.update_mute()

    def clock_length(self):
        """Clock the length counter"""
        if not self.length_halt and self.length_counter > 0:
            self.length_counter -= 1

    def update_mute(self):
        """Update mute status based on timer period and sweep target"""
        if self.timer.period < 8:
            self.muted = True
        elif self.sweep.enabled and self.sweep.shift > 0:
            target = self.sweep.target_period(self)
            self.muted = target > 0x7FF
        else:
            self.muted = False

    def output(self):
        """Get the current output value"""
        if not self.enabled or self.length_counter == 0 or self.muted:
            return 0

        duty_output = self.DUTY_CYCLES[self.duty][self.duty_step]
        if duty_output == 0:
            return 0

        if self.constant_volume:
            return self.envelope.period
        else:
            return self.envelope.step


class TriangleChannel:
    """NES Triangle channel implementation"""

    # Triangle wave sequence
    TRIANGLE_SEQUENCE = [
        15,
        14,
        13,
        12,
        11,
        10,
        9,
        8,
        7,
        6,
        5,
        4,
        3,
        2,
        1,
        0,
        0,
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
        9,
        10,
        11,
        12,
        13,
        14,
        15,
    ]

    def __init__(self):
        self.enabled = False
        self.length_counter = 0
        self.length_halt = False

        # Linear counter
        self.linear_counter = 0
        self.linear_reload = 0
        self.linear_reload_flag = False

        # Timer
        self.timer = Divider()
        self.timer.limit = 31
        self.timer.loop = True

        # Sequencer
        self.sequence_step = 0

    def clock_timer(self):
        """Clock the triangle timer"""
        if self.linear_counter > 0 and self.length_counter > 0:
            if self.timer.clock():
                self.sequence_step = (self.sequence_step + 1) % 32

    def clock_linear(self):
        """Clock the linear counter"""
        if self.linear_reload_flag:
            self.linear_counter = self.linear_reload
        elif self.linear_counter > 0:
            self.linear_counter -= 1

        if not self.length_halt:
            self.linear_reload_flag = False

    def clock_length(self):
        """Clock the length counter"""
        if not self.length_halt and self.length_counter > 0:
            self.length_counter -= 1

    def output(self):
        """Get the current output value"""
        if not self.enabled or self.length_counter == 0 or self.timer.period < 2:
            return 0
        return self.TRIANGLE_SEQUENCE[self.sequence_step]


class NoiseChannel:
    """NES Noise channel implementation"""

    # Noise period lookup tables
    NOISE_PERIODS_NTSC = [
        4,
        8,
        16,
        32,
        64,
        96,
        128,
        160,
        202,
        254,
        380,
        508,
        762,
        1016,
        2034,
        4068,
    ]

    NOISE_PERIODS_PAL = [
        4,
        8,
        14,
        30,
        60,
        88,
        118,
        148,
        188,
        236,
        354,
        472,
        708,
        944,
        1890,
        3778,
    ]

    def __init__(self, pal_mode=False):
        self.enabled = False
        self.length_counter = 0
        self.length_halt = False
        self.pal_mode = pal_mode

        # Timer
        self.timer = Divider()

        # Envelope
        self.envelope = Envelope()
        self.constant_volume = False

        # Shift register
        self.shift_register = 1
        self.mode = False  # False = 1-bit feedback, True = 6-bit feedback

    def clock_timer(self):
        """Clock the noise timer"""
        if self.timer.clock():
            # Calculate feedback
            if self.mode:
                feedback = (self.shift_register & 1) ^ ((self.shift_register >> 6) & 1)
            else:
                feedback = (self.shift_register & 1) ^ ((self.shift_register >> 1) & 1)

            # Shift register
            self.shift_register >>= 1
            self.shift_register |= feedback << 14

    def clock_envelope(self):
        """Clock the envelope"""
        self.envelope.clock()

    def clock_length(self):
        """Clock the length counter"""
        if not self.length_halt and self.length_counter > 0:
            self.length_counter -= 1

    def set_period(self, index):
        """Set the timer period from lookup table"""
        periods = self.NOISE_PERIODS_PAL if self.pal_mode else self.NOISE_PERIODS_NTSC
        self.timer.period = periods[index & 0xF]

    def output(self):
        """Get the current output value"""
        if not self.enabled or self.length_counter == 0 or (self.shift_register & 1):
            return 0

        if self.constant_volume:
            return self.envelope.period
        else:
            return self.envelope.step


class DMCChannel:
    """NES Delta Modulation Channel implementation"""

    # DMC period lookup tables
    DMC_PERIODS_NTSC = [
        428,
        380,
        340,
        320,
        286,
        254,
        226,
        214,
        190,
        160,
        142,
        128,
        106,
        84,
        72,
        54,
    ]

    DMC_PERIODS_PAL = [
        398,
        354,
        316,
        298,
        276,
        236,
        210,
        198,
        176,
        148,
        132,
        118,
        98,
        78,
        66,
        50,
    ]

    def __init__(self, pal_mode=False, memory=None):
        self.enabled = False
        self.pal_mode = pal_mode
        self.memory = memory

        # IRQ
        self.irq_enable = False
        self.irq_flag = False

        # Loop flag
        self.loop = False

        # Timer
        self.timer = Divider()

        # Output unit
        self.output_level = 0
        self.shift_register = 0
        self.bits_remaining = 0
        self.silence = True

        # Memory reader
        self.sample_address = 0xC000
        self.sample_length = 1
        self.current_address = 0xC000
        self.bytes_remaining = 0
        self.sample_buffer = 0
        self.sample_buffer_empty = True

    def clock_timer(self):
        """Clock the DMC timer"""
        if self.timer.clock():
            self.clock_output()

    def clock_output(self):
        """Clock the output unit"""
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

    def fill_sample_buffer(self):
        """Fill the sample buffer from memory"""
        if self.sample_buffer_empty and self.bytes_remaining > 0:
            if self.memory:
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
                        self.irq_flag = True

    def restart(self):
        """Restart the sample"""
        self.current_address = self.sample_address
        self.bytes_remaining = self.sample_length

    def set_period(self, index):
        """Set the timer period from lookup table"""
        periods = self.DMC_PERIODS_PAL if self.pal_mode else self.DMC_PERIODS_NTSC
        self.timer.period = periods[index & 0xF]

    def output(self):
        """Get the current output value"""
        return self.output_level


class FrameSequencer:
    """APU Frame sequencer (controls envelope, sweep, and length counters)"""

    def __init__(self):
        self.mode = 0  # 0 = 4-step, 1 = 5-step
        self.irq_inhibit = False
        self.irq_flag = False
        self.step = 0
        self.cycles = 0

    def clock(self, apu):
        """Clock the frame sequencer"""
        if self.mode == 0:  # 4-step mode
            if self.cycles in [7457, 14913, 22371, 29829]:
                self.clock_quarter_frame(apu)
            if self.cycles in [14913, 29829]:
                self.clock_half_frame(apu)
            if self.cycles == 29829:
                if not self.irq_inhibit:
                    self.irq_flag = True
                self.cycles = 0
            else:
                self.cycles += 1
        else:  # 5-step mode
            if self.cycles in [7457, 14913, 22371, 37281]:
                self.clock_quarter_frame(apu)
            if self.cycles in [14913, 37281]:
                self.clock_half_frame(apu)
            if self.cycles == 37281:
                self.cycles = 0
            else:
                self.cycles += 1

    def clock_quarter_frame(self, apu):
        """Clock envelopes and triangle linear counter"""
        apu.pulse1.clock_envelope()
        apu.pulse2.clock_envelope()
        apu.noise.clock_envelope()
        apu.triangle.clock_linear()

    def clock_half_frame(self, apu):
        """Clock length counters and sweep units"""
        apu.pulse1.clock_length()
        apu.pulse1.clock_sweep()
        apu.pulse2.clock_length()
        apu.pulse2.clock_sweep()
        apu.triangle.clock_length()
        apu.noise.clock_length()


class APU:
    """Main Audio Processing Unit"""

    # Length counter lookup table
    LENGTH_COUNTER_TABLE = [
        10,
        254,
        20,
        2,
        40,
        4,
        80,
        6,
        160,
        8,
        60,
        10,
        14,
        12,
        26,
        14,
        12,
        16,
        24,
        18,
        48,
        20,
        96,
        22,
        192,
        24,
        72,
        26,
        16,
        28,
        32,
        30,
    ]

    def __init__(self, nes, pal_mode=False):
        self.nes = nes
        self.pal_mode = pal_mode

        # Audio channels
        self.pulse1 = PulseChannel(1)
        self.pulse2 = PulseChannel(2)
        self.triangle = TriangleChannel()
        self.noise = NoiseChannel(pal_mode)
        self.dmc = DMCChannel(pal_mode, nes.memory)

        # Frame sequencer
        self.frame_sequencer = FrameSequencer()

        # Audio output
        self.sample_rate = 48000
        self.audio_buffer = []
        self.audio_stream = None
        self.cycles_per_sample = 1789773.0 / self.sample_rate  # NTSC timing
        if pal_mode:
            self.cycles_per_sample = 1662607.0 / self.sample_rate  # PAL timing
        self.cycle_accumulator = 0.0

        # Mixer lookup tables
        self.pulse_table = self._create_pulse_table()
        self.tnd_table = self._create_tnd_table()

        self._init_audio()

    def _create_pulse_table(self):
        """Create pulse channel mixer lookup table"""
        table = [0.0] * 31
        for i in range(1, 31):
            table[i] = 95.52 / (8128.0 / i + 100)
        return table

    def _create_tnd_table(self):
        """Create triangle/noise/DMC mixer lookup table"""
        table = [0.0] * 203
        for i in range(1, 203):
            table[i] = 163.67 / (24329.0 / i + 100)
        return table

    def _init_audio(self):
        """Initialize SDL audio"""
        # Audio will be initialized when needed by the main emulator
        pass

    def init_audio_stream(self, audio_stream):
        """Initialize with SDL audio stream from main emulator"""
        self.audio_stream = audio_stream

    def step(self):
        """Step the APU by one CPU cycle - optimized"""
        # Reduce function call overhead by combining operations
        # Clock all timers in one pass
        self.pulse1.clock_timer()
        self.pulse2.clock_timer()
        self.triangle.clock_timer()

        # Clock noise and DMC every other cycle - use bit mask for speed
        if not (self.nes.cpu.total_cycles & 1):
            self.noise.clock_timer()
            self.dmc.clock_timer()

        # Clock frame sequencer less frequently
        self.frame_sequencer.clock(self)

        # Generate audio sample with reduced frequency
        self.cycle_accumulator += 1.0
        if self.cycle_accumulator >= self.cycles_per_sample:
            self.cycle_accumulator -= self.cycles_per_sample
            self._generate_sample()

    def _generate_sample(self):
        """Generate an audio sample"""
        # Get channel outputs
        pulse1_out = self.pulse1.output()
        pulse2_out = self.pulse2.output()
        triangle_out = self.triangle.output()
        noise_out = self.noise.output()
        dmc_out = self.dmc.output()

        # Mix using lookup tables
        pulse_sum = pulse1_out + pulse2_out
        tnd_sum = 3 * triangle_out + 2 * noise_out + dmc_out

        pulse_sample = self.pulse_table[min(pulse_sum, 30)]
        tnd_sample = self.tnd_table[min(tnd_sum, 202)]

        # Combine and convert to 16-bit signed
        output = pulse_sample + tnd_sample
        sample = int((output - 0.5) * 32767)
        sample = max(-32768, min(32767, sample))

        self.audio_buffer.append(sample)

        # Queue audio when buffer is full
        if len(self.audio_buffer) >= 1024:
            self._queue_audio()

    def _queue_audio(self):
        """Queue audio buffer to SDL"""
        if self.audio_stream and self.audio_buffer:
            # Convert to bytes using struct
            audio_data = struct.pack(f"{len(self.audio_buffer)}h", *self.audio_buffer)

            # Queue to SDL2 audio device
            sdl2.SDL_QueueAudio(self.audio_stream, audio_data, len(audio_data))

            self.audio_buffer.clear()

    def read_status(self):
        """Read APU status register ($4015)"""
        status = 0
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

        # Clear frame IRQ flag
        self.frame_sequencer.irq_flag = False
        return status

    def write_register(self, addr, value):
        """Write to APU register"""
        if addr == 0x4000:  # Pulse 1 duty/envelope
            self.pulse1.duty = (value >> 6) & 3
            self.pulse1.length_halt = bool(value & 0x20)
            self.pulse1.envelope.loop = bool(value & 0x20)
            self.pulse1.constant_volume = bool(value & 0x10)
            self.pulse1.envelope.period = value & 0x0F

        elif addr == 0x4001:  # Pulse 1 sweep
            self.pulse1.sweep.enabled = bool(value & 0x80)
            self.pulse1.sweep.period = (value >> 4) & 7
            self.pulse1.sweep.negate = bool(value & 0x08)
            self.pulse1.sweep.shift = value & 7
            self.pulse1.sweep.reload = True

        elif addr == 0x4002:  # Pulse 1 timer low
            self.pulse1.timer.period = (self.pulse1.timer.period & 0x700) | value
            self.pulse1.update_mute()

        elif addr == 0x4003:  # Pulse 1 timer high/length
            self.pulse1.timer.period = (self.pulse1.timer.period & 0xFF) | (
                (value & 7) << 8
            )
            if self.pulse1.enabled:
                self.pulse1.length_counter = self.LENGTH_COUNTER_TABLE[value >> 3]
            self.pulse1.envelope.start = True
            self.pulse1.duty_step = 0
            self.pulse1.update_mute()

        elif addr == 0x4004:  # Pulse 2 duty/envelope
            self.pulse2.duty = (value >> 6) & 3
            self.pulse2.length_halt = bool(value & 0x20)
            self.pulse2.envelope.loop = bool(value & 0x20)
            self.pulse2.constant_volume = bool(value & 0x10)
            self.pulse2.envelope.period = value & 0x0F

        elif addr == 0x4005:  # Pulse 2 sweep
            self.pulse2.sweep.enabled = bool(value & 0x80)
            self.pulse2.sweep.period = (value >> 4) & 7
            self.pulse2.sweep.negate = bool(value & 0x08)
            self.pulse2.sweep.shift = value & 7
            self.pulse2.sweep.reload = True

        elif addr == 0x4006:  # Pulse 2 timer low
            self.pulse2.timer.period = (self.pulse2.timer.period & 0x700) | value
            self.pulse2.update_mute()

        elif addr == 0x4007:  # Pulse 2 timer high/length
            self.pulse2.timer.period = (self.pulse2.timer.period & 0xFF) | (
                (value & 7) << 8
            )
            if self.pulse2.enabled:
                self.pulse2.length_counter = self.LENGTH_COUNTER_TABLE[value >> 3]
            self.pulse2.envelope.start = True
            self.pulse2.duty_step = 0
            self.pulse2.update_mute()

        elif addr == 0x4008:  # Triangle linear counter
            self.triangle.length_halt = bool(value & 0x80)
            self.triangle.linear_reload = value & 0x7F

        elif addr == 0x400A:  # Triangle timer low
            self.triangle.timer.period = (self.triangle.timer.period & 0x700) | value

        elif addr == 0x400B:  # Triangle timer high/length
            self.triangle.timer.period = (self.triangle.timer.period & 0xFF) | (
                (value & 7) << 8
            )
            if self.triangle.enabled:
                self.triangle.length_counter = self.LENGTH_COUNTER_TABLE[value >> 3]
            self.triangle.linear_reload_flag = True

        elif addr == 0x400C:  # Noise envelope
            self.noise.length_halt = bool(value & 0x20)
            self.noise.envelope.loop = bool(value & 0x20)
            self.noise.constant_volume = bool(value & 0x10)
            self.noise.envelope.period = value & 0x0F

        elif addr == 0x400E:  # Noise period/mode
            self.noise.mode = bool(value & 0x80)
            self.noise.set_period(value & 0x0F)

        elif addr == 0x400F:  # Noise length
            if self.noise.enabled:
                self.noise.length_counter = self.LENGTH_COUNTER_TABLE[value >> 3]
            self.noise.envelope.start = True

        elif addr == 0x4010:  # DMC control
            self.dmc.irq_enable = bool(value & 0x80)
            self.dmc.loop = bool(value & 0x40)
            self.dmc.set_period(value & 0x0F)
            if not self.dmc.irq_enable:
                self.dmc.irq_flag = False

        elif addr == 0x4011:  # DMC direct load
            self.dmc.output_level = value & 0x7F

        elif addr == 0x4012:  # DMC sample address
            self.dmc.sample_address = 0xC000 | (value << 6)

        elif addr == 0x4013:  # DMC sample length
            self.dmc.sample_length = (value << 4) | 1

        elif addr == 0x4015:  # APU status/enable
            self.pulse1.enabled = bool(value & 0x01)
            self.pulse2.enabled = bool(value & 0x02)
            self.triangle.enabled = bool(value & 0x04)
            self.noise.enabled = bool(value & 0x08)
            self.dmc.enabled = bool(value & 0x10)

            # Clear length counters if disabled
            if not self.pulse1.enabled:
                self.pulse1.length_counter = 0
            if not self.pulse2.enabled:
                self.pulse2.length_counter = 0
            if not self.triangle.enabled:
                self.triangle.length_counter = 0
            if not self.noise.enabled:
                self.noise.length_counter = 0

            # DMC handling
            self.dmc.irq_flag = False
            if self.dmc.enabled:
                if self.dmc.bytes_remaining == 0:
                    self.dmc.restart()
            else:
                self.dmc.bytes_remaining = 0

        elif addr == 0x4017:  # Frame sequencer
            self.frame_sequencer.mode = (value >> 7) & 1
            self.frame_sequencer.irq_inhibit = bool(value & 0x40)
            if self.frame_sequencer.irq_inhibit:
                self.frame_sequencer.irq_flag = False

            # Reset sequencer
            self.frame_sequencer.cycles = 0
            if self.frame_sequencer.mode == 1:  # 5-step mode
                self.frame_sequencer.clock_quarter_frame(self)
                self.frame_sequencer.clock_half_frame(self)

    def reset(self):
        """Reset the APU"""
        self.write_register(0x4015, 0)  # Disable all channels
        self.frame_sequencer.cycles = 0
        self.cycle_accumulator = 0.0
        self.audio_buffer.clear()
