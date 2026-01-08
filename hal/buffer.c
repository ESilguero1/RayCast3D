#include "buffer.h"
#include "../services/graphics.h"
#include "../drivers/ST7735.h"
#include "../drivers/ST7735_DMA.h"
#include "../bus/SPI.h"
#include "../assets/font.h"
#include "../utils/fixed.h"

uint16_t renderBuffer[BUFFER_WIDTH * BUFFER_HEIGHT];

// Configurable colors (defaults)
static uint16_t floorColor = 0x0000;
static uint16_t skyColor = 0x0000;
static fixed_t gradientIntensity = FIXED_ONE;  // 1.0 = full gradient, 0.0 = solid color

uint16_t floorGradient[SCREEN_HEIGHT / 2];

// Precomputed constants for performance
#define BUFFER_SIZE (BUFFER_WIDTH * BUFFER_HEIGHT)
#define BUFFER_HALF_SIZE (BUFFER_SIZE / 2)

static void PrecalculateFloorGradient(void) {
    // Format: BBBBBGGGGGGRRRRR (blue in high bits, red in low bits)
    uint16_t r = floorColor & 0x1F;           // bits 0-4
    uint16_t g = (floorColor >> 5) & 0x3F;    // bits 5-10
    uint16_t b = (floorColor >> 11) & 0x1F;   // bits 11-15

    // Pre-calculate step size in fixed-point
    // baseFactor goes from 0 to 1 as y goes from 0 to SCREEN_HEIGHT/2
    fixed_t baseStep = FIXED_ONE / (SCREEN_HEIGHT / 2);

    for (int y = 0; y < SCREEN_HEIGHT / 2; y++) {
        // intensity=1.0: factor goes 1.0->0.0 (full gradient to black)
        // intensity=0.0: factor stays at 1.0 (solid color)
        fixed_t baseFactor = y * baseStep;
        fixed_t factor = FIXED_ONE - fixed_mul(gradientIntensity, baseFactor);

        // Scale color components (factor is 0 to FIXED_ONE)
        uint16_t scaledR = (r * factor) >> FIXED_SHIFT;
        uint16_t scaledG = (g * factor) >> FIXED_SHIFT;
        uint16_t scaledB = (b * factor) >> FIXED_SHIFT;

        // Put channels back at their original positions
        floorGradient[y] = (scaledB << 11) | (scaledG << 5) | scaledR;
    }
}

void Buffer_Init(void) {
    SPI_Init();
    ST7735_InitR(INITR_REDTAB);
    ST7735_SetRotation(1);
    PrecalculateFloorGradient();
}

void Buffer_SetFloorColor(uint16_t color) {
    floorColor = color;
    PrecalculateFloorGradient();
}

void Buffer_SetSkyColor(uint16_t color) {
    skyColor = color;
}

void Buffer_SetFloorGradient(double intensity) {
    if (intensity < 0.0) intensity = 0.0;
    if (intensity > 1.0) intensity = 1.0;
    gradientIntensity = FLOAT_TO_FIXED(intensity);
    PrecalculateFloorGradient();
}

void clearRenderBuffer(void) {
    // Optimized: use 32-bit writes to store 2 pixels at once
    uint32_t* bufPtr32 = (uint32_t*)renderBuffer;

    // Floor gradient (bottom half) - each row same color
    for (int y = 0; y < SCREEN_HEIGHT / 2; y++) {
        uint32_t gradColor32 = floorGradient[y] | ((uint32_t)floorGradient[y] << 16);
        // BUFFER_WIDTH/2 iterations (2 pixels per write), unrolled 4x
        for (int x = 0; x < BUFFER_WIDTH / 8; x++) {
            *bufPtr32++ = gradColor32;
            *bufPtr32++ = gradColor32;
            *bufPtr32++ = gradColor32;
            *bufPtr32++ = gradColor32;
        }
    }

    // Sky (top half) - solid color, pack into 32-bit
    uint32_t skyColor32 = skyColor | ((uint32_t)skyColor << 16);
    // BUFFER_HALF_SIZE/2 iterations, unrolled 4x
    for (int i = 0; i < BUFFER_HALF_SIZE / 8; i++) {
        *bufPtr32++ = skyColor32;
        *bufPtr32++ = skyColor32;
        *bufPtr32++ = skyColor32;
        *bufPtr32++ = skyColor32;
    }
}

void setPixelBuffer(int x, int y, uint16_t color) {
  if (x >= BUFFER_WIDTH){
    x -= BUFFER_WIDTH;
  }
  if (x >= 0 && x < BUFFER_WIDTH && y >= 0 && y < BUFFER_HEIGHT) {
   int index = y * BUFFER_WIDTH + x;
   renderBuffer[index] = color;
  }
 }

 void blitBufferToRenderBuffer(uint16_t* srcBuffer, int srcWidth, int srcHeight, int destX, int destY) {
    for (int y = 0; y < srcHeight; y++) {
        int renderY = destY + y;
        if (renderY >= 0 && renderY < BUFFER_HEIGHT) {
            for (int x = 0; x < srcWidth; x++) {
                int renderX = destX + x;
                if (renderX >= 0 && renderX < BUFFER_WIDTH) {
                    renderBuffer[renderY * BUFFER_WIDTH + renderX] = srcBuffer[y * srcWidth + x];
                }
            }
        }
    }
}

