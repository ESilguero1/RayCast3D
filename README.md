# RayCast3D

A pseudo-3D graphics library for the ST7735R display using raycasting techniques.

## Overview

RayCast3D is designed for ECE 319K students working with the MSPM0 microcontroller. It provides a simple interface for rendering pseudo-3D environments on the ST7735R LCD display using raycasting algorithms.

## Hardware Requirements

- MSPM0 MCU
- ST7735R LCD Display

## Dependencies

This library requires the following external Valvanoware files:

- `inc/Clock.h` / `Clock.c` - Clock configuration and delay functions
- `file.h` / `file.c` - File system support

These files are provided in the ECE 319K Valvanoware distribution and should be placed in an `inc/` directory at the same level as the `RayCast3D/` folder.

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

## UI Overlay Functions

### FPS Display
```c
Graphics_DisplayFPS(int x, int y, uint16_t color);
Graphics_DisableFPS(void);
```
- Call `Graphics_DisplayFPS()` once during setup to enable FPS counter
- Automatically initializes Timer G12 for timing
- FPS is updated internally each frame (averaged over 16 frames)
- Drawn automatically inside `RenderScene()` after sprites
- Call `Graphics_DisableFPS()` to hide

### Per-Frame Text
```c
Graphics_Text(const char* text, int x, int y, uint16_t color);
```
- Call before `RenderScene()` each frame you want text displayed
- Queued internally (max 8 text entries, 32 chars each)
- Drawn after sprites, before FPS overlay
- Queue automatically cleared after `RenderScene()` completes
- Handles text spanning the screen center (split-buffer boundary)

### Per-Frame Foreground Sprites
```c
Graphics_ForegroundSprite(const uint16_t* image, int x, int y, int width, int height, int scale, uint16_t transparent);
```
- Call before `RenderScene()` each frame you want sprite displayed
- Queued internally (max 8 sprites)
- `x, y` is screen position (y is bottom of sprite)
- `scale` of 2 = 32 pixels tall for 16px source (scale/8 * SCREEN_HEIGHT)
- `transparent` color is not drawn
- Queue automatically cleared after `RenderScene()` completes

### World Sprites
```c
int Sprite_Add(double x, double y, const uint16_t* image, int width, int height, int scale, uint16_t transparent);
void Sprite_Remove(int index);
void Sprite_Clear(void);
```
- Persistent sprites in 3D world space (not cleared each frame)
- `x, y` is world/map position
- Rendered with depth sorting (farther sprites drawn first)
- Occluded by walls based on Z-buffer

## License

For educational use in ECE 319K.
