/* graphics.c
 * RayCast3D Graphics Library
 * Core raycasting and rendering functions
 * Optimized with fixed-point math for embedded performance
 */

#include <stdint.h>
#include <ti/devices/msp/msp.h> // Remove this in production
#include "../inc/LaunchPad.h" // Remove this in production
#include "../inc/Clock.h"
#include "graphics.h"
#include "sprites.h"
#include "../hal/buffer.h"
#include "../drivers/ST7735_DMA.h"
#include "../assets/textures.h"
#include "../utils/fixed.h"
#include "../utils/fpscounter.h"

// Z-buffer for depth sorting (fixed-point Q16.16)
fixed_t ZBuffer[SCREEN_WIDTH];

// FPS display state
static int fpsEnabled = 0;
static int fpsX = 0;
static int fpsY = 0;
static uint16_t fpsColor = 0xFFFF;


// Text queue
#define MAX_TEXT_QUEUE 8
#define MAX_TEXT_LENGTH 32
typedef struct {
    char text[MAX_TEXT_LENGTH];
    int x;
    int y;
    uint16_t color;
} TextEntry;
static TextEntry textQueue[MAX_TEXT_QUEUE];
static int textQueueCount = 0;

// Foreground sprite queue
#define MAX_FG_SPRITE_QUEUE 8
typedef struct {
    const uint16_t* image;
    int x;
    int y;
    int width;
    int height;
    int scale;
    uint16_t transparent;
} FGSpriteEntry;
static FGSpriteEntry fgSpriteQueue[MAX_FG_SPRITE_QUEUE];
static int fgSpriteQueueCount = 0;

// Forward declarations
static void drawFPSOverlay(int side);
static void drawTextQueue(int side);
static void drawFGSpriteQueue(int side);

