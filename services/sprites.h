/* sprites.h
 * RayCast3D Sprite Rendering Module
 * Billboard sprite rendering with depth sorting
 *
 * Author: Elijah Silguero (with contributions from Surya Balaji)
 * Created: December 2025
 * Modified: January 2026
 * Hardware: MSPM0G3507 with ST7735 LCD
 *
 * Provides billboarded sprite rendering integrated with the
 * raycasting Z-buffer for proper depth occlusion.
 */

#ifndef SPRITES_H_
#define SPRITES_H_

#include <stdint.h>

/*---------------------------------------------------------------------------
 * Constants
 *---------------------------------------------------------------------------*/

/* Maximum number of sprites in the world */
#define SPRITES_MAX_COUNT 16

/*---------------------------------------------------------------------------
 * Types
 *---------------------------------------------------------------------------*/

/* Sprite structure for world sprites */
typedef struct {
    double x;               /* World X position */
    double y;               /* World Y position */
    const uint16_t* image;  /* Pointer to image data */
    uint16_t transparent;   /* Transparent color key */
    int width;              /* Image width in pixels */
    int height;             /* Image height in pixels */
    int scale;              /* Scale factor (8 = full height) */
    int8_t type;            /* User-defined sprite type */
    int8_t active;          /* 0 = slot empty, 1 = in use */
} Sprite;

/*---------------------------------------------------------------------------
 * Public Variables
 *---------------------------------------------------------------------------*/

/* Current number of active sprites */
extern int Sprites_Count;

/* Sprite array (access via Sprite_* functions preferred) */
extern Sprite Sprites_Array[SPRITES_MAX_COUNT];

/*---------------------------------------------------------------------------
 * Rendering Functions
 *---------------------------------------------------------------------------*/

/* Render all active sprites for a screen quarter
 * Inputs: side - which quarter (0-3) */
void Sprites_RenderAll(int side);

/* Render a single sprite
 * Inputs: sprite - sprite data
 *         side - which quarter (0-3)
 *         spriteIndex - index for Z-buffer lookup */
void Sprites_RenderOne(Sprite sprite, int side, int spriteIndex);

/*---------------------------------------------------------------------------
 * Management Functions
 *---------------------------------------------------------------------------*/

/* Add a new sprite to the world
 * Inputs: x, y - world position
 *         image - pointer to image data
 *         width, height - image dimensions
 *         scale - size factor (8 = full screen height)
 *         transparent - color key for transparency
 * Returns: sprite index, or -1 if no slots available */
uint8_t Sprite_Add(double x, double y, const uint16_t* image,
                   int width, int height, int scale, uint16_t transparent);

/* Remove all sprites from the world */
void Sprite_Clear(void);

/* Remove a specific sprite
 * Inputs: index - sprite index returned by Sprite_Add */
void Sprite_Remove(int index);

/* Move a sprite to a new world position
 * Inputs: index - sprite index returned by Sprite_Add
 *         x, y - new world coordinates */
void Sprite_Move(int index, double x, double y);

/* Set sprite scale factor
 * Inputs: index - sprite index returned by Sprite_Add
 *         scale - size factor (8 = full screen height) */
void Sprite_Scale(int index, int scale);

/* Get a read-only pointer to a sprite
 * Inputs: index - sprite index
 * Returns: pointer to sprite, or NULL if invalid/inactive */
const Sprite* Sprite_Get(int index);

/* Get count of active sprites
 * Returns: number of active sprites */
int Sprites_GetCount(void);

#endif /* SPRITES_H_ */