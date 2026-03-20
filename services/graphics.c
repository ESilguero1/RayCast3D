/* graphics.c
 * RayCast3D Graphics Library
 * Core raycasting and rendering functions
 *
 * Author: Elijah Silguero (with contributions from Surya Balaji)
 * Created: December 2025
 * Modified: January 2026
 * Hardware: MSPM0G3507 with ST7735 LCD
 *
 * This module implements the DDA raycasting algorithm using
 * Q16.16 fixed-point math for embedded performance.
 */

#include <stdint.h>
#include "graphics.h"
#include "sprites.h"
#include "../hal/buffer.h"
#include "../drivers/ST7735_DMA.h"
#include "../assets/textures.h"
#include "../utils/fixed.h"
#include "../utils/fpscounter.h"

// Z-buffer for depth sorting (fixed-point Q16.16)
fixed_t ZBuffer[SCREEN_WIDTH];

// Floor texture state (-1 = disabled, 0+ = texture index)
static int floorTexIndex = -1;
static const uint16_t* floorTexData = 0;
static int floorTexRes = 0;
static int floorTexMask = 0;

// Ceiling texture state (-1 = disabled, 0+ = texture index)
static int ceilTexIndex = -1;
static const uint16_t* ceilTexData = 0;
static int ceilTexRes = 0;
static int ceilTexMask = 0;

// Precomputed row distance LUT for floorcasting
// rowDistanceLUT[p] = HALF_SCREEN_HEIGHT / p in Q16.16
// p = distance below horizon in screen rows (1 = near horizon, 64 = screen bottom)
static fixed_t rowDistanceLUT[HALF_SCREEN_HEIGHT + 1];
static int floorLUTInitialized = 0;

static void initRowDistanceLUT(void) {
    if (floorLUTInitialized) return;
    rowDistanceLUT[0] = FIXED_LARGE;
    for (int p = 1; p <= HALF_SCREEN_HEIGHT; p++) {
        rowDistanceLUT[p] = Fixed_Div(INT_TO_FIXED(HALF_SCREEN_HEIGHT), INT_TO_FIXED(p));
    }
    floorLUTInitialized = 1;
}

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

// Per-column wall coverage (written by CastRays, read by CastFloors)
// drawStart = bottom edge of wall (floor visible below), drawEnd = top edge (ceiling visible above)
static uint8_t columnDrawStart[BUFFER_WIDTH];
static uint8_t columnDrawEnd[BUFFER_WIDTH];

// Row-level bounds for fast-path / checked-path split in CastFloors
// minDrawStart: below this row ALL floor pixels are visible (no per-pixel check needed)
// maxDrawStart: at or above this row NO floor pixels are visible (stop the loop)
// minDrawEnd:   below this row NO ceiling pixels are visible (start the loop here)
// maxDrawEnd:   at or above this row ALL ceiling pixels are visible (no check needed)
static uint8_t minDrawStart;
static uint8_t maxDrawStart;
static uint8_t minDrawEnd;
static uint8_t maxDrawEnd;

// Forward declarations
static void drawFPSOverlay(int side);
static void drawTextQueue(int side);
static void drawFGSpriteQueue(int side);

