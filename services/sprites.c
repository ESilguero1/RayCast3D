/* sprites.c
 * RayCast3D Sprite Rendering
 * Core sprite rendering functions
 * Optimized with fixed-point math for embedded performance
 */

#include "sprites.h"
#include "graphics.h"
#include "../hal/buffer.h"
#include "../utils/fixed.h"
#include <stdlib.h>

// External references (now fixed-point)
extern fixed_t ZBuffer[SCREEN_WIDTH];

// Sprite storage
int numSprites = 0;
Sprite sprites[MAX_SPRITES];

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

void RenderSprite(Sprite sprite, int side, int spriteIndex) {
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
                setPixelBuffer(visibleCols[i].bufferX, y, pixelColor);
            }
        }
    }
}

void RenderSprites(int side) {
    const Camera* cam = Camera_Get();
    SpriteDistancePair spriteOrder[MAX_SPRITES];
    int activeCount = 0;

    // Build list of active sprites with their distances (fixed-point)
    for (int i = 0; i < MAX_SPRITES; i++) {
        if (sprites[i].active) {
            spriteOrder[activeCount].index = i;
            // Calculate distance squared in fixed-point
            fixed_t dx = cam->posX - FLOAT_TO_FIXED(sprites[i].x);
            fixed_t dy = cam->posY - FLOAT_TO_FIXED(sprites[i].y);
            // Distance squared (no need for sqrt, just for sorting)
            spriteOrder[activeCount].distance = fixed_mul(dx, dx) + fixed_mul(dy, dy);
            activeCount++;
        }
    }

    qsort(spriteOrder, activeCount, sizeof(SpriteDistancePair), compareSprites);

    for (int i = 0; i < activeCount; i++) {
        if (sprites[spriteOrder[i].index].width != 0) {
            RenderSprite(sprites[spriteOrder[i].index], side, spriteOrder[i].index);
        }
    }
}

uint8_t Sprite_Add(double x, double y, const uint16_t* image, int width, int height, int scale, uint16_t transparent) {
    // Find first inactive slot
    for (int i = 0; i < MAX_SPRITES; i++) {
        if (!sprites[i].active) {
            sprites[i].x = x;
            sprites[i].y = y;
            sprites[i].image = image;
            sprites[i].width = width;
            sprites[i].height = height;
            sprites[i].scale = scale;
            sprites[i].transparent = transparent;
            sprites[i].type = 0;
            sprites[i].active = 1;
            numSprites++;
            return i;  // Index remains stable even after other sprites are removed
        }
    }
    return -1;  // No free slots
}

void Sprite_Clear(void) {
    for (int i = 0; i < MAX_SPRITES; i++) {
        sprites[i].active = 0;
    }
    numSprites = 0;
}

void Sprite_Remove(int index) {
    if (index < 0 || index >= MAX_SPRITES) return;
    if (!sprites[index].active) return;  // Already inactive

    sprites[index].active = 0;
    numSprites--;
}
