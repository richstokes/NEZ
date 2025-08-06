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
        self.ppu = PPU(self.memory)
        self.cpu = CPU(self.memory)
        self.apu = APU(self)

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

    def load_cartridge(self, rom_path):
        """Load a ROM cartridge"""
        try:
            cartridge = Cartridge(rom_path)
            self.memory.set_cartridge(cartridge)
            return True
        except Exception as e:
            print(f"Error loading ROM: {e}")
            return False

    def load_rom(self, rom_path):
        """Load a ROM file - alias for load_cartridge"""
        return self.load_cartridge(rom_path)

    def reset(self):
        """Reset the NES"""
        self.cpu.reset()
        self.ppu.reset()
        self.apu.reset()
        self.cpu_cycles = 0
        self.ppu_cycles = 0
        self.nmi_pending = False
        self.nmi_delay = 0
        print("NES Reset")

    def step(self):
        """Execute one NES step - cycle-accurate like reference"""
        # Handle pending NMI
        if self.nmi_pending:
            if self.nmi_delay > 0:
                self.nmi_delay -= 1
            else:
                debug_print(f"NES: Handling NMI, calling handle_nmi()")
                self.handle_nmi()
                self.nmi_pending = False

        # Step CPU (returns number of cycles used)
        cpu_cycles = self.cpu.step()
        self.cpu_cycles += cpu_cycles

        # Step PPU (3 PPU cycles per CPU cycle for NTSC)
        # Reference implementation: execute_ppu() called cpu_cycles * 3 times
        for _ in range(cpu_cycles * 3):
            self.ppu.step()

            # VBlank NMI detection now happens immediately in PPU when flag is set
            self.ppu_cycles += 1

        # Step APU (1 APU cycle per CPU cycle)
        for _ in range(cpu_cycles):
            self.apu.step()

    def step_frame(self):
        """Step one complete frame - using the unified step() method"""
        step_count = 0
        # Reset the render flag at the start of each frame
        self.ppu.render = False

        # Clear frame-state variables to ensure clean start
        # This ensures proper timing between CPU and PPU
        self.nmi_pending = False
        self.nmi_delay = 0

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
        # Clear any pending IRQ - NMI should take precedence
        self.cpu.interrupt_pending = None

        # Trigger NMI through the CPU's new interrupt system
        if hasattr(self.cpu, "trigger_interrupt"):
            debug_print(
                f"NES: Calling CPU.trigger_interrupt('NMI'), CPU PC=0x{self.cpu.PC:04X}"
            )
            self.cpu.trigger_interrupt("NMI")
        else:
            # Fallback for old CPU implementation
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

        # Clear any pending IRQ to prioritize NMI
        if (
            hasattr(self.cpu, "interrupt_pending")
            and self.cpu.interrupt_pending == "IRQ"
        ):
            self.cpu.interrupt_pending = None

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
