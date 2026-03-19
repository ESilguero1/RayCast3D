/**
 * @file      graphics.h
 * @brief     RayCast3D Graphics Library - Core raycasting and rendering
 *
 * @author    Elijah Silguero (with contributions from Surya Balaji)
 * @date      December 2025
 * @hardware  MSPM0G3507 with ST7735 LCD
 *
 * Provides the main rendering interface including raycasting,
 * sprite rendering, FPS display, and text overlay functions.
 */

#ifndef GRAPHICS_H_
#define GRAPHICS_H_

#include <stdint.h>
#include "../utils/fixed.h"

// Include sub-modules
#include "camera.h"
#include "map.h"

// Screen dimensions
#define SCREEN_WIDTH 160
#define SCREEN_HEIGHT 128

/** Texture info structure (allows per-texture resolution) */
typedef struct {
    const uint16_t* data;  /**< Pointer to texture pixel data */
    int resolution;        /**< Texture dimension (e.g., 16, 32, 64, 128) */
    int mask;              /**< Precomputed: resolution - 1 (for power-of-2 textures) */
} TextureInfo;

// Precomputed constants for hot paths
#define SCREEN_HEIGHT_SHIFTED ((int64_t)SCREEN_HEIGHT << FIXED_SHIFT)
#define HALF_SCREEN_HEIGHT (SCREEN_HEIGHT / 2)
#define HALF_SCREEN_WIDTH (SCREEN_WIDTH / 2)

// Depth buffer for sprite sorting (fixed-point Q16.16)
extern fixed_t ZBuffer[SCREEN_WIDTH];

/** @brief Initialize the graphics subsystem */
void Graphics_Init(void);

/**
 * @brief Set floor color
 * @param color  BGR565 color value
 */
void Graphics_SetFloorColor(uint16_t color);

/**
 * @brief Set sky color
 * @param color  BGR565 color value
 */
void Graphics_SetSkyColor(uint16_t color);

/**
 * @brief Set floor gradient darkness
 * @param intensity  Gradient intensity (0.0 = none, 1.0 = full gradient)
 */
void Graphics_SetFloorGradient(double intensity);

/**
 * @brief Cast rays for one screen quarter
 * @param side  Which quarter to render (0-3)
 */
void CastRays(int side);

// Internal functions (called by RayCast3D_Render)
void Graphics_RenderOverlays(int side);
void Graphics_ClearOverlayQueues(void);

/**
 * @brief Enable FPS overlay on screen
 *
 * Automatically initializes Timer G12 for timing.
 * FPS is updated internally each frame (averaged over 16 frames).
 * Call once during setup.
 *
 * @param x      Screen X position
 * @param y      Screen Y position
 * @param color  BGR565 text color
 */
void Graphics_DisplayFPS(int x, int y, uint16_t color);

/** @brief Disable FPS overlay */
void Graphics_DisableFPS(void);

/**
 * @brief Queue text for rendering on the current frame
 *
 * Call before RayCast3D_Render() each frame you want text displayed.
 * Queue is automatically cleared after RayCast3D_Render() completes.
 * Max 8 text entries, 32 chars each.
 *
 * @param text   String to display
 * @param x      Screen X position
 * @param y      Screen Y position
 * @param color  BGR565 text color
 */
void Graphics_Text(const char* text, int x, int y, uint16_t color);

/**
 * @brief Queue a foreground sprite for rendering on the current frame
 *
 * Call before RayCast3D_Render() each frame you want sprite displayed.
 * Queue is automatically cleared after RayCast3D_Render() completes.
 * Max 8 sprites.
 *
 * @param image        Pointer to 16-bit color image data
 * @param x            Screen X position
 * @param y            Screen Y position (bottom of sprite)
 * @param width        Source image width in pixels
 * @param height       Source image height in pixels
 * @param scale        Scale factor (scale/8 * SCREEN_HEIGHT)
 * @param transparent  Color key that will not be drawn
 */
void Graphics_ForegroundSprite(const uint16_t* image, int x, int y, int width, int height, int scale, uint16_t transparent);

#endif /* GRAPHICS_H_ */
