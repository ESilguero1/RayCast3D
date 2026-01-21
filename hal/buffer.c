/* buffer.c
 * Double-Buffered Rendering HAL for RayCast3D
 * Manages quarter-screen render buffers with DMA transfer
 *
 * Author: Elijah Silguero
 * Created: December 2025
 * Modified: January 2026
 * Hardware: MSPM0G3507 with ST7735 LCD
 */

#include "buffer.h"
#include "../drivers/ST7735_DMA.h"
#include "../inc/ST7735.h"
#include "../inc/SPI.h"
#include "../assets/font.h"
#include "../utils/fixed.h"

/*---------------------------------------------------------------------------
 * Private Constants
 *---------------------------------------------------------------------------*/

/* Byte-swap macro for ST7735 (MSB first) */
#define SWAP16(c) (((c) >> 8) | ((c) << 8))

/* Precomputed buffer sizes for performance */
#define BUFFER_SIZE (BUFFER_WIDTH * BUFFER_HEIGHT)
#define BUFFER_HALF_SIZE (BUFFER_SIZE / 2)

/*---------------------------------------------------------------------------
 * Private Variables
 *---------------------------------------------------------------------------*/

/* Double-buffer: one for rendering, one for DMA */
static uint16_t BufferA[BUFFER_WIDTH * BUFFER_HEIGHT];
static uint16_t BufferB[BUFFER_WIDTH * BUFFER_HEIGHT];

/* Pointers for buffer swapping (render to one, DMA from other) */
uint16_t* Buffer_RenderBuffer = BufferA;
static uint16_t* DmaBuffer = BufferB;

/* Configurable colors (defaults) - stored in native format */
static uint16_t FloorColor = 0x0000;
static uint16_t SkyColor = 0x0000;
static uint16_t SkyColorSwapped = 0x0000;  /* Pre-swapped for DMA */
static fixed_t GradientIntensity = FIXED_ONE;  /* 1.0 = full gradient */

/* Floor gradient stored pre-swapped for DMA */
static uint16_t FloorGradient[SCREEN_HEIGHT / 2];

/*---------------------------------------------------------------------------
 * Private Function Prototypes
 *---------------------------------------------------------------------------*/

static void precalculateFloorGradient(void);
static void drawCharToBuffer(char ch, int screenX, int screenY,
                             uint16_t color, int side);

/*---------------------------------------------------------------------------
 * Private Functions
 *---------------------------------------------------------------------------*/

static void precalculateFloorGradient(void) {
    /* Extract RGB565 color components */
    uint16_t r = FloorColor & 0x1F;           /* bits 0-4 (red) */
    uint16_t g = (FloorColor >> 5) & 0x3F;    /* bits 5-10 (green) */
    uint16_t b = (FloorColor >> 11) & 0x1F;   /* bits 11-15 (blue) */

    /* Pre-calculate step size in fixed-point */
    fixed_t baseStep = FIXED_ONE / (SCREEN_HEIGHT / 2);

    for (int y = 0; y < SCREEN_HEIGHT / 2; y++) {
        /* intensity=1.0: factor goes 1.0->0.0 (full gradient to black) */
        /* intensity=0.0: factor stays at 1.0 (solid color) */
        fixed_t baseFactor = y * baseStep;
        fixed_t factor = FIXED_ONE - fixed_mul(GradientIntensity, baseFactor);

        /* Scale color components */
        uint16_t scaledR = (r * factor) >> FIXED_SHIFT;
        uint16_t scaledG = (g * factor) >> FIXED_SHIFT;
        uint16_t scaledB = (b * factor) >> FIXED_SHIFT;

        /* Reconstruct color and store pre-swapped for DMA */
        uint16_t color = (scaledB << 11) | (scaledG << 5) | scaledR;
        FloorGradient[y] = SWAP16(color);
    }
}

/*---------------------------------------------------------------------------
 * Public Functions - Initialization
 *---------------------------------------------------------------------------*/

void Buffer_Init(void) {
    SPI_Init();
    ST7735_InitR(INITR_REDTAB);
    ST7735_SetRotation(1);
    precalculateFloorGradient();
}

