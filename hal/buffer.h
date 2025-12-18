#ifndef BUFFER_H_
#define BUFFER_H_

#include "Graphics.h"
#include "sprites.h"
#include <stdint.h>

#define BUFFER_WIDTH SCREEN_WIDTH / 2
#define BUFFER_HEIGHT SCREEN_HEIGHT

extern uint16_t renderBuffer[BUFFER_WIDTH * BUFFER_HEIGHT];

void PrecalculateFloorGradient();
void clearRenderBuffer();
void setPixelBuffer(int x, int y, uint16_t color);
void drawForegroundSpriteToBuffer(int side, Sprite sprite);
void blitBufferToRenderBuffer(uint16_t* srcBuffer, int srcWidth, int srcHeight, int destX, int destY);
void printToBuffer(const char *text, int screenX, int screenY, uint16_t color, int side);
void RenderBuffer(int side);

#endif /* BUFFER_H_ */