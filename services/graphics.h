/**
 * @file      graphics.h
 * @brief     RayCast3D Graphics Library - Core raycasting and rendering
 *
 * @author    Elijah Silguero (with contributions from Surya Balaji)
 * @date      December 2025
 *
 * Provides the main rendering interface including raycasting,
 * sprite rendering, FPS display, and text overlay functions.
 */

/**
 * @defgroup Graphics Graphics
 * @brief Scene appearance and UI overlay rendering.
 *
 * The Graphics module controls the visual appearance of the rendered
 * scene. Use it to set floor and sky colors, enable a distance-based
 * floor gradient, display an FPS counter, and queue per-frame text
 * and foreground sprites that are drawn on top of the 3D scene.
 *
 * Overlay functions (Graphics_Text, Graphics_ForegroundSprite) are
 * queued — call them each frame before RayCast3D_Render(). The queues
 * are automatically cleared after each frame completes.
 *
 * @{
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

/* Texture info structure (allows per-texture resolution) */
typedef struct {
    const uint16_t* data;  /*< Pointer to texture pixel data */
    int resolution;        /*< Texture dimension (e.g., 16, 32, 64, 128) */
    int mask;              /*< Precomputed: resolution - 1 (for power-of-2 textures) */
} TextureInfo;

// Precomputed constants for hot paths
#define SCREEN_HEIGHT_SHIFTED ((int64_t)SCREEN_HEIGHT << FIXED_SHIFT)
#define HALF_SCREEN_HEIGHT (SCREEN_HEIGHT / 2)
#define HALF_SCREEN_WIDTH (SCREEN_WIDTH / 2)

// Depth buffer for sprite sorting (fixed-point Q16.16)
extern fixed_t ZBuffer[SCREEN_WIDTH];

/**
 * @brief Initialize the graphics subsystem.
 *
 * Configures the ST7735 display, SPI, DMA, and internal render buffers.
 * Called automatically by RayCast3D_Init() — do not call directly.
 */
void Graphics_Init(void);

/**
 * @brief Set the solid color drawn below the horizon.
 *
 * Takes effect on the next call to RayCast3D_Render(). Use color
 * constants from colors.h (exported by RayCast3D Studio) or ST7735
 * defines such as ST7735_DARKGREY.
 *
 * @note Has no visible effect while a floor texture is active
 *       (set via Studio or Graphics_SetFloorTexture()). The color is
 *       still stored and will be used if the floor texture is later
 *       disabled.
 *
 * @param color  BGR565 color value
 */
void Graphics_SetFloorColor(uint16_t color);

/**
 * @brief Set the solid color drawn above the horizon.
 *
 * Takes effect on the next call to RayCast3D_Render().
 *
 * @note Has no visible effect while a ceiling texture is active
 *       (set via Studio or Graphics_SetCeilingTexture()). The color is
 *       still stored and will be used if the ceiling texture is later
 *       disabled.
 *
 * @param color  BGR565 color value
 */
void Graphics_SetSkyColor(uint16_t color);

/**
 * @brief Enable a distance-based darkening gradient on the floor.
 *
 * Simulates depth by darkening floor pixels farther from the camera.
 * An intensity of 0.0 disables the gradient entirely; 1.0 applies
 * maximum darkening at the horizon line.
 *
 * @note Has no visible effect while a floor texture is active.
 *
 * @param intensity  Gradient strength (0.0 = off, 1.0 = full)
 */
void Graphics_SetFloorGradient(double intensity);

/**
 * @brief Select a texture for floor rendering (enables textured floorcasting).
 *
 * When set to a valid index, the engine replaces the solid-color gradient
 * floor with perspective-correct textured floorcasting. Set to -1 to
 * revert to the gradient floor (Graphics_SetFloorColor / Graphics_SetFloorGradient).
 *
 * Normally configured per-map in RayCast3D Studio and applied automatically
 * by Map_Load(). Call directly only to override the Studio setting at runtime.
 *
 * @note Textured floorcasting is more CPU-intensive than the solid-color
 *       gradient. Disable (set to None in Studio) to improve FPS on scenes
 *       where floor detail is not needed.
 *
 * @param texIndex  Index into textures[] (0-based), or -1 to disable
 */
