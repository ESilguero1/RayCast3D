/* graphics.h
 * RayCast3D Graphics Library
 * Main header - includes all sub-modules
 */

#ifndef GRAPHICS_H_
#define GRAPHICS_H_

#include <stdint.h>
#include "../drivers/ST7735.h"

// Include sub-modules
#include "camera.h"
#include "map.h"

// Screen dimensions
#define SCREEN_WIDTH 160
#define SCREEN_HEIGHT 128
#define BUFFER_WIDTH (SCREEN_WIDTH / 2)
#define BUFFER_HEIGHT SCREEN_HEIGHT

// Texture info structure (allows per-texture resolution)
typedef struct {
    const uint16_t* data;
    int resolution;  // Texture dimension (e.g., 16, 32, 64, 128)
} TextureInfo;

// Depth buffer for sprite sorting
extern double ZBuffer[SCREEN_WIDTH];

// Core functions
void Graphics_Init(void);
void Graphics_SetFloorColor(uint16_t color);
void Graphics_SetSkyColor(uint16_t color);
void Graphics_SetFloorGradient(double intensity);
void RenderScene(void);
void CastRays(int side);

// FPS display - enables/disables FPS overlay on screen
void Graphics_DisplayFPS(int x, int y, uint16_t color);
void Graphics_DisableFPS(void);

// Per-frame text rendering (call before RenderScene, cleared after render)
void Graphics_Text(const char* text, int x, int y, uint16_t color);

// Per-frame foreground sprite rendering (call before RenderScene, cleared after render)
void Graphics_ForegroundSprite(const uint16_t* image, int x, int y, int width, int height, int scale, uint16_t transparent);

#endif /* GRAPHICS_H_ */