void CastRays(int side) {
    const Camera* cam = Camera_Get();

    // Quarter-screen: side 0-3, each covers BUFFER_WIDTH (40) columns
    int startX = side * BUFFER_WIDTH;
    int endX = startX + BUFFER_WIDTH;

    // Pre-calculate values used in the loop
    // cameraX = 2 * x / SCREEN_WIDTH - 1, ranges from -1 to +1
    // We'll compute: cameraX_fixed = (2 * x * 65536 / SCREEN_WIDTH) - 65536
    // Simplified: cameraX_step = 2 * 65536 / SCREEN_WIDTH = 819 (for 160 pixels)
    const fixed_t cameraX_step = (2 * FIXED_ONE) / SCREEN_WIDTH;  // 819 for 160px

    for (int x = startX; x < endX; x++) {
        // Calculate ray position and direction (all fixed-point)
        fixed_t cameraX = (x * cameraX_step) - FIXED_ONE;  // Range: -1 to +1

        fixed_t rayDirX = cam->dirX + fixed_mul(cam->planeX, cameraX);
        fixed_t rayDirY = cam->dirY + fixed_mul(cam->planeY, cameraX);

        // Which box of the map we're in
        int mapX = FIXED_TO_INT(cam->posX);
        int mapY = FIXED_TO_INT(cam->posY);

        // Length of ray from current position to next x or y-side
        fixed_t sideDistX;
        fixed_t sideDistY;

        // Length of ray from one x or y-side to next x or y-side
        // deltaDistX = |1 / rayDirX|, deltaDistY = |1 / rayDirY|
        fixed_t deltaDistX = (rayDirX == 0) ? FIXED_LARGE : fixed_abs(fixed_recip_large(rayDirX));
        fixed_t deltaDistY = (rayDirY == 0) ? FIXED_LARGE : fixed_abs(fixed_recip_large(rayDirY));
        fixed_t perpWallDist;

        // What direction to step in x or y direction
        int stepX;
        int stepY;

        int hit = 0;   // Was there a wall hit?
        int sideHit;   // Was a NS or EW wall hit?

        // Calculate step and initial sideDist
        // posX fractional part: cam->posX & (FIXED_ONE - 1)
        fixed_t posXfrac = FIXED_FRAC(cam->posX);
        fixed_t posYfrac = FIXED_FRAC(cam->posY);

        if (rayDirX < 0) {
            stepX = -1;
            sideDistX = fixed_mul(posXfrac, deltaDistX);
        } else {
            stepX = 1;
            sideDistX = fixed_mul(FIXED_ONE - posXfrac, deltaDistX);
        }
        if (rayDirY < 0) {
            stepY = -1;
            sideDistY = fixed_mul(posYfrac, deltaDistY);
        } else {
            stepY = 1;
            sideDistY = fixed_mul(FIXED_ONE - posYfrac, deltaDistY);
        }

        // Perform DDA with bounds checking
        int maxSteps = MAP_WIDTH + MAP_HEIGHT;  // Prevent infinite loops
        while (hit == 0 && maxSteps > 0) {
            maxSteps--;

            // Jump to next map square in x or y direction
            if (sideDistX < sideDistY) {
                sideDistX += deltaDistX;
                mapX += stepX;
                sideHit = 0;
            } else {
                sideDistY += deltaDistY;
                mapY += stepY;
                sideHit = 1;
            }

            // Bounds check to prevent out-of-bounds access
            if (mapX < 0 || mapX >= MAP_WIDTH || mapY < 0 || mapY >= MAP_HEIGHT) {
                hit = -1;  // Mark as boundary hit (no valid wall)
                break;
            }

            // Check if ray hit a wall (row-major: Y=row, X=col)
            if (worldMap[mapY][mapX] > 0) hit = 1;
        }

        // Skip this column if ray escaped or hit boundary
        if (maxSteps <= 0 || hit != 1) continue;

        // Calculate distance from wall to camera plane
        if (sideHit == 0)
            perpWallDist = sideDistX - deltaDistX;
        else
            perpWallDist = sideDistY - deltaDistY;

        // Clamp to avoid division by zero or very large values
        if (perpWallDist < 256) perpWallDist = 256;  // Min ~0.004

        ZBuffer[x] = perpWallDist;

        // Calculate height of line to draw on screen
        // lineHeight = SCREEN_HEIGHT / perpWallDist (using precomputed constant)
        int lineHeight = (int)(SCREEN_HEIGHT_SHIFTED / perpWallDist);

        // Calculate lowest and highest pixel to fill (use precomputed half-height)
        int halfLineHeight = lineHeight >> 1;  // Faster than / 2
        int drawStart = HALF_SCREEN_HEIGHT - halfLineHeight;
        if (drawStart < 0) drawStart = 0;
        int drawEnd = HALF_SCREEN_HEIGHT + halfLineHeight;
        if (drawEnd > SCREEN_HEIGHT) drawEnd = SCREEN_HEIGHT;

        int texNum = (worldMap[mapY][mapX] - 1) % NUM_TEXTURES;
        int texRes = textures[texNum].resolution;
        int texResMask = textures[texNum].mask;  // Use precomputed mask

        // Calculate where exactly the wall was hit (fixed-point)
        fixed_t wallX;
        if (sideHit == 0)
            wallX = cam->posY + fixed_mul(perpWallDist, rayDirY);
        else
            wallX = cam->posX + fixed_mul(perpWallDist, rayDirX);
        wallX = FIXED_FRAC(wallX);  // Get fractional part

        // Convert to texture X coordinate
        int texX = (wallX * texRes) >> FIXED_SHIFT;
        if (sideHit == 0 && rayDirX > 0) texX = texRes - texX - 1;
        if (sideHit == 1 && rayDirY < 0) texX = texRes - texX - 1;
        if (texX < 0) texX = 0;
        if (texX >= texRes) texX = texRes - 1;

        // Calculate texture step per screen pixel (fixed-point)
        // step = texRes / lineHeight - use reciprocal multiplication
        fixed_t texStep;
        if (lineHeight > 0) {
            // texStep = (texRes << 16) / lineHeight
            // Rewritten as: texRes * (65536 / lineHeight) = texRes * recip(lineHeight)
            fixed_t recipLineHeight = fixed_recip_large(lineHeight << FIXED_SHIFT);
            texStep = (fixed_t)texRes * recipLineHeight;
        } else {
            texStep = 0;
        }

        // Starting texture coordinate (use cached halfLineHeight)
        // texPos = (drawStart - HALF_SCREEN_HEIGHT + halfLineHeight) * step
        fixed_t texPos = ((drawStart - HALF_SCREEN_HEIGHT + halfLineHeight) * texStep);

        // Cache texture data pointer for this wall's texture
        const uint16_t* texData = textures[texNum].data;

        // Branchless shading: precompute mask/shift to avoid per-pixel conditional
        uint16_t shadeMask = (sideHit == 1) ? 0x7BEF : 0xFFFF;
        int shadeShift = (sideHit == 1) ? 1 : 0;

        // Texture rendering loop
        // Convert screen x to buffer-local coordinate
        int bufferX = x - startX;
        for (int y = drawStart; y < drawEnd; y++) {
            int texY = texResMask - ((texPos >> FIXED_SHIFT) & texResMask);
            texPos += texStep;

            uint16_t color = texData[texY * texRes + texX];
            color = (color >> shadeShift) & shadeMask;

            setPixelBuffer(bufferX, y, color);
        }
    }
}

// Clear Z-buffer to maximum depth (sprites behind everything)
static void clearZBuffer(void) {
    for (int i = 0; i < SCREEN_WIDTH; i++) {
        ZBuffer[i] = FIXED_LARGE;  // Max distance = infinitely far
    }
}

// Temporary: force 10µs gap between profiling pulses for visibility
#define PROFILE_GAP() Clock_Delay(320)  // 320 cycles @ 32MHz = 10µs

