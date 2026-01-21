/* sprites.c
 * RayCast3D Sprite Rendering Module
 * Billboard sprite rendering with depth sorting
 *
 * Author: Elijah Silguero (with contributions from Surya Balaji)
 * Created: December 2025
 * Modified: January 2026
 * Hardware: MSPM0G3507 with ST7735 LCD
 *
 * Uses the inverse camera transform for projection and
 * the Z-buffer for depth-correct sprite occlusion.
 */

#include "sprites.h"
#include "graphics.h"
#include "../hal/buffer.h"
#include "../utils/fixed.h"
#include <stdlib.h>

/*---------------------------------------------------------------------------
 * External References
 *---------------------------------------------------------------------------*/

extern fixed_t ZBuffer[SCREEN_WIDTH];

/*---------------------------------------------------------------------------
 * Public Variables
 *---------------------------------------------------------------------------*/

int Sprites_Count = 0;
Sprite Sprites_Array[SPRITES_MAX_COUNT];

// Helper structure for sorting sprites
typedef struct {
    int index;
    fixed_t distance;  // Fixed-point distance squared
} SpriteDistancePair;

// Comparison function for sorting sprites by distance (far to near)
static int compareSprites(const void *a, const void *b) {
    const SpriteDistancePair *spriteA = (SpriteDistancePair *)a;
    const SpriteDistancePair *spriteB = (SpriteDistancePair *)b;
    if (spriteA->distance < spriteB->distance) return 1;
    if (spriteA->distance > spriteB->distance) return -1;
    return 0;
}

// Maximum columns a sprite can span (usually much less than screen width)
#define MAX_VISIBLE_COLUMNS 80

// Structure to track visible columns for cache-friendly sprite rendering
typedef struct {
    int8_t bufferX;  // Buffer X position (-1 if not visible)
    int8_t texX;     // Texture X coordinate
} VisibleColumn;

void Sprites_RenderOne(Sprite sprite, int side, int spriteIndex) {
    const Camera* cam = Camera_Get();

    // Convert sprite position to fixed-point
    fixed_t spritePosX = FLOAT_TO_FIXED(sprite.x);
    fixed_t spritePosY = FLOAT_TO_FIXED(sprite.y);

    // Sprite position relative to the camera (all fixed-point)
    fixed_t spriteX = spritePosX - cam->posX;
    fixed_t spriteY = spritePosY - cam->posY;

    // Inverse camera transformation
    fixed_t det = fixed_mul(cam->planeX, cam->dirY) - fixed_mul(cam->dirX, cam->planeY);
    if (det == 0) return;
    fixed_t invDet = fixed_recip_large(det);

    fixed_t transformX = fixed_mul(invDet, fixed_mul(cam->dirY, spriteX) - fixed_mul(cam->dirX, spriteY));
    fixed_t transformY = fixed_mul(invDet, -fixed_mul(cam->planeY, spriteX) + fixed_mul(cam->planeX, spriteY));

    // Ignore if behind camera
    if (transformY <= 6554) return;

    // Project sprite to screen
    fixed_t ratio = fixed_div(transformX, transformY);
    int spriteScreenX = (HALF_SCREEN_WIDTH) * (FIXED_ONE + ratio) >> FIXED_SHIFT;

    // Calculate sprite dimensions (use precomputed constant)
    int originalSpriteHeight = (int)(SCREEN_HEIGHT_SHIFTED / transformY);
    if (originalSpriteHeight < 0) originalSpriteHeight = -originalSpriteHeight;

    int originalSpriteWidth = (int64_t)originalSpriteHeight * sprite.width / sprite.height;
    if (originalSpriteWidth < 0) originalSpriteWidth = -originalSpriteWidth;

    // Scale sprite
    int spriteHeight = (originalSpriteHeight * sprite.scale) >> 3;
    int spriteWidth = (originalSpriteWidth * sprite.scale) >> 3;

    if (spriteWidth <= 0 || spriteHeight <= 0) return;

    int pushdown = (originalSpriteHeight - spriteHeight) >> 1;

    // Calculate drawing boundaries
    int drawStartY = HALF_SCREEN_HEIGHT - (spriteHeight >> 1) - pushdown;
    int drawEndY = HALF_SCREEN_HEIGHT + (spriteHeight >> 1) - pushdown;
    int drawStartX = spriteScreenX - (spriteWidth >> 1);
    int drawEndX = spriteScreenX + ((spriteWidth + 1) >> 1);

    // Clamp Y boundaries
    if (drawStartY < 0) drawStartY = 0;
    if (drawEndY > SCREEN_HEIGHT) drawEndY = SCREEN_HEIGHT;

    // === PASS 1: Build visibility list for columns ===
    // This allows us to do row-major texture access in pass 2
    VisibleColumn visibleCols[MAX_VISIBLE_COLUMNS];
    int numVisible = 0;

    // Quarter-screen: each side covers BUFFER_WIDTH (40) columns
    int sideStartX = side * BUFFER_WIDTH;
    int sideEndX = sideStartX + BUFFER_WIDTH;

    for (int stripe = drawStartX; stripe < drawEndX && numVisible < MAX_VISIBLE_COLUMNS; stripe++) {
        // Check if this screen column falls within current side's range
        if (stripe >= sideStartX && stripe < sideEndX) {
            int bufferX = stripe - sideStartX;

            // Check ZBuffer visibility
            if (stripe >= 0 && stripe < SCREEN_WIDTH && transformY < ZBuffer[stripe]) {
                int texX = (stripe - drawStartX) * sprite.width / spriteWidth;
                if (texX >= 0 && texX < sprite.width) {
                    visibleCols[numVisible].bufferX = bufferX;
                    visibleCols[numVisible].texX = texX;
                    numVisible++;
                }
            }
        }
    }

    if (numVisible == 0) return;  // Nothing visible

    // === PASS 2: Row-major rendering for cache efficiency ===
    // Outer loop: Y (rows) - texture rows are contiguous in memory
    // Inner loop: visible X columns
    const uint16_t* imgData = sprite.image;
    uint16_t transparent = sprite.transparent;
    int imgWidth = sprite.width;

    for (int y = drawStartY; y < drawEndY; y++) {
        // Calculate texY once per row
        int texY = (drawEndY - y) * sprite.height / spriteHeight;
        if (texY < 0 || texY >= sprite.height) continue;

        // Row base pointer - now we iterate X which is contiguous in memory
        const uint16_t* rowPtr = imgData + texY * imgWidth;

        // Iterate through visible columns (cache-friendly X access)
        for (int i = 0; i < numVisible; i++) {
            uint16_t pixelColor = rowPtr[visibleCols[i].texX];
            if (pixelColor != transparent) {
                Buffer_SetPixel(visibleCols[i].bufferX, y, pixelColor);
            }
        }
    }
}