/*---------------------------------------------------------------------------
 * Public Functions - Configuration
 *---------------------------------------------------------------------------*/

void Buffer_SetFloorColor(uint16_t color) {
    FloorColor = color;
    precalculateFloorGradient();
}

void Buffer_SetSkyColor(uint16_t color) {
    SkyColor = color;
    SkyColorSwapped = SWAP16(color);
}

void Buffer_SetFloorGradient(double intensity) {
    if (intensity < 0.0) {
        intensity = 0.0;
    }
    if (intensity > 1.0) {
        intensity = 1.0;
    }
    GradientIntensity = FLOAT_TO_FIXED(intensity);
    precalculateFloorGradient();
}

/*---------------------------------------------------------------------------
 * Public Functions - Rendering Operations
 *---------------------------------------------------------------------------*/

void Buffer_Clear(void) {
    /* Optimized: use 32-bit writes to store 2 pixels at once */
    uint32_t* bufPtr32 = (uint32_t*)Buffer_RenderBuffer;

    /* Sky (top half of screen = buffer rows 0-63) */
    uint32_t skyColor32 = SkyColorSwapped | ((uint32_t)SkyColorSwapped << 16);
    for (int i = 0; i < BUFFER_HALF_SIZE / 8; i++) {
        *bufPtr32++ = skyColor32;
        *bufPtr32++ = skyColor32;
        *bufPtr32++ = skyColor32;
        *bufPtr32++ = skyColor32;
    }

    /* Floor gradient (bottom half of screen = buffer rows 64-127) */
    for (int y = 0; y < SCREEN_HEIGHT / 2; y++) {
        uint32_t gradColor32 = FloorGradient[y] | ((uint32_t)FloorGradient[y] << 16);
        for (int x = 0; x < BUFFER_WIDTH / 8; x++) {
            *bufPtr32++ = gradColor32;
            *bufPtr32++ = gradColor32;
            *bufPtr32++ = gradColor32;
            *bufPtr32++ = gradColor32;
        }
    }
}

void Buffer_SetPixel(int x, int y, uint16_t color) {
    /* Bounds check - callers pass buffer-local coordinates */
    if (x >= 0 && x < BUFFER_WIDTH && y >= 0 && y < BUFFER_HEIGHT) {
        /* Store Y-inverted so DMA sends in natural order */
        int index = (BUFFER_HEIGHT - 1 - y) * BUFFER_WIDTH + x;
        Buffer_RenderBuffer[index] = SWAP16(color);
    }
}

void Buffer_Blit(uint16_t* srcBuffer, int srcWidth, int srcHeight,
                 int destX, int destY) {
    for (int y = 0; y < srcHeight; y++) {
        int renderY = destY + y;
        if (renderY >= 0 && renderY < BUFFER_HEIGHT) {
            for (int x = 0; x < srcWidth; x++) {
                int renderX = destX + x;
                if (renderX >= 0 && renderX < BUFFER_WIDTH) {
                    int idx = renderY * BUFFER_WIDTH + renderX;
                    Buffer_RenderBuffer[idx] = srcBuffer[y * srcWidth + x];
                }
            }
        }
    }
}

