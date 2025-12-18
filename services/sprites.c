#include "sprites.h"
#include "Graphics.h"
#include "Buffer.h"
#include "Inventory.h"
#include "Sync.h"
#include <stdlib.h>
#include <math.h>

extern double ZBuffer[SCREEN_WIDTH];

extern int numsprites;
extern Sprite Sprites[];
extern Inventory inventory;
extern Item* items[];
extern uint8_t itemsStatus;
uint8_t canSwapItems = 0;
extern uint8_t isSwapping;

// Helper structure for sorting sprites
typedef struct {
    int index;
    double distance;
} SpriteDistancePair;

void generateSprite(){
  uint8_t sprite_count = 0;
  uint8_t sprite_index = (rand() % (numsprites-1)) + 1;
  while (Sprites[sprite_index].width != 0 && sprite_count <= 12){
    sprite_index = (rand() % (numsprites-1)) + 1;
    sprite_count++;
  }
  itemsStatus = sprite_index;
  itemsStatus |= SPAWNCODE << 6;
  Sprites[sprite_index].width = Sprites[sprite_index].height;
}

// Comparison function for sorting sprites
int compareSprites(const void *a, const void *b) {
    const SpriteDistancePair *spriteA = (SpriteDistancePair *)a;
    const SpriteDistancePair *spriteB = (SpriteDistancePair *)b;
    if (spriteA->distance < spriteB->distance) return 1;
    if (spriteA->distance > spriteB->distance) return -1;
    return 0;
}

void RenderSprite(Sprite sprite, int side, int sprite_index) {
    if (sprite_index == 0 && side == 1) self.isOnTarget = 0;
    // Sprite position relative to the player
    double spriteX = sprite.x - self.posX;
    double spriteY = sprite.y - self.posY;

    // Inverse camera transformation
    double invDet = 1.0 / (self.planeX * self.dirY - self.dirX * self.planeY);
    double transformX = invDet * (self.dirY * spriteX - self.dirX * spriteY);
    double transformY = invDet * (-self.planeY * spriteX + self.planeX * spriteY);

    // Ignore if behind player
    if (transformY <= 0.1) return;

    canSwapItems = 0;
    // Pick up sprite if it's an item and we're close enough
    if (sprite_index != 0 && spriteX < .8 && spriteX > -.8 && spriteY < .8 && spriteY > -.8){
        uint8_t pickup_code = Inventory_add(&inventory, items[sprite.type]); // Inventory_add() will return 0 if inventory is full
        if (pickup_code) {
            Sprites[sprite_index].width = 0; // if pickup was successful, remove sprite from map
            itemsStatus = sprite_index; // Send code over to tell other controller that sprite was removed
            itemsStatus |= (PICKUPCODE << 6);
        }
        if (pickup_code == AMMO_SMALL) Inventory_currentItem(&inventory)->tot_ammo += Inventory_currentItem(&inventory)->mag_ammo;
        if (pickup_code == AMMO_BIG) Inventory_currentItem(&inventory)->tot_ammo += Inventory_currentItem(&inventory)->mag_ammo*3;
        // If pickup was not successful, this is a possibility for swapping items
        if (isSwapping && sprite.type != AMMO_SMALL && sprite.type != AMMO_BIG){
            Sprites[sprite_index].width = 0;
            Inventory_replace(&inventory, items[sprite.type]);
            itemsStatus = sprite_index; // Send code over to tell other controller that sprite was removed
            itemsStatus |= (PICKUPCODE << 6);
            isSwapping = 0;
        }
        if (!pickup_code){
            canSwapItems = 1;
        }
    }

    // Project sprite to screen
    int spriteScreenX = (int)((SCREEN_WIDTH / 2) * (1 + transformX / transformY));

    // Calculate sprite height and width
    int originalSpriteHeight = abs((int)(SCREEN_HEIGHT / transformY));
    int originalSpriteWidth = abs((int)(SCREEN_HEIGHT / transformY * sprite.width / sprite.height));

    // Scale sprite based on size
    int spriteHeight = originalSpriteHeight *sprite.scale/8.0;
    int spriteWidth = originalSpriteWidth * sprite.scale/8.0;

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
            // Determine if enemy is on target
            Item* weapon = Inventory_currentItem(&inventory);
            if ((stripe >= SCREEN_WIDTH/2 - weapon->crosshair_size && stripe <= SCREEN_WIDTH/2 + weapon->crosshair_size) && sprite_index == 0 && side == 1 && transformY <= weapon->range) self.isOnTarget = 1;
            // Calculate texture x coordinate
            int texX = (stripe - drawStartX) * sprite.width / spriteWidth;
            if (texX >= 0 && texX < sprite.width) {
                for (int y = drawStartY; y < drawEndY; y++) {
                    if (y >= 0 && y < SCREEN_HEIGHT) {
                        // Calculate texture y coordinate
                        int texY = (int)((drawEndY - y) * sprite.height / spriteHeight);
                        if (texY >= 0 && texY < sprite.height) {
                            int index = texY * sprite.width + texX;
                            int pixelColor = sprite.image[index];

                            if (pixelColor != sprite.transparent) {
                                // If the current pixel is not transparent
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
    SpriteDistancePair spriteOrder[numsprites];
    for (int i = 0; i < numsprites; i++) {
        spriteOrder[i].index = i;
        spriteOrder[i].distance = (self.posX - Sprites[i].x)*(self.posX - Sprites[i].x) + (self.posY - Sprites[i].y)*(self.posY - Sprites[i].y);
    }

    qsort(spriteOrder, numsprites, sizeof(SpriteDistancePair), compareSprites);

    for (int i = 0; i < numsprites; i++) {
        if (Sprites[spriteOrder[i].index].width != 0) RenderSprite(Sprites[spriteOrder[i].index], side, spriteOrder[i].index);
    }
}

void RenderInventory(int side){
    for (int i = 0; i < inventory.size; i++){
        drawForegroundSpriteToBuffer(side, inventory.items[i]->invent_sprite);
    }

    if (side == 0){
         for (int i = 0; i < 16; i++){
             setPixelBuffer(i+(inventory.index*16), 0, MATRIX_NEON_GREEN);
         }
    }
}

extern uint8_t isShooting;
extern Sprite gunFlash;
void RenderForegroundSprites(int side){
    Item* current = Inventory_currentItem(&inventory);
    static uint8_t sidesDrawn = 0; // To ensure flash gets drawn regardless of side, weird synchronization fix
    // Draw flash first if we're shooting
    if (isShooting){
        // To ensure flash shows up in the right spot
        gunFlash.x = current->muzzleX;
        gunFlash.y = current->muzzleY;

        drawForegroundSpriteToBuffer(side, gunFlash);
        sidesDrawn++;
        if (sidesDrawn == 2){
            isShooting = 0; // Only clear flag if both sides have been drawn
            sidesDrawn = 0;
        }
    }

    // Draw current item we're holding
    drawForegroundSpriteToBuffer(side, current->holding_sprite);
    RenderInventory(side);
}