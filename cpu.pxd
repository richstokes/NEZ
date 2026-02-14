# cython: language_level=3
from memory cimport Memory

cdef class CPU:
    cdef public Memory memory
    cdef public int A, X, Y, PC, S
    cdef public int C, Z, I, D, B, V, N
    cdef public int cycles, dma_cycles, total_cycles, odd_cycle
    cdef public object interrupt_pending
    cdef public int interrupt_state
    cdef public int interrupt_inhibit, pending_interrupt_inhibit
    cdef public int interrupt_latency_remaining
    cdef public bint interrupt_latency_armed
    cdef public int interrupt_unmask_grace
    cdef public bint branch_pending
    cdef public int branch_target
    cdef public bint in_nmi
    cdef public object current_interrupt_type
    cdef public object jam_reported_at
    cdef public int current_instruction_pc
    cdef public object kil_opcodes
    cdef public list cycle_lookup
    cdef public dict instructions
    cdef public dict instruction_dispatch

    cdef void _set_zn(self, int value)
    cdef int _get_status(self)
    cdef void _set_status(self, int value)
    cdef void _push(self, int value)
    cdef int _pop(self)
    cdef bint _page_crossed(self, int a1, int a2)
    cdef int _resolve_address(self, int am, int instr_id, int *penalty)
    cdef void _handle_interrupt_c(self)
    cdef int _do_branch(self, int instr_id, int address)
    cdef int _exec(self, int instr_id, int am, int address)
    cdef int _run_instruction(self)
    cpdef int step(self)
