"""
NES Emulator with SDL2 Graphics
Main entry point for the emulator
"""

import sys
import os
import time
import sdl2
import sdl2.ext
from PIL import Image
import io
from nes import NES
from performance_config import apply_optimizations


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

    def take_screenshot(self, filename="exit_screenshot.png"):
        """Take a screenshot of the current SDL window state and save as PNG/JPEG"""
        try:
            # Get the size of the window
            width, height = self.window_width, self.window_height
            
            # First, make sure we have the latest frame rendered to the screen
            # Clear and render the current frame
            sdl2.SDL_SetRenderDrawColor(self.renderer, 0, 0, 0, 255)
            sdl2.SDL_RenderClear(self.renderer)
            
            if self.texture:
                sdl2.SDL_RenderCopy(self.renderer, self.texture, None, None)
            
            # Present to ensure the frame is in the framebuffer
            sdl2.SDL_RenderPresent(self.renderer)
            
            # Now create a surface to hold the pixel data
            surface = sdl2.SDL_CreateRGBSurfaceWithFormat(
                0, width, height, 32, sdl2.SDL_PIXELFORMAT_RGBA8888
            )
            
            if not surface:
                print(f"Failed to create surface for screenshot: {sdl2.SDL_GetError()}")
                return False
            
            # Read pixels directly from the current renderer
            # On Metal/macOS, this needs to happen after SDL_RenderPresent
            result = sdl2.SDL_RenderReadPixels(
                self.renderer,
                None,  # Read entire viewport
                sdl2.SDL_PIXELFORMAT_RGBA8888,
                surface.contents.pixels,
                surface.contents.pitch
            )
            
            if result != 0:
                print(f"Failed to read pixels: {sdl2.SDL_GetError()}")
                sdl2.SDL_FreeSurface(surface)
                return False
            
            # Convert SDL surface to PIL Image
            # Get raw pixel data from the surface
            import ctypes
            pixels_ptr = surface.contents.pixels
            pitch = surface.contents.pitch
            
            # Create a bytes buffer from the pixel data using ctypes
            # Cast the pixels pointer to a byte array
            pixel_buffer = ctypes.cast(pixels_ptr, ctypes.POINTER(ctypes.c_ubyte * (height * pitch)))
            pixel_data = bytes(pixel_buffer.contents)
            
            # Create PIL Image from the pixel data
            # SDL uses RGBA format with proper pitch handling
            img = Image.frombytes('RGBA', (width, height), pixel_data, 'raw', 'RGBA', pitch)
            
            # Determine output format from filename extension
            output_filename = filename
            if filename.endswith('.bmp'):
                output_filename = filename.replace('.bmp', '.png')
            
            # Save the image
            if output_filename.lower().endswith('.jpg') or output_filename.lower().endswith('.jpeg'):
                # Convert RGBA to RGB for JPEG
                rgb_img = Image.new('RGB', img.size, (0, 0, 0))
                rgb_img.paste(img, mask=img.split()[3] if len(img.split()) == 4 else None)
                rgb_img.save(output_filename, 'JPEG', quality=95)
            else:
                # Default to PNG
                if not output_filename.lower().endswith('.png'):
                    output_filename += '.png'
                img.save(output_filename, 'PNG')
            
            print(f"Screenshot saved as: {output_filename}")
            
            # Clean up the surface
            sdl2.SDL_FreeSurface(surface)
            
            return True
            
        except Exception as e:
            print(f"Error taking screenshot: {e}")
            return False

    def cleanup_sdl(self):
        """Clean up SDL2 resources"""
        # Take a screenshot before cleaning up
        if self.renderer and self.window:
            self.take_screenshot("exit_screenshot.png")
        
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
        elif key == sdl2.SDLK_F12:  # Manual screenshot
            self.take_screenshot(f"screenshot_{int(time.time())}.png")
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
        """Update SDL texture with NES screen data"""
        screen = self.nes.get_screen()

        # Convert screen pixels to bytes array for SDL_UpdateTexture
        # Texture is SDL_PIXELFORMAT_ABGR8888. On little-endian, the byte order in memory is R, G, B, A.
        pixels_bytes = bytearray(256 * 240 * 4)

        for i, pixel in enumerate(screen):
            # Pixel is stored as ABGR (0xAABBGGRR) in a 32-bit integer
            base_idx = i * 4
            # Pack bytes in memory as R, G, B, A for ABGR8888 on little-endian
            pixels_bytes[base_idx + 0] = (pixel >> 0) & 0xFF   # R
            pixels_bytes[base_idx + 1] = (pixel >> 8) & 0xFF   # G
            pixels_bytes[base_idx + 2] = (pixel >> 16) & 0xFF  # B
            pixels_bytes[base_idx + 3] = (pixel >> 24) & 0xFF  # A

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

        # Updated: use NES.load_rom instead of deprecated load_cartridge
        if not self.nes.load_rom(rom_path):
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
        print("  F12: Take screenshot")
        print("  Escape: Quit")
        print("\nNote: A screenshot will be saved automatically when you exit the emulator.")

        frame_count = 0
        start_time = time.time()

        while self.running:
            frame_start = time.time()

            # Handle events BEFORE running the frame
            self.handle_events()

            # Update controller state to NES before frame
            self.nes.set_controller_input(1, self.controller_state)

            # Run emulator for one frame - optimized
            self.nes.step_frame()

            # Update display only when necessary
            self.update_texture()
            self.render()

            # Process any pending audio samples
            if hasattr(self.nes.apu, 'audio_buffer') and len(self.nes.apu.audio_buffer) > 0:
                self.nes.apu._queue_audio()

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