void Buffer_DrawForegroundSprite(int side, Sprite sprite) {
    if (sprite.image == 0) {
        return;
    }

    /* Scale of 8 = full screen height */
    int scaledSpriteHeight = (SCREEN_HEIGHT * sprite.scale) >> 3;
    int scaledSpriteWidth = (scaledSpriteHeight * sprite.width) / sprite.height;

    int spriteBottomCenterY = (int)sprite.y;
    int spriteBottomCenterX = (int)sprite.x;

    int spriteTopY = spriteBottomCenterY - scaledSpriteHeight;
    int spriteLeftX = spriteBottomCenterX - scaledSpriteWidth / 2;

    /* Calculate screen-space drawing boundaries */
    int drawStartX = spriteLeftX;
    int drawEndX = spriteLeftX + scaledSpriteWidth;
    int drawStartY = spriteTopY;
    int drawEndY = spriteTopY + scaledSpriteHeight;

    /* Quarter-screen: each side covers BUFFER_WIDTH columns */
    int sideStartX = side * BUFFER_WIDTH;
    int sideEndX = sideStartX + BUFFER_WIDTH;

    for (int stripe = drawStartX; stripe < drawEndX; stripe++) {
        /* Check if column falls within current side's range */
        if (stripe >= sideStartX && stripe < sideEndX) {
            int bufferX = stripe - sideStartX;

            /* Calculate texture x coordinate */
            int texX = (stripe - drawStartX) * sprite.width / scaledSpriteWidth;
            if (texX >= 0 && texX < sprite.width) {
                for (int y = drawStartY; y < drawEndY; y++) {
                    if (y >= 0 && y < SCREEN_HEIGHT) {
                        int texY = (y - drawStartY) * sprite.height / scaledSpriteHeight;
                        if (texY >= 0 && texY < sprite.height) {
                            int index = texY * sprite.width + texX;
                            uint16_t pixelColor = sprite.image[index];

                            if (pixelColor != sprite.transparent) {
                                Buffer_SetPixel(bufferX, BUFFER_HEIGHT - 1 - y,
                                                pixelColor);
                            }
                        }
                    }
                }
            }
        }
    }
}

static void drawCharToBuffer(char ch, int screenX, int screenY,
                             uint16_t color, int side) {
    if (ch < 0 || ch > (sizeof(Font) / FONT_BYTES_PER_CHAR) - 1) {
        return;
    }

    int charIndex = ch * FONT_BYTES_PER_CHAR;

    /* Quarter-screen: each side covers BUFFER_WIDTH columns */
    int sideStartX = side * BUFFER_WIDTH;
    int sideEndX = sideStartX + BUFFER_WIDTH;

    for (int col = 0; col < FONT_WIDTH; col++) {
        int pixelScreenX = screenX + col;

        /* Check if column falls within current side's range */
        if (pixelScreenX >= sideStartX && pixelScreenX < sideEndX) {
            int bufferX = pixelScreenX - sideStartX;
            uint8_t colData = Font[charIndex + col];
            for (int row = 0; row < FONT_HEIGHT; row++) {
                if ((colData >> row) & 0x01) {
                    Buffer_SetPixel(bufferX, BUFFER_HEIGHT - 1 - (screenY + row),
                                    color);
                }
            }
        }
    }
}

void Buffer_PrintText(const char *text, int screenX, int screenY,
                      uint16_t color, int side) {
    int currentScreenX = screenX;

    /* Quarter-screen: each side covers BUFFER_WIDTH columns */
    int sideStartX = side * BUFFER_WIDTH;
    int sideEndX = sideStartX + BUFFER_WIDTH;

    for (int i = 0; text[i] != '\0'; i++) {
        int charStartX = currentScreenX;
        int charEndX = currentScreenX + FONT_WIDTH - 1;

        /* Check if any part of character overlaps current side's range */
        if (charEndX >= sideStartX && charStartX < sideEndX) {
            drawCharToBuffer(text[i], currentScreenX, screenY, color, side);
        }
        currentScreenX += FONT_WIDTH + FONT_SPACE;
    }
}

/*---------------------------------------------------------------------------
 * Public Functions - DMA Transfer Operations
 *---------------------------------------------------------------------------*/

int Buffer_RenderDMA(int side, void (*callback)(void)) {
    /* Swap buffers: what we just rendered becomes the DMA source */
    uint16_t* temp = Buffer_RenderBuffer;
    Buffer_RenderBuffer = DmaBuffer;
    DmaBuffer = temp;

    /* Quarter-screen: side 0-3, each BUFFER_WIDTH pixels wide */
    int x = side * BUFFER_WIDTH;
    return ST7735_DrawBitmapDMA(x, BUFFER_HEIGHT - 1, DmaBuffer,
                                BUFFER_WIDTH, BUFFER_HEIGHT, callback);
}

int Buffer_IsBusy(void) {
    return ST7735_DMA_IsBusy();
}

void Buffer_WaitComplete(void) {
    ST7735_DMA_WaitComplete();
}