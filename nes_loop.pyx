# cython: boundscheck=False, wraparound=False, cdivision=True, language_level=3
"""
Tight NES frame loop — Cython accelerated.
Calls cpu.step() and ppu.step() at C level via cimport.
APU step uses Python dispatch (only 1 call per CPU cycle, not a bottleneck).
"""
from cpu cimport CPU
from ppu cimport PPU


def run_frame_fast(object nes):
    """Run one complete frame with C-level dispatch for CPU/PPU."""
    cdef CPU cpu = <CPU>nes.cpu
    cdef PPU ppu = <PPU>nes.ppu
    apu = nes.apu
    apu_step = apu.step

    ppu.render = False

    cdef int nmi_pending = 1 if nes.nmi_pending else 0
    cdef int nmi_delay = nes.nmi_delay
    cdef int cpu_cycles_total = nes.cpu_cycles
    cdef int ppu_cycles_total = nes.ppu_cycles
    cdef int step_limit = 200000
    cdef int steps = 0
    cdef int cc, ppu_n, i

    while not ppu.render and steps < step_limit:
        steps += 1

        # Inline NMI handling
        if nmi_pending:
            if nmi_delay > 0:
                nmi_delay -= 1
                nes.nmi_delay = nmi_delay
            else:
                nes.nmi_pending = False
                nes.handle_nmi()
                nmi_pending = 0
            # Re-read in case handler changed them
            nmi_pending = 1 if nes.nmi_pending else 0
            nmi_delay = nes.nmi_delay

        # CPU step — C-level call via cimport
        cc = cpu.step()
        cpu_cycles_total += cc

        # PPU: 3 cycles per CPU cycle (NTSC) — C-level calls
        ppu_n = cc * 3
        for i in range(ppu_n):
            ppu.step()
        ppu_cycles_total += ppu_n

        # APU: 1 cycle per CPU cycle — Python dispatch
        for i in range(cc):
            apu_step()

        # Re-sync NMI state (PPU may trigger NMI during its step)
        nmi_pending = 1 if nes.nmi_pending else 0
        nmi_delay = nes.nmi_delay

    # Write back counters
    nes.cpu_cycles = cpu_cycles_total
    nes.ppu_cycles = ppu_cycles_total
    nes.nmi_pending = True if nmi_pending else False
    nes.nmi_delay = nmi_delay

    return ppu.screen