void CastRays(int side) {
    const Camera* cam = Camera_Get();

    // Quarter-screen: side 0-3, each covers BUFFER_WIDTH (40) columns
    int startX = side * BUFFER_WIDTH;
    int endX = startX + BUFFER_WIDTH;

    // Initialize wall coverage: no wall = floor/ceiling fill everything
    for (int i = 0; i < BUFFER_WIDTH; i++) {
        columnDrawStart[i] = HALF_SCREEN_HEIGHT;
        columnDrawEnd[i] = HALF_SCREEN_HEIGHT;
    }
    minDrawStart = HALF_SCREEN_HEIGHT;
    maxDrawStart = HALF_SCREEN_HEIGHT;
    minDrawEnd = HALF_SCREEN_HEIGHT;
    maxDrawEnd = HALF_SCREEN_HEIGHT;

    const fixed_t cameraX_step = (2 * FIXED_ONE) / SCREEN_WIDTH;

    for (int x = startX; x < endX; x++) {
        // Calculate ray position and direction (all fixed-point)
        fixed_t cameraX = (x * cameraX_step) - FIXED_ONE;  // Range: -1 to +1

        fixed_t rayDirX = cam->dirX + Fixed_Mul(cam->planeX, cameraX);
        fixed_t rayDirY = cam->dirY + Fixed_Mul(cam->planeY, cameraX);

        // Which box of the map we're in
        int mapX = FIXED_TO_INT(cam->posX);
        int mapY = FIXED_TO_INT(cam->posY);

        // Length of ray from current position to next x or y-side
        fixed_t sideDistX;
        fixed_t sideDistY;

        // Length of ray from one x or y-side to next x or y-side
        // deltaDistX = |1 / rayDirX|, deltaDistY = |1 / rayDirY|
        fixed_t deltaDistX = (rayDirX == 0) ? FIXED_LARGE : Fixed_Abs(Fixed_RecipLarge(rayDirX));
        fixed_t deltaDistY = (rayDirY == 0) ? FIXED_LARGE : Fixed_Abs(Fixed_RecipLarge(rayDirY));
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
            sideDistX = Fixed_Mul(posXfrac, deltaDistX);
        } else {
            stepX = 1;
            sideDistX = Fixed_Mul(FIXED_ONE - posXfrac, deltaDistX);
        }
        if (rayDirY < 0) {
            stepY = -1;
            sideDistY = Fixed_Mul(posYfrac, deltaDistY);
        } else {
            stepY = 1;
            sideDistY = Fixed_Mul(FIXED_ONE - posYfrac, deltaDistY);
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
            if (Map_WorldMap[mapY][mapX] > 0) hit = 1;
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

        // Store wall coverage for CastFloors visibility culling
        int bufIdx = x - startX;
        columnDrawStart[bufIdx] = (uint8_t)drawStart;
        columnDrawEnd[bufIdx] = (uint8_t)drawEnd;
        if (drawStart < minDrawStart) minDrawStart = drawStart;
        if (drawStart > maxDrawStart) maxDrawStart = drawStart;
        if (drawEnd < minDrawEnd) minDrawEnd = drawEnd;
        if (drawEnd > maxDrawEnd) maxDrawEnd = drawEnd;

        int texNum = (Map_WorldMap[mapY][mapX] - 1) % NUM_TEXTURES;
        int texRes = textures[texNum].resolution;
        int texResMask = textures[texNum].mask;  // Use precomputed mask

        // Calculate where exactly the wall was hit (fixed-point)
        fixed_t wallX;
        if (sideHit == 0)
            wallX = cam->posY + Fixed_Mul(perpWallDist, rayDirY);
        else
            wallX = cam->posX + Fixed_Mul(perpWallDist, rayDirX);
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
            fixed_t recipLineHeight = Fixed_RecipLarge(lineHeight << FIXED_SHIFT);
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

            Buffer_SetPixel(bufferX, y, color);
        }
    }
}