void Sprites_RenderAll(int side) {
    const Camera* cam = Camera_Get();
    SpriteDistancePair spriteOrder[SPRITES_MAX_COUNT];
    int activeCount = 0;

    // Build list of active sprites with their distances (fixed-point)
    for (int i = 0; i < SPRITES_MAX_COUNT; i++) {
        if (Sprites_Array[i].active) {
            spriteOrder[activeCount].index = i;
            // Calculate distance squared in fixed-point
            fixed_t dx = cam->posX - FLOAT_TO_FIXED(Sprites_Array[i].x);
            fixed_t dy = cam->posY - FLOAT_TO_FIXED(Sprites_Array[i].y);
            // Distance squared (no need for sqrt, just for sorting)
            spriteOrder[activeCount].distance = fixed_mul(dx, dx) + fixed_mul(dy, dy);
            activeCount++;
        }
    }

    qsort(spriteOrder, activeCount, sizeof(SpriteDistancePair), compareSprites);

    for (int i = 0; i < activeCount; i++) {
        if (Sprites_Array[spriteOrder[i].index].width != 0) {
            Sprites_RenderOne(Sprites_Array[spriteOrder[i].index], side, spriteOrder[i].index);
        }
    }
}

uint8_t Sprite_Add(double x, double y, const uint16_t* image, int width, int height, int scale, uint16_t transparent) {
    // Find first inactive slot
    for (int i = 0; i < SPRITES_MAX_COUNT; i++) {
        if (!Sprites_Array[i].active) {
            Sprites_Array[i].x = x;
            Sprites_Array[i].y = y;
            Sprites_Array[i].image = image;
            Sprites_Array[i].width = width;
            Sprites_Array[i].height = height;
            Sprites_Array[i].scale = scale;
            Sprites_Array[i].transparent = transparent;
            Sprites_Array[i].type = 0;
            Sprites_Array[i].active = 1;
            Sprites_Count++;
            return i;  // Index remains stable even after other sprites are removed
        }
    }
    return -1;  // No free slots
}

void Sprite_Clear(void) {
    for (int i = 0; i < SPRITES_MAX_COUNT; i++) {
        Sprites_Array[i].active = 0;
    }
    Sprites_Count = 0;
}

void Sprite_Remove(int index) {
    if (index < 0 || index >= SPRITES_MAX_COUNT) {
        return;
    }
    if (!Sprites_Array[index].active) {
        return;  /* Already inactive */
    }

    Sprites_Array[index].active = 0;
    Sprites_Count--;
}

void Sprite_Move(int index, double x, double y) {
    if (index < 0 || index >= SPRITES_MAX_COUNT) {
        return;
    }
    if (!Sprites_Array[index].active) {
        return;  /* Sprite not active */
    }

    Sprites_Array[index].x = x;
    Sprites_Array[index].y = y;
}

void Sprite_Scale(int index, int scale) {
    if (index < 0 || index >= SPRITES_MAX_COUNT) {
        return;
    }
    if (!Sprites_Array[index].active) {
        return;  /* Sprite not active */
    }

    Sprites_Array[index].scale = scale;
}

const Sprite* Sprite_Get(int index) {
    if (index < 0 || index >= SPRITES_MAX_COUNT) {
        return 0;
    }
    if (!Sprites_Array[index].active) {
        return 0;
    }
    return &Sprites_Array[index];
}

int Sprites_GetCount(void) {
    return Sprites_Count;
}
