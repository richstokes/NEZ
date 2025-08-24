"""
Main NES Emulator Class
Coordinates CPU, PPU, APU, and Memory components
"""

from cpu import CPU
from ppu import PPU
from apu import APU
from memory import Memory, Cartridge
from utils import debug_print


class NES:
    def __init__(self):
        # Initialize components
        self.memory = Memory()
        self.region = 'NTSC'  # Default region, will be updated when ROM loads
        self.ppu = PPU(self.memory, self.region)
        self.cpu = CPU(self.memory)
        self.apu = APU(self, pal_mode=False)  # Will be reconfigured when ROM loads

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
            debug_print(f"NES: Failed to load ROM '{rom_path}': {e}")
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
        debug_print(f"NES: ROM '{rom_path}' loaded (mapper={cart.mapper}, region={self.region})")
        return True

    def reset(self):
        """Reset CPU, PPU, and APU state (power-on like)."""
        # CPU Reset Vector
        low = self.memory.read(0xFFFC)
        high = self.memory.read(0xFFFD)
        pc = (high << 8) | low
        self.cpu.PC = pc
        self.cpu.S = 0xFD
        self.cpu.I = 1
        self.cpu.C = self.cpu.Z = self.cpu.D = self.cpu.B = self.cpu.V = self.cpu.N = 0
        self.cpu.cycles = 0
        self.cpu.total_cycles = 0
        # Clear PPU timing/frame state
        self.ppu.frame = 0
        self.ppu.scanline = 0
        self.ppu.cycle = 0
        self.ppu.render = False
        # Clear any pending NMI
        self.nmi_pending = False
        self.nmi_delay = 0
        # APU basic reset if available
        if hasattr(self.apu, 'reset'):
            try:
                self.apu.reset()
            except Exception:
                pass
        debug_print(f"NES: Reset complete, PC=0x{pc:04X}, region={self.region}")

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

        # Update PPU open bus decay
        self.ppu.update_bus_decay(cpu_cycles)

        # PPU cycles: 3 per CPU cycle (NTSC) or 3.2 average (PAL)
        if self.region == 'PAL':
            if not hasattr(self, 'pal_cycle_counter'):
                self.pal_cycle_counter = 0
            for _ in range(cpu_cycles * 3):
                self.ppu.step(); self.ppu_cycles += 1
            self.pal_cycle_counter += cpu_cycles
            extra = self.pal_cycle_counter // 5
            self.pal_cycle_counter %= 5
            for _ in range(extra):
                self.ppu.step(); self.ppu_cycles += 1
        else:
            for _ in range(cpu_cycles * 3):
                self.ppu.step(); self.ppu_cycles += 1

        # APU: 1 per CPU cycle
        for _ in range(cpu_cycles):
            self.apu.step()

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
                    debug_print(
                        f"DEBUG: PPU OSCILLATION DETECTED at scanline={self.ppu.scanline}, cycle={self.ppu.cycle}, frame={self.ppu.frame}"
                    )
                    # Force the PPU to advance
                    self.ppu.cycle += 1
                    oscillation_counter = 0
            else:
                oscillation_counter = 0
                last_scanline = self.ppu.scanline
                last_cycle = self.ppu.cycle

            if (
                step_count > 89000
            ):  # Safety break to prevent infinite loops (increased for NTSC frame)
                debug_print(
                    f"DEBUG: step_frame safety break at {step_count} steps, PPU at scanline={self.ppu.scanline}, cycle={self.ppu.cycle}, mask={self.ppu.mask}, render={self.ppu.render}, frame={self.ppu.frame}"
                )
                # Force render flag to exit loop if we hit the safety limit
                self.ppu.render = True
                break

        # The render flag is kept true until the next frame starts
        # This is important for proper frame synchronization
        return self.ppu.screen

    def handle_nmi(self):
        """Handle Non-Maskable Interrupt"""
        debug_print(f"NES: handle_nmi() called, CPU PC=0x{self.cpu.PC:04X}")

        # Do not clear pending IRQs here. NMI takes precedence naturally at the CPU,
        # and any latched IRQ should remain pending to be serviced after NMI if allowed.

        # Trigger NMI through the CPU's new interrupt system
        if hasattr(self.cpu, "trigger_interrupt"):
            debug_print(
                f"NES: Calling CPU.trigger_interrupt('NMI'), CPU PC=0x{self.cpu.PC:04X}"
            )
            self.cpu.trigger_interrupt("NMI")
        else:
            # Fallback for old CPU implementation
            debug_print(f"NES: CPU doesn't have trigger_interrupt, using fallback")
            # Push PC and status to stack
            self.cpu.push_stack((self.cpu.PC >> 8) & 0xFF)
            self.cpu.push_stack(self.cpu.PC & 0xFF)

            # Mask B flag off when pushing status during interrupt
            status = self.cpu.get_status_byte() & 0xEF  # Clear B flag (bit 4)
            self.cpu.push_stack(status)

            # Set interrupt disable flag
            self.cpu.I = 1

            # Jump to NMI vector
            low = self.memory.read(0xFFFA)
            high = self.memory.read(0xFFFB)
            new_pc = (high << 8) | low
            debug_print(
                f"NES: NMI handling - jumping to 0x{new_pc:04X}, prev PC=0x{self.cpu.PC:04X}"
            )
            self.cpu.PC = new_pc

    def trigger_nmi(self):
        """Trigger NMI immediately - called directly from PPU"""
        debug_print(f"NES: trigger_nmi() called, setting nmi_pending=True")
        debug_print(
            f"NES: NMI triggered at frame {self.ppu.frame}, scanline {self.ppu.scanline}, CPU PC=0x{self.cpu.PC:04X}"
        )

        # Mark NMI as pending - will be handled in next CPU step
        self.nmi_pending = True
        debug_print(f"NES: NMI pending set to True, will be handled in next step")


        # The delay is important for accurate timing
        # NMI is detected at the end of the current instruction
        # 2 cycles gives enough time for the current instruction to finish
        self.nmi_delay = 2

        # Inform user about NMI trigger during early frames
        if self.ppu.frame <= 35:
            debug_print(
                f"NES: NMI triggered at frame {self.ppu.frame}, scanline {self.ppu.scanline}, CPU PC=0x{self.cpu.PC:04X}"
            )

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
