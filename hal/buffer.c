#include "buffer.h"
#include "../services/graphics.h"
#include "../drivers/ST7735_DMA.h"
#include "../inc/ST7735.h"
#include "../inc/SPI.h"
#include "../assets/font.h"
#include "../utils/fixed.h"

// Double-buffer: one for rendering, one for DMA
static uint16_t bufferA[BUFFER_WIDTH * BUFFER_HEIGHT];
static uint16_t bufferB[BUFFER_WIDTH * BUFFER_HEIGHT];

// Pointers for buffer swapping (render to one, DMA from other)
uint16_t* renderBuffer = bufferA;
static uint16_t* dmaBuffer = bufferB;

// Byte-swap macro for ST7735 (MSB first)
#define SWAP16(c) (((c) >> 8) | ((c) << 8))

// Configurable colors (defaults) - stored in native format
static uint16_t floorColor = 0x0000;
static uint16_t skyColor = 0x0000;
static uint16_t skyColorSwapped = 0x0000;  // Pre-swapped for DMA
static fixed_t gradientIntensity = FIXED_ONE;  // 1.0 = full gradient, 0.0 = solid color

// Floor gradient stored pre-swapped for DMA
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

        // Put channels back and store PRE-SWAPPED for DMA
        uint16_t color = (scaledB << 11) | (scaledG << 5) | scaledR;
        floorGradient[y] = SWAP16(color);
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
    skyColorSwapped = SWAP16(color);
}

void Buffer_SetFloorGradient(double intensity) {
    if (intensity < 0.0) intensity = 0.0;
    if (intensity > 1.0) intensity = 1.0;
    gradientIntensity = FLOAT_TO_FIXED(intensity);
    PrecalculateFloorGradient();
}

void clearRenderBuffer(void) {
    // Optimized: use 32-bit writes to store 2 pixels at once
    // Y-inverted storage: buffer row 0 = screen top, row 127 = screen bottom
    uint32_t* bufPtr32 = (uint32_t*)renderBuffer;

    // Sky (top half of screen = buffer rows 0-63)
    uint32_t skyColor32 = skyColorSwapped | ((uint32_t)skyColorSwapped << 16);
    for (int i = 0; i < BUFFER_HALF_SIZE / 8; i++) {
        *bufPtr32++ = skyColor32;
        *bufPtr32++ = skyColor32;
        *bufPtr32++ = skyColor32;
        *bufPtr32++ = skyColor32;
    }

    // Floor gradient (bottom half of screen = buffer rows 64-127)
    // floorGradient[0] = horizon (bright), floorGradient[63] = bottom edge (dark)
    for (int y = 0; y < SCREEN_HEIGHT / 2; y++) {
        uint32_t gradColor32 = floorGradient[y] | ((uint32_t)floorGradient[y] << 16);
        for (int x = 0; x < BUFFER_WIDTH / 8; x++) {
            *bufPtr32++ = gradColor32;
            *bufPtr32++ = gradColor32;
            *bufPtr32++ = gradColor32;
            *bufPtr32++ = gradColor32;
        }
    }
}

void setPixelBuffer(int x, int y, uint16_t color) {
    // Bounds check only - callers now pass buffer-local coordinates (0 to BUFFER_WIDTH-1)
    if (x >= 0 && x < BUFFER_WIDTH && y >= 0 && y < BUFFER_HEIGHT) {
        // Store Y-inverted so DMA can send in natural order (row 0 first = bottom of screen)
        // Also pre-swap bytes for ST7735 (MSB first)
        int index = (BUFFER_HEIGHT - 1 - y) * BUFFER_WIDTH + x;
        renderBuffer[index] = SWAP16(color);
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

    // Quarter-screen: each side covers BUFFER_WIDTH (40) columns
    int sideStartX = side * BUFFER_WIDTH;
    int sideEndX = sideStartX + BUFFER_WIDTH;

    for (int stripe = drawStartX; stripe < drawEndX; stripe++) {
        // Check if this screen column falls within current side's range
        if (stripe >= sideStartX && stripe < sideEndX) {
            int bufferX = stripe - sideStartX;

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

    // Quarter-screen: each side covers BUFFER_WIDTH (40) columns
    int sideStartX = side * BUFFER_WIDTH;
    int sideEndX = sideStartX + BUFFER_WIDTH;

    for (int col = 0; col < FONT_WIDTH; col++) {
        int pixelScreenX = screenX + col;

        // Check if this column falls within current side's range
        if (pixelScreenX >= sideStartX && pixelScreenX < sideEndX) {
            int bufferX = pixelScreenX - sideStartX;
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

    // Quarter-screen: each side covers BUFFER_WIDTH (40) columns
    int sideStartX = side * BUFFER_WIDTH;
    int sideEndX = sideStartX + BUFFER_WIDTH;

    for (int i = 0; text[i] != '\0'; i++) {
        // Calculate the screen range for the current character
        int charStartX = currentScreenX;
        int charEndX = currentScreenX + FONT_WIDTH - 1;

        // Check if any part of the character overlaps current side's range
        if (charEndX >= sideStartX && charStartX < sideEndX) {
            drawCharToBuffer(text[i], currentScreenX, screenY, color, side);
        }
        currentScreenX += FONT_WIDTH + FONT_SPACE;
    }
}

int RenderBufferDMA(int side, void (*callback)(void)) {
    // Swap buffers: what we just rendered becomes the DMA source
    uint16_t* temp = renderBuffer;
    renderBuffer = dmaBuffer;
    dmaBuffer = temp;

    // Quarter-screen: side 0-3, each 40 pixels wide
    int x = side * BUFFER_WIDTH;
    return ST7735_DrawBitmapDMA(x, BUFFER_HEIGHT - 1, dmaBuffer,
                                BUFFER_WIDTH, BUFFER_HEIGHT, callback);
}

int RenderBuffer_IsBusy(void) {
    return ST7735_DMA_IsBusy();
}

void RenderBuffer_WaitComplete(void) {
    ST7735_DMA_WaitComplete();
}