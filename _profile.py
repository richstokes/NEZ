import cProfile
import pstats
import time
from nes import NES

def run():
    nes = NES()
    nes.load_rom('mario.nes')
    start = time.time()
    frames = 0
    while time.time() - start < 10:
        nes.run_frame_fast()
        frames += 1
    elapsed = time.time() - start
    print(f'RESULT: {frames} frames in {elapsed:.1f}s = {frames/elapsed:.1f} fps')

pr = cProfile.Profile()
pr.enable()
run()
pr.disable()

stats = pstats.Stats(pr)
stats.sort_stats('cumulative')
stats.print_stats(40)
print("\n--- By tottime ---")
stats.sort_stats('tottime')
stats.print_stats(40)
