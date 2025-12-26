/* sprites.c
 * RayCast3D Sprite Rendering
 * Core sprite rendering functions
 */

#include "sprites.h"
#include "graphics.h"
#include "../hal/buffer.h"
#include <stdlib.h>
#include <math.h>

// External references
extern double ZBuffer[SCREEN_WIDTH];

// Sprite storage
int numSprites = 0;
Sprite sprites[MAX_SPRITES];

// Helper structure for sorting sprites
typedef struct {
    int index;
    double distance;
} SpriteDistancePair;

// Comparison function for sorting sprites by distance (far to near)
static int compareSprites(const void *a, const void *b) {
    const SpriteDistancePair *spriteA = (SpriteDistancePair *)a;
    const SpriteDistancePair *spriteB = (SpriteDistancePair *)b;
    if (spriteA->distance < spriteB->distance) return 1;
    if (spriteA->distance > spriteB->distance) return -1;
    return 0;
}

void RenderSprite(Sprite sprite, int side, int spriteIndex) {
    const Camera* cam = Camera_Get();

    // Sprite position relative to the camera
    double spriteX = sprite.x - cam->posX;
    double spriteY = sprite.y - cam->posY;

    // Inverse camera transformation
    double invDet = 1.0 / (cam->planeX * cam->dirY - cam->dirX * cam->planeY);
    double transformX = invDet * (cam->dirY * spriteX - cam->dirX * spriteY);
    double transformY = invDet * (-cam->planeY * spriteX + cam->planeX * spriteY);

    // Ignore if behind camera
    if (transformY <= 0.1) return;

    // Project sprite to screen
    int spriteScreenX = (int)((SCREEN_WIDTH / 2) * (1 + transformX / transformY));

    // Calculate sprite height and width
    int originalSpriteHeight = abs((int)(SCREEN_HEIGHT / transformY));
    int originalSpriteWidth = abs((int)(SCREEN_HEIGHT / transformY * sprite.width / sprite.height));

    // Scale sprite based on size
    int spriteHeight = originalSpriteHeight * sprite.scale / 8.0;
    int spriteWidth = originalSpriteWidth * sprite.scale / 8.0;

    double pushdown = (originalSpriteHeight - spriteHeight) / 2.0;

    // Calculate vertical drawing boundaries
    int drawStartY = -spriteHeight / 2 + SCREEN_HEIGHT / 2 - pushdown;
    int drawEndY = spriteHeight / 2 + SCREEN_HEIGHT / 2 - pushdown;

    // Calculate horizontal drawing boundaries
    int drawStartX = -spriteWidth / 2 + spriteScreenX;
    int drawEndX = (spriteWidth + 1) / 2 + spriteScreenX;

    int bufferBoundary = SCREEN_WIDTH / 2;

    // Draw sprite to buffer
    for (int stripe = drawStartX; stripe < drawEndX; stripe++) {
        int bufferX = -1;

        if (side == 0 && stripe >= 0 && stripe < bufferBoundary) {
            bufferX = stripe;
        } else if (side == 1 && stripe >= bufferBoundary && stripe < SCREEN_WIDTH) {
            bufferX = stripe - bufferBoundary;
        }

        if (bufferX != -1 && transformY < ZBuffer[stripe]) {
            // Calculate texture x coordinate
            int texX = (stripe - drawStartX) * sprite.width / spriteWidth;
            if (texX >= 0 && texX < sprite.width) {
                for (int y = drawStartY; y < drawEndY; y++) {
                    if (y >= 0 && y < SCREEN_HEIGHT) {
                        // Calculate texture y coordinate
                        int texY = (int)((drawEndY - y) * sprite.height / spriteHeight);
                        if (texY >= 0 && texY < sprite.height) {
                            int index = texY * sprite.width + texX;
                            uint16_t pixelColor = sprite.image[index];

                            if (pixelColor != sprite.transparent) {
                                setPixelBuffer(bufferX, y, pixelColor);
                            }
                        }
                    }
                }
            }
        }
    }
}

void RenderSprites(int side) {
    const Camera* cam = Camera_Get();
    SpriteDistancePair spriteOrder[MAX_SPRITES];
    int activeCount = 0;

    // Build list of active sprites with their distances
    for (int i = 0; i < MAX_SPRITES; i++) {
        if (sprites[i].active) {
            spriteOrder[activeCount].index = i;
            spriteOrder[activeCount].distance = (cam->posX - sprites[i].x) * (cam->posX - sprites[i].x) +
                                                 (cam->posY - sprites[i].y) * (cam->posY - sprites[i].y);
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

int Sprite_Add(double y, double x, const uint16_t* image, int width, int height, int scale, uint16_t transparent) {
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
