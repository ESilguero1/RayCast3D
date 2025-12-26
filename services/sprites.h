#ifndef SPRITES_H_
#define SPRITES_H_

#include <stdint.h>

// Sprite structure for world sprites
typedef struct {
    double x;
    double y;
    const uint16_t* image;
    uint16_t transparent;
    int width;
    int height;
    int scale;
    int8_t type;
} Sprite;

// Maximum number of sprites in the world
#define MAX_SPRITES 16

// Sprite array and count (defined in sprites.c)
extern int numSprites;
extern Sprite sprites[MAX_SPRITES];

// Core sprite functions
void RenderSprites(int side);
void RenderSprite(Sprite sprite, int side, int spriteIndex);

// Sprite management
int Sprite_Add(double y, double x, const uint16_t* image, int width, int height, int scale, uint16_t transparent);
void Sprite_Clear(void);
void Sprite_Remove(int index);

#endif /* SPRITES_H_ */