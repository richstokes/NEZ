"""
NES Emulator with SDL2 Graphics
Main entry point for the emulator
"""

import sys
import os
import time
import sdl2
import sdl2.ext
from nes import NES
from performance_config import apply_optimizations
from utils import debug_print


class NEZEmulator:
    def __init__(self):
        self.nes = NES()
        self.running = False

        # Display settings
        self.window_width = 768  # 256 * 3
        self.window_height = 720  # 240 * 3
        self.scale = 3

        # SDL components
        self.window = None
        self.renderer = None
        self.texture = None
        self.audio_stream = None
        self.audio_device = None

        # Controller state
        self.controller_state = {
            "A": False,
            "B": False,
            "Select": False,
            "Start": False,
            "Up": False,
            "Down": False,
            "Left": False,
            "Right": False,
        }

        # Timing
        self.last_frame_time = 0
        self.target_fps = 60
        self.frame_time = 1.0 / self.target_fps

    def initialize_sdl(self):
        """Initialize SDL2"""
        if (
            sdl2.SDL_Init(
                sdl2.SDL_INIT_VIDEO | sdl2.SDL_INIT_AUDIO | sdl2.SDL_INIT_EVENTS
            )
            != 0
        ):
            print(f"SDL2 initialization failed: {sdl2.SDL_GetError()}")
            return False

        # Create window
        self.window = sdl2.SDL_CreateWindow(
            b"NEZ - NES Emulator",
            sdl2.SDL_WINDOWPOS_CENTERED,
            sdl2.SDL_WINDOWPOS_CENTERED,
            self.window_width,
            self.window_height,
            sdl2.SDL_WINDOW_SHOWN,
        )

        if not self.window:
            print(f"Window creation failed: {sdl2.SDL_GetError()}")
            return False

        # Create renderer
        self.renderer = sdl2.SDL_CreateRenderer(
            self.window,
            -1,
            sdl2.SDL_RENDERER_ACCELERATED | sdl2.SDL_RENDERER_PRESENTVSYNC,
        )

        if not self.renderer:
            print(f"Renderer creation failed: {sdl2.SDL_GetError()}")
            return False

        # Create texture for NES screen (256x240 ABGR) to match reference implementation
        self.texture = sdl2.SDL_CreateTexture(
            self.renderer,
            sdl2.SDL_PIXELFORMAT_ABGR8888,
            sdl2.SDL_TEXTUREACCESS_STREAMING,
            256,
            240,
        )

        if not self.texture:
            print(f"Texture creation failed: {sdl2.SDL_GetError()}")
            return False

        # Create audio device for sound output (SDL2 style)
        desired = sdl2.SDL_AudioSpec(48000, sdl2.AUDIO_S16, 1, 1024)

        obtained = sdl2.SDL_AudioSpec(0, 0, 0, 0)
        self.audio_device = sdl2.SDL_OpenAudioDevice(None, 0, desired, obtained, 0)

        if self.audio_device == 0:
            print(f"Audio device creation failed: {sdl2.SDL_GetError()}")
            return False

        # For compatibility, we'll create a simple audio stream simulation
        self.audio_stream = self.audio_device

        print("SDL2 initialized successfully")
        return True

    def cleanup_sdl(self):
        """Clean up SDL2 resources"""
        if hasattr(self, "audio_device") and self.audio_device:
            sdl2.SDL_CloseAudioDevice(self.audio_device)
        if self.texture:
            sdl2.SDL_DestroyTexture(self.texture)
        if self.renderer:
            sdl2.SDL_DestroyRenderer(self.renderer)
        if self.window:
            sdl2.SDL_DestroyWindow(self.window)
        sdl2.SDL_Quit()

    def handle_events(self):
        """Handle SDL events"""
        event = sdl2.SDL_Event()

        # debug_print(f"Handling events - {self.running}")

        while sdl2.SDL_PollEvent(event):
            if event.type == sdl2.SDL_QUIT:
                self.running = False

            elif event.type == sdl2.SDL_KEYDOWN:
                self.handle_keydown(event.key.keysym.sym)

            elif event.type == sdl2.SDL_KEYUP:
                self.handle_keyup(event.key.keysym.sym)

    def handle_keydown(self, key):
        """Handle key press"""
        if key == sdl2.SDLK_ESCAPE:
            self.running = False
        elif key == sdl2.SDLK_r or key == sdl2.SDLK_F5:  # Reset like reference
            self.nes.reset()
            print("Reset NES")
        elif key == sdl2.SDLK_j:  # A button (match reference: J)
            self.controller_state["A"] = True
        elif key == sdl2.SDLK_k:  # B button (match reference: K)
            self.controller_state["B"] = True
        elif key == sdl2.SDLK_RSHIFT:  # Select (match reference: Shift)
            self.controller_state["Select"] = True
        elif key == sdl2.SDLK_RETURN:  # Start (match reference: Enter)
            self.controller_state["Start"] = True
        elif key == sdl2.SDLK_UP:
            self.controller_state["Up"] = True
        elif key == sdl2.SDLK_DOWN:
            self.controller_state["Down"] = True
        elif key == sdl2.SDLK_LEFT:
            self.controller_state["Left"] = True
        elif key == sdl2.SDLK_RIGHT:
            self.controller_state["Right"] = True

        # Update controller input
        self.nes.set_controller_input(1, self.controller_state)

    def handle_keyup(self, key):
        """Handle key release"""
        if key == sdl2.SDLK_j:  # A button (match reference: J)
            self.controller_state["A"] = False
        elif key == sdl2.SDLK_k:  # B button (match reference: K)
            self.controller_state["B"] = False
        elif key == sdl2.SDLK_RSHIFT:  # Select (match reference: Shift)
            self.controller_state["Select"] = False
        elif key == sdl2.SDLK_RETURN:  # Start (match reference: Enter)
            self.controller_state["Start"] = False
        elif key == sdl2.SDLK_UP:
            self.controller_state["Up"] = False
        elif key == sdl2.SDLK_DOWN:
            self.controller_state["Down"] = False
        elif key == sdl2.SDLK_LEFT:
            self.controller_state["Left"] = False
        elif key == sdl2.SDLK_RIGHT:
            self.controller_state["Right"] = False

        # Update controller input
        self.nes.set_controller_input(1, self.controller_state)

    def update_texture(self):
        """Update SDL texture with NES screen data - matching reference implementation"""
        screen = self.nes.get_screen()
        
        # Debug: Check if screen has non-zero pixels
        non_zero_pixels = sum(1 for pixel in screen if pixel != 0)
        if non_zero_pixels > 0:
            debug_print(f"Screen has {non_zero_pixels} non-zero pixels, first few: {screen[:10]}")

        # Convert screen pixels to bytes array for SDL_UpdateTexture
        # SDL expects ABGR8888 format: A, B, G, R bytes in sequence
        pixels_bytes = bytearray(256 * 240 * 4)

        for i, pixel in enumerate(screen):
            # Extract ABGR components from 32-bit pixel value
            # Our palette is already in ABGR format from PPU
            base_idx = i * 4
            pixels_bytes[base_idx] = pixel & 0xFF  # A
            pixels_bytes[base_idx + 1] = (pixel >> 8) & 0xFF  # B
            pixels_bytes[base_idx + 2] = (pixel >> 16) & 0xFF  # G
            pixels_bytes[base_idx + 3] = (pixel >> 24) & 0xFF  # R

        # Update texture with correct byte order
        sdl2.SDL_UpdateTexture(self.texture, None, bytes(pixels_bytes), 256 * 4)

    def render(self):
        """Render the current frame"""
        # Clear screen
        sdl2.SDL_SetRenderDrawColor(self.renderer, 0, 0, 0, 255)
        sdl2.SDL_RenderClear(self.renderer)

        # Render NES screen
        sdl2.SDL_RenderCopy(self.renderer, self.texture, None, None)

        # Present
        sdl2.SDL_RenderPresent(self.renderer)

    def run(self, rom_path):
        """Run the emulator"""
        if not self.initialize_sdl():
            return False

        if not self.nes.load_cartridge(rom_path):
            self.cleanup_sdl()
            return False

        # Initialize APU with audio stream
        self.nes.apu.init_audio_stream(self.audio_stream)

        self.nes.reset()
        self.running = True

        # Start audio playback
        if hasattr(self, "audio_device") and self.audio_device:
            sdl2.SDL_PauseAudioDevice(self.audio_device, 0)

        print("Starting emulator...")
        print("Controls:")
        print("  Arrow keys: D-pad")
        print("  J: A button")
        print("  K: B button")
        print("  Right Shift: Select")
        print("  Enter: Start")
        print("  R: Reset")
        print("  Escape: Quit")

        frame_count = 0
        start_time = time.time()

        while self.running:
            frame_start = time.time()

            # Handle events
            self.handle_events()

            # Run emulator for one frame - optimized
            self.nes.step_frame()

            # Update display only when necessary
            self.update_texture()
            self.render()

            frame_count += 1

            # Print FPS less frequently for performance
            if frame_count % 120 == 0:  # Every 2 seconds instead of 1
                elapsed = time.time() - start_time
                fps = frame_count / elapsed if elapsed > 0 else 0
                print(f"FPS: {fps:.1f}")

            # Optimized frame timing - reduce sleep granularity
            frame_end = time.time()
            frame_duration = frame_end - frame_start

            if frame_duration < self.frame_time:
                sleep_time = self.frame_time - frame_duration
                if sleep_time > 0.001:  # Only sleep if significant time remains
                    time.sleep(sleep_time)

        self.cleanup_sdl()
        return True


def main():
    """Main entry point"""
    if len(sys.argv) != 2:
        print("Usage: python main.py <rom_file>")
        print("Example: python main.py mario.nes")
        return 1

    rom_path = sys.argv[1]

    if not os.path.exists(rom_path):
        print(f"ROM file not found: {rom_path}")
        return 1

    emulator = NEZEmulator()

    # Apply performance optimizations
    apply_optimizations()

    try:
        success = emulator.run(rom_path)
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\nEmulator stopped by user")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
