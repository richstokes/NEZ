#!/usr/bin/env python3
import sys
import time
import argparse
import importlib
from nes import NES
from utils import set_debug


def main():
    parser = argparse.ArgumentParser(description="Headless NES run to generate logs without SDL.")
    parser.add_argument("rom", nargs="?", default="mario.nes", help="Path to ROM file")
    parser.add_argument("--frames", type=int, default=90, help="Number of frames to run")
    parser.add_argument("--out", default=None, help="Path to write full debug log output (optional)")
    parser.add_argument("--hits", default=None, help="Path to write filtered sprite0 hit lines (optional)")
    parser.add_argument(
        "--continue-after-hit",
        action="store_true",
        help="Do not stop early when a genuine sprite0 hit occurs; run the full frame count",
    )
    args = parser.parse_args()

    # Disable global debug prints (we'll intercept only PPU sprite0 lines)
    set_debug(False)

    # Optional full log redirection
    log_fp = None
    if args.out:
        log_fp = open(args.out, "w", buffering=1)
        sys.stdout = log_fp

    # Intercept PPU/module-level debug_print to count events and log filtered lines
    spr0_hit_count = 0
    forced_hit_count = 0
    filtered_fp = open(args.hits, "w", buffering=1) if args.hits else None

    def debug_wrapper(msg: str):
        nonlocal spr0_hit_count, forced_hit_count
        # Capture key PPU events
        key = False
        if "PPU: Sprite0 hit SET" in msg:
            spr0_hit_count += 1
            key = True
        elif "FORCED SPR0 HIT" in msg:
            forced_hit_count += 1
            key = True
        elif "SPR0 PIXEL PROBE" in msg or "SPR0 OVERLAP PROBE" in msg or "SPR0 COMMIT" in msg:
            key = True
        elif "WRITE $2001" in msg or "FIRST $2001" in msg or "PPU: RENDERING ENABLED" in msg:
            key = True
        elif "WRITE $2000" in msg or "FIRST $2000" in msg:
            key = True
        elif "BG PAT LOW" in msg or "BG PAT HIGH" in msg or "BG TILE FETCH" in msg:
            key = True
        elif "PPU PROBE2" in msg or "BG PIXEL PROBE" in msg:
            key = True
        elif "SPR0 PATFETCH" in msg:
            key = True
        elif "OAM[0.." in msg or "Sprite 0 " in msg:
            key = True
        elif "PPU: New frame start" in msg:
            key = True
        if key and filtered_fp:
            filtered_fp.write(msg + "\n")
        # Also write to stdout if full log requested
        if log_fp is None:
            # No full log: do nothing for other messages to keep output small
            return
        print(msg)

    # Replace debug_print in ppu module so PPU logs go through our wrapper
    ppu_mod = importlib.import_module("ppu")
    ppu_mod.debug_print = debug_wrapper

    nes = NES()

    if not nes.load_rom(args.rom):
        print(f"Failed to load ROM: {args.rom}")
        if log_fp:
            log_fp.close()
        if filtered_fp:
            filtered_fp.close()
        return 1

    nes.reset()

    start = time.time()
    for i in range(args.frames):
        nes.step_frame()
        # Stop early if we observed a real sprite0 hit (unless asked to continue)
        if spr0_hit_count > 0 and not args.continue_after_hit:
            break
    elapsed = time.time() - start

    # Determine how many frames actually executed
    actual_frames = i + 1 if args.frames > 0 else 0

    # Write summary to stdout (not redirected unless --out set)
    if log_fp is not None:
        # Ensure we also see the summary in the filtered file
        print(f"Headless run complete: frames={actual_frames}, elapsed={elapsed:.3f}s, spr0_hits={spr0_hit_count}, forced_hits={forced_hit_count}")
    else:
        # If stdout wasn't redirected, print summary to console
        sys.stdout.write(
            f"Headless run complete: frames={actual_frames}, elapsed={elapsed:.3f}s, spr0_hits={spr0_hit_count}, forced_hits={forced_hit_count}\n"
        )
    if filtered_fp:
        filtered_fp.close()
    if log_fp:
        log_fp.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

