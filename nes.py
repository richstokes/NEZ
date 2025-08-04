"""
Main NES Emulator Class
Coordinates CPU, PPU, and Memory components
"""

from cpu import CPU
from ppu import PPU
from memory import Memory, Cartridge


class NES:
    def __init__(self):
        # Initialize components
        self.memory = Memory()
        self.ppu = PPU(self.memory)
        self.cpu = CPU(self.memory)

        # Connect components
        self.memory.set_ppu(self.ppu)
        self.memory.set_cpu(self.cpu)
        self.ppu.memory = self.memory

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

    def reset(self):
        """Reset the NES"""
        self.cpu.reset()
        self.ppu.reset()
        self.cpu_cycles = 0
        self.ppu_cycles = 0
        self.nmi_pending = False
        self.nmi_delay = 0
        print("NES Reset")

    def step_frame(self):
        """Step one complete frame (29780.5 CPU cycles)"""
        target_cycles = self.cpu_cycles + 29781

        while self.cpu_cycles < target_cycles:
            self.step()

        return self.ppu.screen

    def step(self):
        """Step one CPU cycle"""
        # Handle NMI
        if self.nmi_pending:
            if self.nmi_delay > 0:
                self.nmi_delay -= 1
            else:
                self.handle_nmi()
                self.nmi_pending = False

        # Step CPU
        self.cpu.step()
        self.cpu_cycles += 1

        # Step PPU (3 PPU cycles per CPU cycle)
        for _ in range(3):
            old_status = self.ppu.status
            self.ppu.step()

            # Check for VBlank NMI
            if (self.ppu.status & 0x80) and not (old_status & 0x80):
                if self.ppu.ctrl & 0x80:  # NMI enabled
                    self.nmi_pending = True
                    self.nmi_delay = 2  # 2 cycle delay

            self.ppu_cycles += 1

    def handle_nmi(self):
        """Handle Non-Maskable Interrupt"""
        # Push PC and status to stack
        self.cpu.push_stack((self.cpu.PC >> 8) & 0xFF)
        self.cpu.push_stack(self.cpu.PC & 0xFF)
        self.cpu.push_stack(self.cpu.get_status_byte())

        # Set interrupt disable flag
        self.cpu.I = 1

        # Jump to NMI vector
        low = self.memory.read(0xFFFA)
        high = self.memory.read(0xFFFB)
        self.cpu.PC = (high << 8) | low

        # Add cycles for NMI
        self.cpu.cycles += 7

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
