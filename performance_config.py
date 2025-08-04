"""
Performance configuration for NEZ emulator
Contains optimizations based on the reference C implementation analysis
"""

# CPU optimizations
CPU_OPTIMIZATIONS = {
    "use_dispatch_table": True,  # Use function dispatch table instead of getattr
    "bulk_processing": True,  # Process multiple cycles at once when possible
    "fast_memory_access": True,  # Optimize memory access patterns
    "reduced_debug_output": True,  # Minimize debug/trace output
}

# PPU optimizations
PPU_OPTIMIZATIONS = {
    "skip_invisible_rendering": True,  # Skip rendering for invisible scanlines
    "fast_pixel_update": True,  # Optimize pixel buffer updates
    "batch_screen_updates": True,  # Update screen in batches
    "sprite_eval_optimization": True,  # Optimize sprite evaluation
}

# APU optimizations
APU_OPTIMIZATIONS = {
    "reduced_sample_rate": True,  # Generate fewer audio samples
    "timer_batching": True,  # Batch timer updates
    "fast_mixing": True,  # Use optimized mixing algorithms
}

# Main loop optimizations
MAIN_LOOP_OPTIMIZATIONS = {
    "frame_skip": False,  # Skip frames if running too slow
    "adaptive_timing": True,  # Adapt timing based on performance
    "reduced_fps_reporting": True,  # Report FPS less frequently
    "sleep_optimization": True,  # Optimize sleep timing
}

# Memory optimizations
MEMORY_OPTIMIZATIONS = {
    "cache_frequent_reads": True,  # Cache frequently accessed memory
    "fast_mapper_access": True,  # Optimize cartridge mapper access
    "reduced_bounds_checking": False,  # Disable for safety, but can improve speed
}

# Graphics optimizations
GRAPHICS_OPTIMIZATIONS = {
    "texture_reuse": True,  # Reuse texture memory
    "pixel_buffer_optimization": True,  # Optimize pixel buffer handling
    "vsync_disable": False,  # Disable VSync for higher FPS (may cause tearing)
}


def apply_optimizations():
    """Apply performance optimizations"""
    print("Performance optimizations enabled:")
    for category, opts in [
        ("CPU", CPU_OPTIMIZATIONS),
        ("PPU", PPU_OPTIMIZATIONS),
        ("APU", APU_OPTIMIZATIONS),
        ("Main Loop", MAIN_LOOP_OPTIMIZATIONS),
        ("Memory", MEMORY_OPTIMIZATIONS),
        ("Graphics", GRAPHICS_OPTIMIZATIONS),
    ]:
        enabled = [k for k, v in opts.items() if v]
        if enabled:
            print(f"  {category}: {', '.join(enabled)}")
