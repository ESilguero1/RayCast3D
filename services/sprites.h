/**
 * @file      sprites.h
 * @brief     RayCast3D Sprite Rendering Module - Billboard sprites with depth sorting
 *
 * @author    Elijah Silguero (with contributions from Surya Balaji)
 * @date      December 2025
 *
 * Provides billboarded sprite rendering integrated with the
 * raycasting Z-buffer for proper depth occlusion.
 */

/**
 * @defgroup Sprites Sprites
 * @brief Billboarded world sprites with depth-sorted rendering.
 *
 * The Sprites module manages dynamic objects placed in the 3D world.
 * Sprites are always rendered facing the camera (billboarded) and are
 * depth-tested against the raycaster's Z-buffer so they appear correctly
 * behind or in front of walls. Up to @ref SPRITES_MAX_COUNT sprites
 * can be active at once.
 *
 * @note For sprites created in RayCast3D Studio, **always prefer the
 * @c AddSprite(x,y,name,scale) and @c AddFGSprite(name,x,y,scale)
 * macros from images.h** — they automatically fill in the image pointer,
 * dimensions, and transparent color so you only need to specify position
 * and scale. Use Sprite_Add() directly only when working with image data
 * that was not created through the Studio.
 *
 * After adding a sprite, use Sprite_Move() and Sprite_Scale() to update
 * it at runtime. Rendering is handled automatically by RayCast3D_Render().
 *
 * @{
 */

#ifndef SPRITES_H_
#define SPRITES_H_

#include <stdint.h>

/*---------------------------------------------------------------------------
 * Constants
 *---------------------------------------------------------------------------*/

/** Maximum number of sprites in the world */
#define SPRITES_MAX_COUNT 16

/*---------------------------------------------------------------------------
 * Types
 *---------------------------------------------------------------------------*/

/**
 * @brief World sprite descriptor.
 *
 * Each sprite occupies a slot in the global Sprites_Array. It holds
 * a world-space position, a pointer to its BGR565 image data, and
 * rendering parameters (dimensions, scale, transparency key). The
 * raycaster projects the sprite into screen space as a billboard
 * and depth-tests it against the Z-buffer each frame.
 *
 * The @c type field is not used by the engine — it is available for
 * your game logic (e.g., to distinguish enemies from items).
 */
typedef struct {
    double x;               /**< World X position (column, in tile coordinates) */
    double y;               /**< World Y position (row, in tile coordinates) */
    const uint16_t* image;  /**< Pointer to BGR565 image pixel data */
    uint16_t transparent;   /**< Pixel color treated as transparent (not drawn) */
    int width;              /**< Source image width in pixels */
    int height;             /**< Source image height in pixels */
    int scale;              /**< Scale factor (8 = full screen height at distance 1.0) */
    int8_t type;            /**< User-defined tag for game logic (unused by engine) */
    int8_t active;          /**< Slot state: 0 = empty, 1 = in use */
} Sprite;

/*---------------------------------------------------------------------------
 * Public Variables
 *---------------------------------------------------------------------------*/

/** Current number of active sprites */
extern int Sprites_Count;

/** Sprite array (access via Sprite_* functions preferred) */
extern Sprite Sprites_Array[SPRITES_MAX_COUNT];

/*---------------------------------------------------------------------------
 * Rendering Functions
 *---------------------------------------------------------------------------*/

/**
 * @brief Render all active sprites for a screen quarter (internal).
 *
 * Sorts sprites back-to-front by distance from the camera and renders
 * each one with depth testing against the Z-buffer. Called automatically
 * by RayCast3D_Render() — do not call directly.
 *
 * @param side  Which screen quarter to render (0-3)
 */
void Sprites_RenderAll(int side);

/**
 * @brief Render a single sprite to the current screen quarter (internal).
 *
 * Projects the sprite into screen space, clips to the current quarter,
 * and draws visible pixels with Z-buffer occlusion.
 *
 * @param sprite       Sprite data (passed by value)
 * @param side         Which screen quarter (0-3)
 * @param spriteIndex  Index into Sprites_Array for distance sorting
 */
void Sprites_RenderOne(Sprite sprite, int side, int spriteIndex);

/*---------------------------------------------------------------------------
 * Management Functions
 *---------------------------------------------------------------------------*/

/**
 * @brief Add a new sprite to the world.
 *
 * Finds the first empty slot in the sprite array and initializes it.
 *
 * @note For Studio-created sprites, use the @c AddSprite macro from
 * images.h instead — it calls this function automatically with the
 * correct image, dimensions, and transparent color.
 *
 * @param x            World X position (column)
 * @param y            World Y position (row)
 * @param image        Pointer to BGR565 image data
 * @param width        Image width in pixels
 * @param height       Image height in pixels
 * @param scale        Size factor (8 = full screen height at distance 1.0)
 * @param transparent  Pixel color treated as transparent (not drawn)
 * @return Sprite index (use for Move/Remove/Scale), or -1 if all slots full
 */
uint8_t Sprite_Add(double x, double y, const uint16_t* image,
                   int width, int height, int scale, uint16_t transparent);

/**
 * @brief Remove all sprites from the world.
 *
 * Marks every slot as inactive and resets the sprite count to zero.
 */
void Sprite_Clear(void);

/**
 * @brief Remove a specific sprite by index.
 *
 * Marks the slot as inactive so it can be reused by a future
 * Sprite_Add() call. Does nothing if the index is out of range.
 *
 * @param index  Sprite index returned by Sprite_Add
 */
void Sprite_Remove(int index);

/**
 * @brief Move a sprite to a new world position.
 * @param index  Sprite index returned by Sprite_Add
 * @param x      New world X coordinate (column)
 * @param y      New world Y coordinate (row)
 */
void Sprite_Move(int index, double x, double y);

/**
 * @brief Change a sprite's scale factor.
 *
 * A scale of 8 makes the sprite fill the full screen height when
 * at distance 1.0 from the camera. Smaller values shrink it.
 *
 * @param index  Sprite index returned by Sprite_Add
 * @param scale  Size factor (8 = full screen height at distance 1.0)
 */
void Sprite_Scale(int index, int scale);

/**
 * @brief Get a read-only pointer to a sprite's data.
 * @param index  Sprite index
 * @return Pointer to the Sprite struct, or NULL if the index is
 *         out of range or the slot is inactive
 */
const Sprite* Sprite_Get(int index);

/**
 * @brief Get the number of active sprites.
 * @return Count of sprites currently in the world
 */
int Sprites_GetCount(void);

#endif /* SPRITES_H_ */
