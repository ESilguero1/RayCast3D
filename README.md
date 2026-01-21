# RayCast3D

A pseudo-3D graphics library for the ST7735R display using raycasting techniques.

## Overview

RayCast3D is designed for ECE 319K students working with the MSPM0 microcontroller. It provides a simple interface for rendering pseudo-3D environments on the ST7735R LCD display using raycasting algorithms.

## Quick Start

```c
#include "RayCast3D/raycast3d.h"

int main(void) {
    LaunchPad_Init();

    // Initialize engine (clock, display, DMA)
    RayCast3D_Init();

    // Configure scene
    Graphics_SetFloorColor(ST7735_DARKGREY);
    Graphics_SetSkyColor(SKY);
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

These files are provided in the ECE 319K Valvanoware distribution and should be placed in an `inc/` directory at the same level as the `RayCast3D/` folder.

**Note:** The library includes its own DMA-accelerated display driver (`ST7735_DMA.c`, `SPI_DMA.c`) for high-performance rendering. The external ST7735/SPI files are only needed for initialization.

## RayCast3D Studio

A GUI application for creating and managing game assets. Run `RayCast3D_Studio.py` with Python 3.

### Features

- **Map Editor** — 24×24 grid editor with click-and-drag wall placement. Supports multiple maps with add/rename/delete. Perimeter walls are enforced automatically.

- **Texture Manager** — Import textures from image files (PNG, JPG, etc.). Supports 16×16, 32×32, 64×64, and 128×128 resolutions. Each texture can have a different resolution for quality/memory trade-offs.

- **Sprite Manager** — Import sprite images with automatic transparent color detection. Supports alpha channel transparency or top-left pixel as transparent key. Preview shows simulated in-game appearance.

- **Color Picker** — Define named colors with a visual color picker. Colors are exported as BGR565 constants for use with `Graphics_SetFloorColor()`, `Graphics_SetSkyColor()`, etc.

### Auto-Export

The Studio automatically exports to the `assets/` folder:

| File | Contents |
|------|----------|
| `textures.h` | Wall textures with `TextureInfo` structs |
| `map.h` | Map data arrays and `mapList[]` pointer array |
| `images.h` | Sprite images with `SpriteImage` structs |
| `colors.h` | Named color constants in BGR565 format |

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+1/2/3/4` | Switch tabs (Map/Textures/Sprites/Colors) |
| `Ctrl+T` | Add texture |
| `Ctrl+P` | Add sprite |
| `Ctrl+S` | Save and export |
| `Delete` | Remove selected item |
| `↑/↓` | Navigate list items |
| `Escape` | Deselect |

## API Reference

### Engine Core

```c
void RayCast3D_Init(void);
void RayCast3D_Render(void);
```
- `RayCast3D_Init()` — Call once at startup. Initializes clock (80MHz), fixed-point math, display, and DMA.
- `RayCast3D_Render()` — Call once per frame. Casts rays, renders sprites, draws overlays, transfers to display.

### Graphics Configuration

```c
void Graphics_SetFloorColor(uint16_t color);
void Graphics_SetSkyColor(uint16_t color);
void Graphics_SetFloorGradient(double intensity);
```
- Set floor/sky colors using BGR565 constants (from `colors.h` or ST7735 defines)
- `intensity` controls floor gradient darkness (0.0 = none, 1.0 = full gradient)

### Camera Control

```c
void Camera_SetPosition(double x, double y);
void Camera_SetDirection(double dirX, double dirY);
void Camera_Move(double forward, double strafe);
void Camera_Rotate(double degrees);
const Camera* Camera_Get(void);
```
- `SetPosition` / `SetDirection` — Initialize camera state
- `Move` — Move forward/backward and strafe left/right
- `Rotate` — Turn camera by degrees (positive = clockwise)
- `Get` — Access camera state (posX, posY, dirX, dirY, planeX, planeY)

### Map Management