void RenderScene(void) {
    // No wait here - double-buffering means Q0 renders to a different buffer
    // than Q3's DMA is reading. The wait inside the loop handles sync.

    FPSCounter_Update();

    // Clear Z-buffer once per frame (shared between all quarters)
    clearZBuffer();

    // Render all 4 quarters
    for (int side = 0; side < 4; side++) {
        clearRenderBuffer();
        GPIOB->DOUTSET31_0 = RED;
        CastRays(side);
        GPIOB->DOUTCLR31_0 = RED;
        PROFILE_GAP();

        GPIOB->DOUTSET31_0 = RED;
        RenderSprites(side);
        GPIOB->DOUTCLR31_0 = RED;
        PROFILE_GAP();

        GPIOB->DOUTSET31_0 = RED;
        drawFGSpriteQueue(side);
        drawTextQueue(side);
        drawFPSOverlay(side);
        GPIOB->DOUTCLR31_0 = RED;
        PROFILE_GAP();

        // Transfer to display via DMA (async)
        RenderBuffer_WaitComplete();
        RenderBufferDMA(side, 0);
    }

    // Clear queues after all 4 sides rendered
    textQueueCount = 0;
    fgSpriteQueueCount = 0;
}

void Graphics_Init(void) {
    Clock_Init80MHz(0); // We want a fast clock
    Fixed_Init();
    Buffer_Init();
    ST7735_DMA_Init();  // Initialize DMA for async display transfers
}

void Graphics_SetFloorColor(uint16_t color) {
    Buffer_SetFloorColor(color);
}

void Graphics_SetSkyColor(uint16_t color) {
    Buffer_SetSkyColor(color);
}

void Graphics_SetFloorGradient(double intensity) {
    Buffer_SetFloorGradient(intensity);
}

static void drawFPSOverlay(int side) {
    if (!fpsEnabled) return;

    // Get current FPS and format as string
    uint32_t fps = FPSCounter_Get();
    char fpsStr[12];

    fpsStr[0] = 'F';
    fpsStr[1] = 'P';
    fpsStr[2] = 'S';
    fpsStr[3] = ':';
    fpsStr[4] = ' ';

    if (fps >= 100) {
        fpsStr[5] = '0' + (fps / 100);
        fpsStr[6] = '0' + ((fps / 10) % 10);
        fpsStr[7] = '0' + (fps % 10);
        fpsStr[8] = '\0';
    } else if (fps >= 10) {
        fpsStr[5] = '0' + (fps / 10);
        fpsStr[6] = '0' + (fps % 10);
        fpsStr[7] = '\0';
    } else {
        fpsStr[5] = '0' + fps;
        fpsStr[6] = '\0';
    }

    printToBuffer(fpsStr, fpsX, fpsY, fpsColor, side);
}

void Graphics_DisplayFPS(int x, int y, uint16_t color) {
    FPSCounter_Init();
    fpsEnabled = 1;
    fpsX = x;
    fpsY = y;
    fpsColor = color;
}

void Graphics_DisableFPS(void) {
    fpsEnabled = 0;
}

static void drawTextQueue(int side) {
    for (int i = 0; i < textQueueCount; i++) {
        printToBuffer(textQueue[i].text, textQueue[i].x, textQueue[i].y, textQueue[i].color, side);
    }
}

static void drawFGSpriteQueue(int side) {
    for (int i = 0; i < fgSpriteQueueCount; i++) {
        Sprite sprite;
        sprite.x = fgSpriteQueue[i].x;
        sprite.y = fgSpriteQueue[i].y;
        sprite.image = fgSpriteQueue[i].image;
        sprite.width = fgSpriteQueue[i].width;
        sprite.height = fgSpriteQueue[i].height;
        sprite.scale = fgSpriteQueue[i].scale;
        sprite.transparent = fgSpriteQueue[i].transparent;
        drawForegroundSpriteToBuffer(side, sprite);
    }
}

void Graphics_Text(const char* text, int x, int y, uint16_t color) {
    if (textQueueCount >= MAX_TEXT_QUEUE) return;

    // Copy text (truncate if too long)
    int i;
    for (i = 0; i < MAX_TEXT_LENGTH - 1 && text[i] != '\0'; i++) {
        textQueue[textQueueCount].text[i] = text[i];
    }
    textQueue[textQueueCount].text[i] = '\0';

    textQueue[textQueueCount].x = x;
    textQueue[textQueueCount].y = y;
    textQueue[textQueueCount].color = color;
    textQueueCount++;
}

void Graphics_ForegroundSprite(const uint16_t* image, int x, int y, int width, int height, int scale, uint16_t transparent) {
    if (fgSpriteQueueCount >= MAX_FG_SPRITE_QUEUE) return;

    fgSpriteQueue[fgSpriteQueueCount].image = image;
    fgSpriteQueue[fgSpriteQueueCount].x = x;
    fgSpriteQueue[fgSpriteQueueCount].y = y;
    fgSpriteQueue[fgSpriteQueueCount].width = width;
    fgSpriteQueue[fgSpriteQueueCount].height = height;
    fgSpriteQueue[fgSpriteQueueCount].scale = scale;
    fgSpriteQueue[fgSpriteQueueCount].transparent = transparent;
    fgSpriteQueueCount++;
}
