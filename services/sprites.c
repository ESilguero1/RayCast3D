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

void Sprites_RenderOne(Sprite sprite, int side, int spriteIndex) {
    const Camera* cam = Camera_Get();

    // Convert sprite position to fixed-point
    fixed_t spritePosX = FLOAT_TO_FIXED(sprite.x);
    fixed_t spritePosY = FLOAT_TO_FIXED(sprite.y);

    // Sprite position relative to the camera (all fixed-point)
    fixed_t spriteX = spritePosX - cam->posX;
    fixed_t spriteY = spritePosY - cam->posY;

    // Inverse camera transformation
    fixed_t det = Fixed_Mul(cam->planeX, cam->dirY) - Fixed_Mul(cam->dirX, cam->planeY);
    if (det == 0) return;
    fixed_t invDet = Fixed_RecipLarge(det);

    fixed_t transformX = Fixed_Mul(invDet, Fixed_Mul(cam->dirY, spriteX) - Fixed_Mul(cam->dirX, spriteY));
    fixed_t transformY = Fixed_Mul(invDet, -Fixed_Mul(cam->planeY, spriteX) + Fixed_Mul(cam->planeX, spriteY));

    // Ignore if behind camera
    if (transformY <= 6554) return;

    // Project sprite to screen
    fixed_t ratio = Fixed_Div(transformX, transformY);
    int spriteScreenX = (HALF_SCREEN_WIDTH) * (FIXED_ONE + ratio) >> FIXED_SHIFT;

    // Calculate sprite dimensions
    int originalSpriteHeight = (int)(SCREEN_HEIGHT_SHIFTED / transformY);
    if (originalSpriteHeight < 0) originalSpriteHeight = -originalSpriteHeight;

    int originalSpriteWidth = (int64_t)originalSpriteHeight * sprite.width / sprite.height;
    if (originalSpriteWidth < 0) originalSpriteWidth = -originalSpriteWidth;

    // Scale sprite
    int spriteHeight = (originalSpriteHeight * sprite.scale) >> 3;
    int spriteWidth = (originalSpriteWidth * sprite.scale) >> 3;

    if (spriteWidth <= 0 || spriteHeight <= 0) return;

    int pushdown = (originalSpriteHeight - spriteHeight) >> 1;

    // Project elevation into screen space (world units → screen pixels at this depth)
    int vMoveScreen = FIXED_TO_INT(sprite.elevation * originalSpriteHeight);

    // Camera elevation shift: higher camera → sprites shift toward floor (lower y)
    // Same perspective-correct formula as wall columns
    int camZShift = (int)(((int64_t)(cam->posZ - FIXED_HALF) * originalSpriteHeight) >> FIXED_SHIFT);

    // Calculate drawing boundaries (elevation moves sprite up in y-up coords)
    int drawStartY = HALF_SCREEN_HEIGHT - (spriteHeight >> 1) - pushdown + vMoveScreen - camZShift;
    int drawEndY = HALF_SCREEN_HEIGHT + (spriteHeight >> 1) - pushdown + vMoveScreen - camZShift;
    int drawStartX = spriteScreenX - (spriteWidth >> 1);
    int drawEndX = spriteScreenX + ((spriteWidth + 1) >> 1);

    // Save unclamped drawEndY for correct texture mapping when clipped
    int texDrawEndY = drawEndY;

    // Clamp Y boundaries for rendering
    if (drawStartY < 0) drawStartY = 0;
    if (drawEndY > SCREEN_HEIGHT) drawEndY = SCREEN_HEIGHT;

    // Quarter-screen: each side covers BUFFER_WIDTH (40) columns
    int sideStartX = side * BUFFER_WIDTH;
    int sideEndX = sideStartX + BUFFER_WIDTH;

    // Clamp X to current quarter
    if (drawStartX < sideStartX) drawStartX = sideStartX;
    if (drawEndX > sideEndX) drawEndX = sideEndX;

    const uint16_t* imgData = sprite.image;
    uint16_t transparent = sprite.transparent;

    // Render column by column
    for (int stripe = drawStartX; stripe < drawEndX; stripe++) {
        // Check ZBuffer visibility
        if (stripe < 0 || stripe >= SCREEN_WIDTH || transformY >= ZBuffer[stripe])
            continue;

        int texX = (stripe - (spriteScreenX - (spriteWidth >> 1))) * sprite.width / spriteWidth;
        if (texX < 0 || texX >= sprite.width) continue;

        int bufferX = stripe - sideStartX;

        // Draw vertical strip
        for (int y = drawStartY; y < drawEndY; y++) {
            int texY = (texDrawEndY - y) * sprite.height / spriteHeight;
            if (texY < 0 || texY >= sprite.height) continue;

            uint16_t pixelColor = imgData[texY * sprite.width + texX];
            if (pixelColor != transparent) {
                if (sprite.opacity == 255) {
                    Buffer_SetPixel(bufferX, y, pixelColor);
                } else {
                    Buffer_BlendPixelAlpha(bufferX, y, pixelColor, sprite.opacity);
                }
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
            spriteOrder[activeCount].distance = Fixed_Mul(dx, dx) + Fixed_Mul(dy, dy);
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
            Sprites_Array[i].elevation = 0;
            Sprites_Array[i].opacity = 255;
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

void Sprite_SetElevation(int index, double elevation) {
    if (index < 0 || index >= SPRITES_MAX_COUNT) return;
    if (!Sprites_Array[index].active) return;
    Sprites_Array[index].elevation = FLOAT_TO_FIXED(elevation);
}

void Sprite_SetOpacity(int index, double opacity) {
    if (index < 0 || index >= SPRITES_MAX_COUNT) return;
    if (!Sprites_Array[index].active) return;
    if (opacity < 0.0) opacity = 0.0;
    if (opacity > 1.0) opacity = 1.0;
    Sprites_Array[index].opacity = (uint8_t)(opacity * 255.0 + 0.5);
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
