"""
Main NES Emulator Class
Coordinates CPU, PPU, APU, and Memory components
"""

from cpu import CPU
from ppu import PPU
from apu import APU
from memory import Memory, Cartridge


class NES:
    def __init__(self, fast_mode=True):
        # Initialize components
        self.memory = Memory()
        self.region = 'NTSC'  # Default region, will be updated when ROM loads
        self.ppu = PPU(self.memory, self.region)
        self.cpu = CPU(self.memory)
        self.apu = APU(self, pal_mode=False)  # Will be reconfigured when ROM loads
        self.fast_mode = fast_mode  # Skip non-critical updates for speed

        # Connect components
        self.memory.set_ppu(self.ppu)
        self.memory.set_cpu(self.cpu)
        self.memory.set_apu(self.apu)
        self.memory.set_nes(self)  # Add NES reference to memory
        self.ppu.memory = self.memory
        self.ppu.cpu = self.cpu  # Give PPU direct access to CPU for NMI

        # Timing
        self.cpu_cycles = 0
        self.ppu_cycles = 0

        # NMI (Non-Maskable Interrupt)
        self.nmi_pending = False
        self.nmi_delay = 0

        # Reset state
        self.reset_pending = False

        # Running state
        self.running = False

    def load_rom(self, rom_path: str):
        """Load a ROM file and initialize cartridge-dependent state.
        Returns True on success, False on failure.
        """
        try:
            cart = Cartridge(rom_path)
        except Exception as e:
            print(f"Failed to load ROM: {e}")
            return False

        # Attach cartridge
        self.memory.set_cartridge(cart)
        cart.memory = self.memory  # back-reference for mappers if needed

        # Update region from cartridge detection (NTSC/PAL) and reconfigure subsystems
        self.region = getattr(cart, 'region', 'NTSC')
        self.ppu.region = self.region
        pal_mode = (self.region == 'PAL')
        if hasattr(self.apu, 'set_region'):
            try:
                self.apu.set_region(pal_mode)
            except Exception:
                pass

        # Reset CPU/PPU to power-on state using vectors from cartridge PRG
        self.reset()
        return True

    def reset(self):
        """Reset CPU, PPU, and APU state (power-on like)."""
        # Full CPU reset (reads reset vector, resets all internal state
        # including interrupt tracking, DMA cycles, odd_cycle, etc.)
        self.cpu.reset()

        # Clear PPU timing/frame state
        self.ppu.frame = 0
        self.ppu.scanline = 0
        self.ppu.cycle = 0
        self.ppu.render = False
        # Clear any pending NMI at NES level
        self.nmi_pending = False
        self.nmi_delay = 0
        # Reset NES-level cycle counters
        self.cpu_cycles = 0
        self.ppu_cycles = 0
        # APU basic reset if available
        if hasattr(self.apu, 'reset'):
            try:
                self.apu.reset()
            except Exception:
                pass

    def step(self):
        """Execute one NES step (one CPU cycle + corresponding PPU/APU cycles)"""
        # Handle pending NMI timing
        if self.nmi_pending:
            if self.nmi_delay > 0:
                self.nmi_delay -= 1
            else:
                self.handle_nmi()
                self.nmi_pending = False

        # Execute one CPU cycle (CPU internally tracks remaining instruction cycles)
        cpu_cycles = self.cpu.step()
        self.cpu_cycles += cpu_cycles

        # Cache references for speed
        ppu_step = self.ppu.step

        # PPU cycles: 3 per CPU cycle (NTSC)
        ppu_count = cpu_cycles * 3
        for _ in range(ppu_count):
            ppu_step()
        self.ppu_cycles += ppu_count

        # APU must always run (frame counter/DMC IRQs are required for correct emulation)
        apu_step = self.apu.step
        for _ in range(cpu_cycles):
            apu_step()

    def run_frame_fast(self):
        """Run one complete frame in a tight loop with cached locals.
        Avoids per-step method-call overhead of step() by inlining the
        NMI check + CPU/PPU/APU dispatch into a single scope.
        """
        self.ppu.render = False

        # Cache everything as locals for speed
        cpu = self.cpu
        ppu = self.ppu
        apu = self.apu
        cpu_step = cpu.step
        ppu_step = ppu.step
        apu_step = apu.step
        nmi_handler = self.handle_nmi
        step_limit = 200000
        steps = 0

        nmi_pending = self.nmi_pending
        nmi_delay = self.nmi_delay
        cpu_cycles_total = self.cpu_cycles
        ppu_cycles_total = self.ppu_cycles

        while not ppu.render and steps < step_limit:
            steps += 1

            # Inline NMI handling
            if nmi_pending:
                if nmi_delay > 0:
                    nmi_delay -= 1
                    self.nmi_delay = nmi_delay
                else:
                    self.nmi_pending = False
                    nmi_handler()
                    nmi_pending = False
                # Re-read in case handler changed them
                nmi_pending = self.nmi_pending
                nmi_delay = self.nmi_delay

            # CPU step
            cc = cpu_step()
            cpu_cycles_total += cc

            # PPU: 3 cycles per CPU cycle (NTSC)
            ppu_n = cc * 3
            for _ in range(ppu_n):
                ppu_step()
            ppu_cycles_total += ppu_n

            # APU: 1 cycle per CPU cycle
            for _ in range(cc):
                apu_step()

            # Re-sync NMI state (PPU may trigger NMI during its step)
            nmi_pending = self.nmi_pending
            nmi_delay = self.nmi_delay

        # Write back counters
        self.cpu_cycles = cpu_cycles_total
        self.ppu_cycles = ppu_cycles_total
        self.nmi_pending = nmi_pending
        self.nmi_delay = nmi_delay

        return self.ppu.screen

    def step_frame(self):
        """Step one complete frame - using the unified step() method"""
        step_count = 0
        # Reset the render flag at the start of each frame
        self.ppu.render = False

        # Don't clear NMI state - let it be handled naturally
        # The NMI should persist until handled by the CPU

        # Track the last PPU state to detect oscillations
        last_scanline = -1
        last_cycle = -1
        oscillation_counter = 0

        while not self.ppu.render:
            self.step()
            step_count += 1

            # Detect oscillation (PPU stuck at same position)
            if self.ppu.scanline == last_scanline and self.ppu.cycle == last_cycle:
                oscillation_counter += 1
                if oscillation_counter > 100:
                    self.ppu.cycle += 1
                    oscillation_counter = 0
            else:
                oscillation_counter = 0
                last_scanline = self.ppu.scanline
                last_cycle = self.ppu.cycle

            # Safety break to prevent infinite loops
            if step_count > 200000:
                self.ppu.render = True
                break

        # The render flag is kept true until the next frame starts
        # This is important for proper frame synchronization
        return self.ppu.screen

    def handle_nmi(self):
        """Handle Non-Maskable Interrupt"""
        if hasattr(self.cpu, "trigger_interrupt"):
            self.cpu.trigger_interrupt("NMI")
        else:
            # Fallback for old CPU implementation
            self.cpu.push_stack((self.cpu.PC >> 8) & 0xFF)
            self.cpu.push_stack(self.cpu.PC & 0xFF)
            status = self.cpu.get_status_byte() & 0xEF  # Clear B flag
            self.cpu.push_stack(status)
            self.cpu.I = 1
            low = self.memory.read(0xFFFA)
            high = self.memory.read(0xFFFB)
            self.cpu.PC = (high << 8) | low

    def trigger_nmi(self):
        """Trigger NMI - called directly from PPU"""
        self.nmi_pending = True
        self.nmi_delay = 2

    def set_controller_input(self, controller, buttons):
        """Set controller input
        controller: 1 or 2
        buttons: dict with keys 'A', 'B', 'Select', 'Start', 'Up', 'Down', 'Left', 'Right'
        """
        button_byte = 0
        if buttons.get("A", False):
            button_byte |= 0x01
        if buttons.get("B", False):
            button_byte |= 0x02
        if buttons.get("Select", False):
            button_byte |= 0x04
        if buttons.get("Start", False):
            button_byte |= 0x08
        if buttons.get("Up", False):
            button_byte |= 0x10
        if buttons.get("Down", False):
            button_byte |= 0x20
        if buttons.get("Left", False):
            button_byte |= 0x40
        if buttons.get("Right", False):
            button_byte |= 0x80

        self.memory.set_controller_state(controller, button_byte)

    def get_screen(self):
        """Get the current screen buffer"""
        return self.ppu.screen

    def is_frame_ready(self):
        """Check if a new frame is ready"""
        return self.ppu.frame > 0 and self.ppu.scanline == 0 and self.ppu.cycle == 0

    def run_for_cycles(self, cycles):
        """Run emulator for specified number of CPU cycles"""
        target = self.cpu_cycles + cycles
        while self.cpu_cycles < target:
            self.step()

    def run_until_vblank(self):
        """Run until VBlank starts"""
        while not (self.ppu.status & 0x80):
            self.step()

    def get_cpu_state(self):
        """Get CPU state for debugging"""
        return {
            "A": self.cpu.A,
            "X": self.cpu.X,
            "Y": self.cpu.Y,
            "PC": self.cpu.PC,
            "S": self.cpu.S,
            "C": self.cpu.C,
            "Z": self.cpu.Z,
            "I": self.cpu.I,
            "D": self.cpu.D,
            "B": self.cpu.B,
            "V": self.cpu.V,
            "N": self.cpu.N,
            "cycles": self.cpu_cycles,
        }

    def get_ppu_state(self):
        """Get PPU state for debugging"""
        return {
            "ctrl": self.ppu.ctrl,
            "mask": self.ppu.mask,
            "status": self.ppu.status,
            "scanline": self.ppu.scanline,
            "cycle": self.ppu.cycle,
            "frame": self.ppu.frame,
            "v": self.ppu.v,
            "t": self.ppu.t,
            "x": self.ppu.x,
            "w": self.ppu.w,
        }