```c
void Map_Load(const uint8_t map[MAP_HEIGHT][MAP_WIDTH]);
void Map_LoadFromList(const uint8_t* maps[], int index);
uint8_t Map_GetValue(double x, double y);
```
- Load maps created in RayCast3D Studio
- `Map_GetValue` returns wall texture index (0 = empty space)

### World Sprites

```c
uint8_t Sprite_Add(double x, double y, const uint16_t* image, int width, int height, int scale, uint16_t transparent);
void Sprite_Remove(int index);
void Sprite_Move(int index, double x, double y);
void Sprite_Scale(int index, int scale);
const Sprite* Sprite_Get(int index);
int Sprites_GetCount(void);
void Sprite_Clear(void);
```
- `Sprite_Add` — Add sprite at world position, returns index (or -1 if full)
- `Sprite_Remove` — Remove sprite by index
- `Sprite_Move` — Update sprite world position
- `Sprite_Scale` — Update sprite scale (8 = full screen height)
- `Sprite_Get` — Get read-only pointer to sprite data (NULL if invalid/inactive)
- `Sprites_GetCount` — Get number of active sprites
- `Sprite_Clear` — Remove all sprites

**Note:** Use the `AddSprite(x, y, name, scale)` macro from `images.h` for sprites created in the Studio.

## UI Overlay Functions

### FPS Display
```c
Graphics_DisplayFPS(int x, int y, uint16_t color);
Graphics_DisableFPS(void);
```
- Call `Graphics_DisplayFPS()` once during setup to enable FPS counter
- Automatically initializes Timer G12 for timing
- FPS is updated internally each frame (averaged over 16 frames)
- Drawn automatically inside `RayCast3D_Render()` after sprites
- Call `Graphics_DisableFPS()` to hide

### Per-Frame Text
```c
Graphics_Text(const char* text, int x, int y, uint16_t color);
```
- Call before `RayCast3D_Render()` each frame you want text displayed
- Queued internally (max 8 text entries, 32 chars each)
- Drawn after sprites, before FPS overlay
- Queue automatically cleared after `RayCast3D_Render()` completes
- Handles text spanning the screen center (split-buffer boundary)

### Per-Frame Foreground Sprites
```c
Graphics_ForegroundSprite(const uint16_t* image, int x, int y, int width, int height, int scale, uint16_t transparent);
```
- Call before `RayCast3D_Render()` each frame you want sprite displayed
- Queued internally (max 8 sprites)
- `x, y` is screen position (y is bottom of sprite)
- `scale` of 2 = 32 pixels tall for 16px source (scale/8 * SCREEN_HEIGHT)
- `transparent` color is not drawn
- Queue automatically cleared after `RayCast3D_Render()` completes

## Performance Optimizations

### Fixed-Point Math (Q16.16)

All raycasting math uses Q16.16 fixed-point arithmetic for optimal performance on the MSPM0 (which lacks an FPU). This provides:

- **16-bit integer part**: Range of -32768 to +32767
- **16-bit fractional part**: Precision of ~0.00002

Key optimizations:
- Lookup tables for `sin`/`cos` (256 entries with quadrant mirroring)
- Reciprocal lookup tables to minimize division operations
- Precomputed constants (`SCREEN_HEIGHT_SHIFTED`, texture masks)
- Cache-friendly sprite rendering (row-major traversal)

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

## Fixed-Point API

Located in `utils/fixed.h`:

| Macro/Function | Description |
|----------------|-------------|
| `INT_TO_FIXED(x)` | Convert integer to fixed-point |
| `FIXED_TO_INT(x)` | Convert fixed-point to integer (truncates) |
| `FLOAT_TO_FIXED(x)` | Convert float/double to fixed-point |
| `fixed_mul(a, b)` | Multiply two fixed-point values |
| `fixed_div(a, b)` | Divide two fixed-point values |
| `fixed_sin(angle)` | Sine (angle in fixed-point radians) |
| `fixed_cos(angle)` | Cosine (angle in fixed-point radians) |
| `fixed_sqrt(x)` | Square root using Newton-Raphson |

## License

For educational use in ECE 319K.