void CastFloors(int side) {
    if (floorTexIndex < 0 && ceilTexIndex < 0) return;

    const Camera* cam = Camera_Get();
    int startX = side * BUFFER_WIDTH;

    // Ray direction at leftmost column (x=0)
    fixed_t rayDirX0 = cam->dirX - cam->planeX;
    fixed_t rayDirY0 = cam->dirY - cam->planeY;

    // Precompute step scale: 2*plane / SCREEN_WIDTH (constant for all rows)
    fixed_t scaledPlaneX = (cam->planeX * 2) / SCREEN_WIDTH;
    fixed_t scaledPlaneY = (cam->planeY * 2) / SCREEN_WIDTH;

    // Floor: y = 0 (screen bottom) to maxDrawStart-1 (no floor visible above this)
    // Two paths: branchless for rows fully visible, per-pixel check near wall edges
    if (floorTexIndex >= 0 && floorTexData) {
        int floorEnd = maxDrawStart < HALF_SCREEN_HEIGHT ? maxDrawStart : HALF_SCREEN_HEIGHT;

        for (int y = 0; y < floorEnd; y++) {
            int p = HALF_SCREEN_HEIGHT - y;
            fixed_t rowDist = rowDistanceLUT[p];

            fixed_t floorStepX = Fixed_Mul(rowDist, scaledPlaneX);
            fixed_t floorStepY = Fixed_Mul(rowDist, scaledPlaneY);

            fixed_t floorX = cam->posX + Fixed_Mul(rowDist, rayDirX0) + floorStepX * startX;
            fixed_t floorY = cam->posY + Fixed_Mul(rowDist, rayDirY0) + floorStepY * startX;

            if (y < minDrawStart) {
                // Fast path: all columns visible, no per-pixel check
                for (int x = 0; x < BUFFER_WIDTH; x++) {
                    int tx = (FIXED_FRAC(floorX) * floorTexRes) >> FIXED_SHIFT;
                    int ty = (FIXED_FRAC(floorY) * floorTexRes) >> FIXED_SHIFT;
                    Buffer_SetPixelFast(x, y, floorTexData[ty * floorTexRes + tx]);
                    floorX += floorStepX;
                    floorY += floorStepY;
                }
            } else {
                // Checked path: some columns covered by walls
                for (int x = 0; x < BUFFER_WIDTH; x++) {
                    if (y < columnDrawStart[x]) {
                        int tx = (FIXED_FRAC(floorX) * floorTexRes) >> FIXED_SHIFT;
                        int ty = (FIXED_FRAC(floorY) * floorTexRes) >> FIXED_SHIFT;
                        Buffer_SetPixelFast(x, y, floorTexData[ty * floorTexRes + tx]);
                    }
                    floorX += floorStepX;
                    floorY += floorStepY;
                }
            }
        }
    }

    // Ceiling: y = minDrawEnd (no ceiling visible below this) to SCREEN_HEIGHT-1
    // Two paths: per-pixel check near wall edges, branchless for rows fully visible
    if (ceilTexIndex >= 0 && ceilTexData) {
        int ceilStart = minDrawEnd > HALF_SCREEN_HEIGHT ? minDrawEnd : HALF_SCREEN_HEIGHT;

        for (int y = ceilStart; y < SCREEN_HEIGHT; y++) {
            int p = y - HALF_SCREEN_HEIGHT + 1;
            fixed_t rowDist = rowDistanceLUT[p];

            fixed_t ceilStepX = Fixed_Mul(rowDist, scaledPlaneX);
            fixed_t ceilStepY = Fixed_Mul(rowDist, scaledPlaneY);

            fixed_t ceilX = cam->posX + Fixed_Mul(rowDist, rayDirX0) + ceilStepX * startX;
            fixed_t ceilY = cam->posY + Fixed_Mul(rowDist, rayDirY0) + ceilStepY * startX;

            if (y >= maxDrawEnd) {
                // Fast path: all columns visible, no per-pixel check
                for (int x = 0; x < BUFFER_WIDTH; x++) {
                    int tx = (FIXED_FRAC(ceilX) * ceilTexRes) >> FIXED_SHIFT;
                    int ty = (FIXED_FRAC(ceilY) * ceilTexRes) >> FIXED_SHIFT;
                    Buffer_SetPixelFast(x, y, ceilTexData[ty * ceilTexRes + tx]);
                    ceilX += ceilStepX;
                    ceilY += ceilStepY;
                }
            } else {
                // Checked path: some columns covered by walls
                for (int x = 0; x < BUFFER_WIDTH; x++) {
                    if (y >= columnDrawEnd[x]) {
                        int tx = (FIXED_FRAC(ceilX) * ceilTexRes) >> FIXED_SHIFT;
                        int ty = (FIXED_FRAC(ceilY) * ceilTexRes) >> FIXED_SHIFT;
                        Buffer_SetPixelFast(x, y, ceilTexData[ty * ceilTexRes + tx]);
                    }
                    ceilX += ceilStepX;
                    ceilY += ceilStepY;
                }
            }
        }
    }
}

void Graphics_Init(void) {
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

void Graphics_SetFloorTexture(int texIndex) {
    if (texIndex >= 0 && texIndex < NUM_TEXTURES) {
        initRowDistanceLUT();
        floorTexIndex = texIndex;
        floorTexData = textures[texIndex].data;
        floorTexRes = textures[texIndex].resolution;
        floorTexMask = textures[texIndex].mask;
        Buffer_SetFloorTextured(1);
    } else {
        floorTexIndex = -1;
        floorTexData = 0;
        Buffer_SetFloorTextured(0);
    }
}

void Graphics_SetCeilingTexture(int texIndex) {
    if (texIndex >= 0 && texIndex < NUM_TEXTURES) {
        initRowDistanceLUT();
        ceilTexIndex = texIndex;
        ceilTexData = textures[texIndex].data;
        ceilTexRes = textures[texIndex].resolution;
        ceilTexMask = textures[texIndex].mask;
        Buffer_SetCeilingTextured(1);
    } else {
        ceilTexIndex = -1;
        ceilTexData = 0;
        Buffer_SetCeilingTextured(0);
    }
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

    Buffer_PrintText(fpsStr, fpsX, fpsY, fpsColor, side);
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
        Buffer_PrintText(textQueue[i].text, textQueue[i].x, textQueue[i].y, textQueue[i].color, side);
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
        Buffer_DrawForegroundSprite(side, sprite);
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

void Graphics_RenderOverlays(int side) {
    drawFGSpriteQueue(side);
    drawTextQueue(side);
    drawFPSOverlay(side);
}

void Graphics_ClearOverlayQueues(void) {
    textQueueCount = 0;
    fgSpriteQueueCount = 0;
}
