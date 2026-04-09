# RayCast3D

A pseudo-3D graphics library for the ST7735R display using raycasting techniques.

## Overview

RayCast3D is designed for ECE 319K students working with the MSPM0 microcontroller. It provides a simple interface for rendering pseudo-3D environments on the ST7735R LCD display using raycasting algorithms.

## Quick Start

### 1. Get the library

**Option A — Download ZIP:**
1. Download the latest release ZIP from the repository
2. Extract the contents into a folder called `RayCast3D` inside your CCS project directory for Lab 9 (e.g., `Lab9/RayCast3D/`)

**Option B — Git clone:**
```bash
cd <your-Lab9-project-folder>
git clone https://github.com/esilguero1/RayCast3D.git
rm -rf RayCast3D/.git
```

### 2. Include the header and start rendering

Add a single include to your `main.c` to get the full API:

```c
#include "RayCast3D/raycast3d.h"
```

Then initialize and render:

```c
int main(void) {
    LaunchPad_Init();

    // Initialize engine (clock, display, DMA)
    RayCast3D_Init();

    // Configure scene
    Graphics_SetFloorColor(ST7735_DARKGREY);
    Graphics_SetSkyColor(ST7735_BLUE);
    Map_Load(map1);
    Camera_SetPosition(12.0, 12.0);

    // Main loop
    while (1) {
        RayCast3D_Render();
        // ... handle input, update camera, etc.
    }
}
```

## Hardware Requirements

- MSPM0 MCU
- ST7735R LCD Display

## Dependencies

This library requires the following external Valvanoware files:

- `inc/Clock.h` / `Clock.c` - Clock configuration and delay functions
- `inc/ST7735.h` / `ST7735.c` - ST7735 LCD driver (initialization and basic drawing)
- `inc/SPI.h` / `SPI.c` - SPI bus driver
- `inc/file.h` / `file.c` - File system support (dependency of ST7735.c)

These files are provided in the ECE 319K Valvanoware distribution and should be in the `inc/` directory.

**Note:** The library includes its own DMA-accelerated display driver (`ST7735_DMA.c`, `SPI_DMA.c`) for high-performance rendering. The external ST7735/SPI files are only needed for initialization.

## RayCast3D Studio

A GUI application for creating and managing game assets. Requires Python 3 to be installed.

### Running the Studio

1. In CCS Project Explorer, right-click `RayCast3D_Studio.py` and select **Open Containing Folder**
2. Double-click the launcher for your OS:
   - **Windows:** `run_studio.bat`
   - **macOS:** `run_studio.command`
   - **Linux:** `run_studio.sh`

Dependencies (Pillow) are installed automatically on first launch.

### Features

- **Map Editor** — 24x24 grid editor with click-and-drag wall placement. Supports multiple maps with add/rename/delete. Perimeter walls are enforced automatically. Per-map floor and ceiling texture assignment.

- **Texture Manager** — Import textures from image files (PNG, JPG, etc.). Supports 16x16, 32x32, 64x64, and 128x128 resolutions. Each texture can have a different resolution for quality/memory trade-offs. Preview shows simulated in-game wall appearance.

- **Sprite Editor** — Import sprite images with automatic transparent color detection. The editor provides a single editing canvas with a sidebar tool panel:
  - **Pick Color** — Click any pixel to set it as the transparent color
  - **Fill Match** — Click a pixel to make all identically-colored pixels transparent
  - **Erase** — Paint pixels to transparent with an adjustable circular brush
  - **Restore** — Paint over erased areas to make them opaque again
  - **Crop** — Select and resize a region from the original source image
  - Scroll to zoom and middle-click to pan for precise pixel-level editing
  - Source reference thumbnail for comparison alongside the live transparency preview
  - Undo support (Ctrl+Z) for all editing operations

- **Color Picker** — Define named colors with a visual color picker. Colors are exported as BGR565 constants for use with `Graphics_SetFloorColor()`, `Graphics_SetSkyColor()`, etc.

### Auto-Export

The Studio automatically exports to the `assets/` folder:

| File | Contents |
|------|----------|
| `textures.h` | Wall textures with `TextureInfo` structs |
| `maps.h` | Map data arrays and `mapList[]` pointer array |
| `images.h` | Sprite images with `SpriteImage` structs and `AddSprite` macro |
| `colors.h` | Named color constants in BGR565 format |

## API Modules

- **Engine Core** — initialization and rendering
- **Camera** — movement and orientation
- **Graphics** — visual configuration
- **Map** — world data
- **Sprites** — dynamic objects
- **Fixed Point** — math that doesn't need an FPU

For full API details, see the [documentation](https://esilguero1.github.io/RayCast3D/).

## Performance Optimizations

### Fixed-Point Math (Q16.16)

All raycasting math uses Q16.16 fixed-point arithmetic for optimal performance on the MSPM0 (which lacks an FPU). This provides:

- **16-bit integer part**: Range of -32768 to +32767
- **16-bit fractional part**: Precision of ~0.00002

Key optimizations:
- Lookup tables for `sin`/`cos` (256 entries with quadrant mirroring)
- Reciprocal lookup tables to minimize division operations
- Precomputed constants (`SCREEN_HEIGHT_SHIFTED`, texture masks)

### Rotation Drift Prevention

Repeated fixed-point multiplications can cause precision loss, leading to the direction vector drifting from unit length over time. This manifests as walls appearing to move closer or farther without player movement.

**Solution**: After each rotation, the direction vector is re-normalized:
```c
fixed_t lenSq = fixed_mul(dirX, dirX) + fixed_mul(dirY, dirY);
fixed_t len = fixed_sqrt(lenSq);
dirX = fixed_div(dirX, len);
dirY = fixed_div(dirY, len);
```

### Drift Verification (Tested)

The drift fix was verified using a debug display that tracks the direction vector magnitude across rotations:

- `|dir|` — squared magnitude of the direction vector (expected: **65536** = 1.0²)
- `r` — total rotation count

**Test results**: After hundreds of rotations, `|dir|` remained stable at 65536, confirming the re-normalization successfully prevents drift.

### DMA-Accelerated Display Transfer

The library uses DMA (Direct Memory Access) to transfer pixel data to the ST7735 display, allowing the CPU to render the next frame segment while the previous one is being transmitted over SPI.

**Quarter-screen double-buffering:**
- Screen is divided into 4 vertical strips (40×128 pixels each)
- Two 10KB buffers swap roles: one for rendering, one for DMA
- Total RAM: 20KB (same as a single half-screen buffer)

**Rendering pipeline:**
```
Q0: Render to A → Start DMA from A
Q1: Render to B (while DMA sends A) → Wait for DMA → Start DMA from B
Q2: Render to A (while DMA sends B) → Wait for DMA → Start DMA from A
Q3: Render to B (while DMA sends A) → Wait for DMA → Start DMA from B
```

**Key optimizations:**
- **Pointer swap**: No memory copy between buffers — just swap pointers
- **Pre-swapped pixels**: Byte-swap (for ST7735 MSB-first) happens at render time, not DMA time
- **Y-inverted storage**: Buffer layout matches ST7735 scanline order, eliminating row reordering
- **~100% SPI utilization**: CPU and DMA run in parallel with minimal idle time

**Hardware resource:** DMA Channel 0 is reserved for display transfers and is not available for other uses.

## License

For educational use in ECE 319K.