void Graphics_SetFloorTexture(int texIndex);

/**
 * @brief Select a texture for ceiling rendering (enables textured ceilingcasting).
 *
 * When set to a valid index, the engine replaces the solid sky color
 * with perspective-correct textured ceiling. Set to -1 to revert to
 * the solid color (Graphics_SetSkyColor).
 *
 * Normally configured per-map in RayCast3D Studio and applied automatically
 * by Map_Load(). Call directly only to override the Studio setting at runtime.
 *
 * @note Textured ceilingcasting is more CPU-intensive than the solid sky
 *       color. Disable (set to None in Studio) to improve FPS on scenes
 *       where ceiling detail is not needed.
 *
 * @param texIndex  Index into textures[] (0-based), or -1 to disable
 */
void Graphics_SetCeilingTexture(int texIndex);

/**
 * @brief Cast rays for one screen quarter (internal).
 * @param side  Which quarter to render (0-3)
 */
void CastRays(int side);

/**
 * @brief Render textured floor and ceiling for one screen quarter (internal, row-based).
 * @param side  Which quarter to render (0-3)
 */
void CastFloors(int side);

/** @internal Render queued overlays for one quarter. */
void Graphics_RenderOverlays(int side);
/** @internal Clear all overlay queues after a full frame. */
void Graphics_ClearOverlayQueues(void);

/**
 * @brief Enable an on-screen FPS counter.
 *
 * Call once during setup to display a live frames-per-second readout.
 * Automatically initializes Timer G12 for frame timing. The displayed
 * value is a rolling average over 16 frames and is drawn automatically
 * by RayCast3D_Render() after sprites and text overlays.
 *
 * @param x      Screen X position of the counter
 * @param y      Screen Y position of the counter
 * @param color  BGR565 text color
 */
void Graphics_DisplayFPS(int x, int y, uint16_t color);

/**
 * @brief Hide the FPS counter.
 *
 * Disables the overlay enabled by Graphics_DisplayFPS(). Timer G12
 * continues to run but the counter is no longer drawn.
 */
void Graphics_DisableFPS(void);

/**
 * @brief Queue a text string for display on the current frame.
 *
 * Must be called before RayCast3D_Render() every frame you want the
 * text to appear — the queue is automatically cleared after each frame.
 * Supports up to 8 entries per frame, each up to 32 characters.
 * Text that spans the screen center (the split-buffer boundary at
 * x = 80) is handled automatically.
 *
 * @param text   Null-terminated string to display
 * @param x      Screen X position (left edge of first character)
 * @param y      Screen Y position (top edge)
 * @param color  BGR565 text color
 */
void Graphics_Text(const char* text, int x, int y, uint16_t color);

/**
 * @brief Queue a 2D foreground sprite for display on the current frame.
 *
 * Foreground sprites are drawn on top of the 3D scene (walls, world
 * sprites, text) and are not affected by the depth buffer. Must be
 * called before RayCast3D_Render() every frame you want the sprite to
 * appear — the queue is automatically cleared after each frame.
 * Supports up to 8 entries per frame.
 *
 * @note For Studio-created sprites, use the @c AddFGSprite macro from
 * images.h instead — it fills in the image, dimensions, and transparent
 * color automatically.
 *
 * @param image        Pointer to 16-bit BGR565 image data
 * @param x            Screen X position (left edge)
 * @param y            Screen Y position (bottom edge of sprite)
 * @param width        Source image width in pixels
 * @param height       Source image height in pixels
 * @param scale        Scale factor (rendered height = scale/8 * SCREEN_HEIGHT)
 * @param transparent  Pixel color treated as transparent (not drawn)
 */
void Graphics_ForegroundSprite(const uint16_t* image, int x, int y, int width, int height, int scale, uint16_t transparent);

#endif /* GRAPHICS_H_ */
