"""
NES Emulator with SDL2 Graphics
Main entry point for the emulator
"""

import sys
import os
import time
import struct
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

        # Controller state (Player 1)
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

        # Controller state (Player 2)
        self.controller2_state = {
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
        
        # Frame skipping for performance - higher = faster but choppier
        self.frame_skip = 2  # Only render every Nth frame (1 = no skip, 2 = half frames)
        self.frame_counter = 0

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

        # Create texture for NES screen (256x240 ARGB)
        self.texture = sdl2.SDL_CreateTexture(
            self.renderer,
            sdl2.SDL_PIXELFORMAT_ARGB8888,
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
        """Take a screenshot from the PPU screen buffer and save as PNG"""
        try:
            screen = self.nes.get_screen()
            img = Image.new("RGBA", (256, 240))
            pixels = []
            for argb in screen:
                a = (argb >> 24) & 0xFF
                r = (argb >> 16) & 0xFF
                g = (argb >> 8) & 0xFF
                b = argb & 0xFF
                pixels.append((r, g, b, a))
            img.putdata(pixels)

            output_filename = filename
            if not output_filename.lower().endswith('.png'):
                output_filename = os.path.splitext(output_filename)[0] + '.png'

            img.save(output_filename, 'PNG')
            print(f"Screenshot saved as: {output_filename}")
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
        # Player 1: Arrow keys + J/K/RShift/Enter
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
        # Player 2: WASD + G/H/Tab/Space
        elif key == sdl2.SDLK_g:
            self.controller2_state["A"] = True
        elif key == sdl2.SDLK_h:
            self.controller2_state["B"] = True
        elif key == sdl2.SDLK_TAB:
            self.controller2_state["Select"] = True
        elif key == sdl2.SDLK_SPACE:
            self.controller2_state["Start"] = True
        elif key == sdl2.SDLK_w:
            self.controller2_state["Up"] = True
        elif key == sdl2.SDLK_s:
            self.controller2_state["Down"] = True
        elif key == sdl2.SDLK_a:
            self.controller2_state["Left"] = True
        elif key == sdl2.SDLK_d:
            self.controller2_state["Right"] = True

        # Update controller input
        self.nes.set_controller_input(1, self.controller_state)
        self.nes.set_controller_input(2, self.controller2_state)

    def handle_keyup(self, key):
        """Handle key release"""
        # Player 1
        if key == sdl2.SDLK_j:
            self.controller_state["A"] = False
        elif key == sdl2.SDLK_k:
            self.controller_state["B"] = False
        elif key == sdl2.SDLK_RSHIFT:
            self.controller_state["Select"] = False
        elif key == sdl2.SDLK_RETURN:
            self.controller_state["Start"] = False
        elif key == sdl2.SDLK_UP:
            self.controller_state["Up"] = False
        elif key == sdl2.SDLK_DOWN:
            self.controller_state["Down"] = False
        elif key == sdl2.SDLK_LEFT:
            self.controller_state["Left"] = False
        elif key == sdl2.SDLK_RIGHT:
            self.controller_state["Right"] = False
        # Player 2
        elif key == sdl2.SDLK_g:
            self.controller2_state["A"] = False
        elif key == sdl2.SDLK_h:
            self.controller2_state["B"] = False
        elif key == sdl2.SDLK_TAB:
            self.controller2_state["Select"] = False
        elif key == sdl2.SDLK_SPACE:
            self.controller2_state["Start"] = False
        elif key == sdl2.SDLK_w:
            self.controller2_state["Up"] = False
        elif key == sdl2.SDLK_s:
            self.controller2_state["Down"] = False
        elif key == sdl2.SDLK_a:
            self.controller2_state["Left"] = False
        elif key == sdl2.SDLK_d:
            self.controller2_state["Right"] = False

        # Update controller input
        self.nes.set_controller_input(1, self.controller_state)
        self.nes.set_controller_input(2, self.controller2_state)

    def update_texture(self):
        """Update SDL texture with NES screen data - optimized"""
        screen = self.nes.get_screen()
        # Fast pack using struct - converts list of ints to bytes directly
        try:
            pixels_bytes = struct.pack(f'{len(screen)}I', *screen)
        except struct.error:
            # Some pixel value is outside unsigned 32-bit range; log and mask
            bad = [(i, v) for i, v in enumerate(screen) if v < 0 or v > 0xFFFFFFFF]
            if bad:
                print(f"Warning: {len(bad)} screen pixel(s) out of uint32 range, e.g. {bad[:3]}")
            pixels_bytes = struct.pack(f'{len(screen)}I', *(v & 0xFFFFFFFF for v in screen))
        sdl2.SDL_UpdateTexture(self.texture, None, pixels_bytes, 256 * 4)

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
        print("Controls (Player 1):")
        print("  Arrow keys: D-pad")
        print("  J: A button")
        print("  K: B button")
        print("  Right Shift: Select")
        print("  Enter: Start")
        print("Controls (Player 2):")
        print("  WASD: D-pad")
        print("  G: A button")
        print("  H: B button")
        print("  Tab: Select")
        print("  Space: Start")
        print("General:")
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
            self.nes.set_controller_input(2, self.controller2_state)

            # Run emulator for one frame
            self.nes.ppu.render = False
            step_count = 0
            ppu_render = self.nes.ppu
            nes_step = self.nes.step
            while not ppu_render.render and step_count < 200000:
                nes_step()
                step_count += 1
                # Handle events every ~10000 steps to keep UI responsive
                if step_count % 10000 == 0:
                    self.handle_events()
                    if not self.running:
                        break

            # Frame skipping - only update display every Nth frame
            self.frame_counter += 1
            if self.frame_counter >= self.frame_skip:
                self.frame_counter = 0
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


def run_headless(rom_path, duration=60, screenshot_path="headless_screenshot.png"):
    """Run the emulator in headless mode (no SDL window).
    Prints periodic stats and saves a final screenshot.
    """
    from PIL import Image

    nes = NES()
    if not nes.load_rom(rom_path):
        print(f"Failed to load ROM: {rom_path}")
        return 1

    nes.reset()
    apply_optimizations()

    print(f"Headless mode: running {rom_path} for {duration}s ...")
    start = time.time()
    frame_count = 0
    last_report = start

    try:
        while True:
            elapsed = time.time() - start
            if elapsed >= duration:
                break

            # Run one frame using the fast path
            nes.run_frame_fast()

            frame_count += 1

            # Report every 5 seconds
            now = time.time()
            if now - last_report >= 5.0:
                fps = frame_count / (now - start)
                cpu = nes.get_cpu_state()
                ppu = nes.get_ppu_state()
                print(
                    f"[{elapsed:6.1f}s] frames={frame_count}  "
                    f"fps={fps:.1f}  "
                    f"PC=${cpu['PC']:04X}  "
                    f"scanline={ppu['scanline']}  "
                    f"ppu_frame={ppu['frame']}"
                )
                last_report = now
    except KeyboardInterrupt:
        print("\nStopped early by user")

    elapsed = time.time() - start
    fps = frame_count / elapsed if elapsed > 0 else 0
    print(f"\nDone: {frame_count} frames in {elapsed:.1f}s ({fps:.1f} fps)")

    # Save final screenshot from the PPU screen buffer (ARGB format)
    screen = nes.get_screen()
    img = Image.new("RGBA", (256, 240))
    pixels = []
    for argb in screen:
        a = (argb >> 24) & 0xFF
        r = (argb >> 16) & 0xFF
        g = (argb >> 8) & 0xFF
        b = argb & 0xFF
        pixels.append((r, g, b, a))
    img.putdata(pixels)
    img.save(screenshot_path)
    print(f"Screenshot saved to {screenshot_path}")
    return 0


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="NEZ - NES Emulator")
    parser.add_argument("rom", help="Path to ROM file (e.g. mario.nes)")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without a window (no SDL). Prints progress and saves a screenshot.",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Headless mode duration in seconds (default: 60)",
    )
    parser.add_argument(
        "--screenshot",
        default="headless_screenshot.png",
        help="Path for the headless-mode screenshot (default: headless_screenshot.png)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.rom):
        print(f"ROM file not found: {args.rom}")
        return 1

    if args.headless:
        return run_headless(args.rom, args.duration, args.screenshot)

    emulator = NEZEmulator()

    # Apply performance optimizations
    apply_optimizations()

    try:
        success = emulator.run(args.rom)
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\nEmulator stopped by user")
        return 0
    except Exception as e:
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
