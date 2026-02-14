# cython: language_level=3

cdef class Memory:
    # CPU RAM (2KB mirrored)
    cdef int[2048] ram

    # Component references (set after init, typed as object for flexibility)
    cdef public object cartridge
    cdef public object ppu
    cdef public object cpu
    cdef public object apu
    cdef public object nes

    # Bus state
    cdef public int bus

    # Controller state
    cdef public int controller1, controller2
    cdef public int controller1_shift, controller2_shift
    cdef public int controller1_index, controller2_index
    cdef public int strobe

    # Instrumentation
    cdef public int ppu_status_poll_count
    cdef public int low_ram_log_count

    # ---- Hot-path methods (cpdef = C-speed from Cython, callable from Python) ----
    cpdef int read(self, int addr)
    cpdef void write(self, int addr, int value)
    cpdef int ppu_read(self, int addr)
    cpdef void ppu_write(self, int addr, int value)
