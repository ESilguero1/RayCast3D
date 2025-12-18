#ifndef SPRITES_H_
#define SPRITES_H_

#include <stdint.h>

typedef struct{
    double x;
    double y;
    const uint16_t* image;
    uint16_t transparent;
    int width;
    int height;
    int scale;
    int8_t type;
} Sprite;

void RenderSprites(int side);

void RenderForegroundSprites(int side);

void generateSprite();

#endif /* SPRITES_H_ */