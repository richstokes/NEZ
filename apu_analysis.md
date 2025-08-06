# APU Analysis: Comparison with Reference Implementation

## Critical Issues Found

### 1. **Frame Sequencer Timing - CRITICAL BUG**

**Reference Implementation**: Uses precise cycle counts for NTSC/PAL timing

- NTSC: 7457, 14913, 22371, 29829 cycles for 4-step mode
- PAL: 8313, 16627, 24939, 33253 cycles for 4-step mode

**Our Implementation**: Uses simplified cycle counts that don't match hardware

- This causes incorrect envelope, sweep, and length counter timing
- Explains the clicking audio every second (wrong frame sequencer timing)

### 2. **Missing CPU Integration for DMC DMA**

**Reference Implementation**:

- DMC channel adds 3 CPU cycles for DMA stalls: `apu->emulator->cpu.dma_cycles += 3;`
- This is critical for accurate timing

**Our Implementation**: No DMA cycle handling for DMC

### 3. **Incorrect Audio Sample Generation**

**Reference Implementation**:

- Uses proper voltage levels for mixing
- Triangle: `* 3` multiplier, Noise: `* 2` multiplier  
- Proper silence handling for DMC

**Our Implementation**: Different mixing ratios

### 4. **Frame Sequencer Reset Logic**

**Reference Implementation**:

- Has `reset_sequencer` flag and immediate quarter/half frame execution on 5-step mode
- Proper IRQ handling with `interrupt(&apu->emulator->cpu, IRQ)`

**Our Implementation**: Simplified reset without immediate frame execution

### 5. **Missing Envelope Step Reset**

**Reference Implementation**: Sets `envelope.step = 15` on length counter writes
**Our Implementation**: Uses `envelope.start = True` (different approach)

### 6. **SDL2 Audio Integration Issues**

**Reference Implementation**:

- Uses adaptive sampling with queue size monitoring
- Proper audio device management with pause/unpause

**Our Implementation**: Basic SDL2 integration without adaptive sampling

## Recommended Fixes

### 1. Fix Frame Sequencer Timing (HIGHEST PRIORITY)

- Use exact NTSC/PAL cycle counts
- Implement proper reset sequencer logic
- Add CPU IRQ integration

### 2. Add DMC DMA Cycle Handling

- Integrate with CPU for DMA stalls
- Proper memory access for DMC samples

### 3. Fix Audio Mixing

- Use correct multipliers for channels
- Implement proper sample clamping
- Fix voltage level calculations

### 4. Improve SDL2 Integration

- Add adaptive sampling based on queue size
- Implement proper audio device state management

## Code Quality Assessment

Our implementation is structurally sound but has critical timing and integration issues that explain the audio problems Mario is experiencing.
