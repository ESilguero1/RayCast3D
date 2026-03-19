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
 * @brief Dynamic objects in the world.
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

/** Sprite structure for world sprites */
typedef struct {
    double x;               /**< World X position */
    double y;               /**< World Y position */
    const uint16_t* image;  /**< Pointer to image data */
    uint16_t transparent;   /**< Transparent color key */
    int width;              /**< Image width in pixels */
    int height;             /**< Image height in pixels */
    int scale;              /**< Scale factor (8 = full height) */
    int8_t type;            /**< User-defined sprite type */
    int8_t active;          /**< 0 = slot empty, 1 = in use */
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
 * @brief Render all active sprites for a screen quarter
 * @param side  Which quarter (0-3)
 */
void Sprites_RenderAll(int side);

/**
 * @brief Render a single sprite
 * @param sprite       Sprite data
 * @param side         Which quarter (0-3)
 * @param spriteIndex  Index for Z-buffer lookup
 */
void Sprites_RenderOne(Sprite sprite, int side, int spriteIndex);

/*---------------------------------------------------------------------------
 * Management Functions
 *---------------------------------------------------------------------------*/

/**
 * @brief Add a new sprite to the world
 * @param x            World X position
 * @param y            World Y position
 * @param image        Pointer to image data
 * @param width        Image width in pixels
 * @param height       Image height in pixels
 * @param scale        Size factor (8 = full screen height)
 * @param transparent  Color key for transparency
 * @return Sprite index, or -1 if no slots available
 */
uint8_t Sprite_Add(double x, double y, const uint16_t* image,
                   int width, int height, int scale, uint16_t transparent);

/** @brief Remove all sprites from the world */
void Sprite_Clear(void);

/**
 * @brief Remove a specific sprite
 * @param index  Sprite index returned by Sprite_Add
 */
void Sprite_Remove(int index);

/**
 * @brief Move a sprite to a new world position
 * @param index  Sprite index returned by Sprite_Add
 * @param x      New world X coordinate
 * @param y      New world Y coordinate
 */
void Sprite_Move(int index, double x, double y);

/**
 * @brief Set sprite scale factor
 * @param index  Sprite index returned by Sprite_Add
 * @param scale  Size factor (8 = full screen height)
 */
void Sprite_Scale(int index, int scale);

/**
 * @brief Get a read-only pointer to a sprite
 * @param index  Sprite index
 * @return Pointer to sprite, or NULL if invalid/inactive
 */
const Sprite* Sprite_Get(int index);

/**
 * @brief Get count of active sprites
 * @return Number of active sprites
 */
int Sprites_GetCount(void);

#endif /* SPRITES_H_ */