void drawForegroundSpriteToBuffer(int side, Sprite sprite) {
    if (sprite.image == 0) return;
    // Scale of 8 = full screen height, use integer math
    // sizeFactor = scale / 8, so scaledHeight = SCREEN_HEIGHT * scale / 8
    int scaledSpriteHeight = (SCREEN_HEIGHT * sprite.scale) >> 3;
    int scaledSpriteWidth = (scaledSpriteHeight * sprite.width) / sprite.height;

    int spriteBottomCenterY = (int)sprite.y;
    int spriteBottomCenterX = (int)sprite.x;

    int spriteTopY = spriteBottomCenterY - scaledSpriteHeight;
    int spriteLeftX = spriteBottomCenterX - scaledSpriteWidth/2;

    // Calculate screen-space drawing boundaries of the sprite
    int drawStartX = spriteLeftX;
    int drawEndX = spriteLeftX + scaledSpriteWidth;
    int drawStartY = spriteTopY;
    int drawEndY = spriteTopY + scaledSpriteHeight;

    int bufferBoundary = SCREEN_WIDTH / 2;

    for (int stripe = drawStartX; stripe < drawEndX; stripe++) {
        int bufferX = -1;

        if (side == 0 && stripe >= 0 && stripe < bufferBoundary) {
            bufferX = stripe;
        } else if (side == 1 && stripe >= bufferBoundary && stripe < SCREEN_WIDTH) {
            bufferX = stripe - bufferBoundary;
        }

        if (bufferX != -1) {
            // Calculate texture x coordinate
            int texX = (stripe - drawStartX) * sprite.width / scaledSpriteWidth;
            if (texX >= 0 && texX < sprite.width) {
                for (int y = drawStartY; y < drawEndY; y++) {
                    if (y >= 0 && y < SCREEN_HEIGHT) {
                        // Calculate texture y coordinate (assuming sprite image is top-down)
                        int texY = (y - drawStartY) * sprite.height / scaledSpriteHeight;
                        if (texY >= 0 && texY < sprite.height) {
                            int index = texY * sprite.width + texX;
                            uint16_t pixelColor = sprite.image[index];

                            if (pixelColor != sprite.transparent) {
                                setPixelBuffer(bufferX, BUFFER_HEIGHT - 1 - y, pixelColor);
                            }
                        }
                    }
                }
            }
        }
    }
}

void drawCharToBuffer(char ch, int screenX, int screenY, uint16_t color, int side) {
    if (ch < 0 || ch > (sizeof(Font) / FONT_BYTES_PER_CHAR) - 1) return;

    int charIndex = ch * FONT_BYTES_PER_CHAR;
    int bufferBoundary = SCREEN_WIDTH / 2;

    for (int col = 0; col < FONT_WIDTH; col++) {
        int pixelScreenX = screenX + col;
        int bufferX = -1;

        // Check if this column falls on the current side
        if (side == 0 && pixelScreenX >= 0 && pixelScreenX < bufferBoundary) {
            bufferX = pixelScreenX;
        } else if (side == 1 && pixelScreenX >= bufferBoundary && pixelScreenX < SCREEN_WIDTH) {
            bufferX = pixelScreenX - bufferBoundary;
        }

        if (bufferX != -1) {
            uint8_t colData = Font[charIndex + col];
            for (int row = 0; row < FONT_HEIGHT; row++) {
                if ((colData >> row) & 0x01) {
                    setPixelBuffer(bufferX, BUFFER_HEIGHT - 1 - (screenY + row), color);
                }
            }
        }
    }
}

void printToBuffer(const char *text, int screenX, int screenY, uint16_t color, int side) {
    int currentScreenX = screenX;
    int bufferBoundary = SCREEN_WIDTH / 2;

    for (int i = 0; text[i] != '\0'; i++) {
        // Calculate the screen range for the current character
        int charStartX = currentScreenX;
        int charEndX = currentScreenX + FONT_WIDTH - 1;

        // Check if any part of the character falls within the current side's screen range
        int onSide0 = (side == 0 && charStartX < bufferBoundary);
        int onSide1 = (side == 1 && charEndX >= bufferBoundary && charStartX < SCREEN_WIDTH);

        if (onSide0 || onSide1) {
            drawCharToBuffer(text[i], currentScreenX, screenY, color, side);
        }
        currentScreenX += FONT_WIDTH + FONT_SPACE;
    }
}

void RenderBuffer(int side){
  if(side == 0) ST7735_DrawBitmap(0, BUFFER_HEIGHT-1, renderBuffer, BUFFER_WIDTH, BUFFER_HEIGHT);
  else ST7735_DrawBitmap(SCREEN_WIDTH/2, BUFFER_HEIGHT-1, renderBuffer, BUFFER_WIDTH, BUFFER_HEIGHT);
}

int RenderBufferDMA(int side, void (*callback)(void)) {
    int x = (side == 0) ? 0 : SCREEN_WIDTH / 2;
    return ST7735_DrawBitmapDMA(x, BUFFER_HEIGHT - 1, renderBuffer,
                                BUFFER_WIDTH, BUFFER_HEIGHT, callback);
}

int RenderBuffer_IsBusy(void) {
    return ST7735_DMA_IsBusy();
}

void RenderBuffer_WaitComplete(void) {
    ST7735_DMA_WaitComplete();
}