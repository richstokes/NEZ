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
        if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO | sdl2.SDL_INIT_EVENTS) != 0:
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

        # Create texture for NES screen
        self.texture = sdl2.SDL_CreateTexture(
            self.renderer,
            sdl2.SDL_PIXELFORMAT_RGB24,
            sdl2.SDL_TEXTUREACCESS_STREAMING,
            256,
            240,
        )

        if not self.texture:
            print(f"Texture creation failed: {sdl2.SDL_GetError()}")
            return False

        print("SDL2 initialized successfully")
        return True

    def cleanup_sdl(self):
        """Clean up SDL2 resources"""
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
        elif key == sdl2.SDLK_r:
            self.nes.reset()
            print("Reset NES")
        elif key == sdl2.SDLK_z:  # A button
            self.controller_state["A"] = True
        elif key == sdl2.SDLK_x:  # B button
            self.controller_state["B"] = True
        elif key == sdl2.SDLK_SPACE:  # Select
            self.controller_state["Select"] = True
        elif key == sdl2.SDLK_RETURN:  # Start
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
        if key == sdl2.SDLK_z:  # A button
            self.controller_state["A"] = False
        elif key == sdl2.SDLK_x:  # B button
            self.controller_state["B"] = False
        elif key == sdl2.SDLK_SPACE:  # Select
            self.controller_state["Select"] = False
        elif key == sdl2.SDLK_RETURN:  # Start
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
        """Update SDL texture with NES screen data"""
        screen = self.nes.get_screen()

        # Convert screen data to bytes
        pixels = []

        for y in range(240):
            for x in range(256):
                color = screen[y][x]
                pixels.extend([color[0], color[1], color[2]])  # R, G, B

        # Convert to bytes
        pixels_bytes = bytes(pixels)

        # Update texture
        sdl2.SDL_UpdateTexture(self.texture, None, pixels_bytes, 256 * 3)

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

        self.nes.reset()
        self.running = True

        print("Starting emulator...")
        print("Controls:")
        print("  Arrow keys: D-pad")
        print("  Z: A button")
        print("  X: B button")
        print("  Space: Select")
        print("  Enter: Start")
        print("  R: Reset")
        print("  Escape: Quit")

        frame_count = 0
        start_time = time.time()

        while self.running:
            frame_start = time.time()

            # Handle events
            self.handle_events()

            # Run emulator for one frame
            self.nes.step_frame()

            # Update display
            self.update_texture()
            self.render()

            frame_count += 1

            # Print FPS every second
            if frame_count % 60 == 0:
                elapsed = time.time() - start_time
                fps = frame_count / elapsed if elapsed > 0 else 0
                print(f"FPS: {fps:.1f}")

            # Frame timing
            frame_end = time.time()
            frame_duration = frame_end - frame_start

            if frame_duration < self.frame_time:
                time.sleep(self.frame_time - frame_duration)

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
