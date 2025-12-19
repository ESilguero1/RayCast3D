/* graphics.c
 * RayCast3D Graphics Library
 * Core raycasting and rendering functions
 */

#include <stdint.h>
#include <math.h>
#include "graphics.h"
#include "sprites.h"
#include "../hal/buffer.h"
#include "../assets/textures.h"
#include "../utils/fastmath.h"
#include "../utils/fpscounter.h"

// World map
uint8_t worldMap[MAP_WIDTH][MAP_HEIGHT];

// Z-buffer for depth sorting
double ZBuffer[SCREEN_WIDTH];

// Camera state (owned by library)
static Camera camera = {
    .posX = 12.0,
    .posY = 12.0,
    .dirX = -1.0,
    .dirY = 0.0,
    .planeX = 0.0,
    .planeY = 0.66
};

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

void FillMap(const uint8_t map[MAP_WIDTH][MAP_HEIGHT]) {
    for (int i = 0; i < MAP_WIDTH; i++) {
        for (int j = 0; j < MAP_HEIGHT; j++) {
            worldMap[i][j] = map[i][j];
        }
    }
}

void CastRays(int side) {
    // Determine loop bounds
    int startX = (side == 0) ? 0 : SCREEN_WIDTH / 2;
    int endX = (side == 0) ? SCREEN_WIDTH / 2 : SCREEN_WIDTH;

    for (int x = startX; x < endX; x++) {
        // Calculate ray position and direction
        double cameraX = 2 * x / (double)SCREEN_WIDTH - 1;
        double rayDirX = camera.dirX + camera.planeX * cameraX;
        double rayDirY = camera.dirY + camera.planeY * cameraX;

        // Which box of the map we're in
        int mapX = (int)camera.posX;
        int mapY = (int)camera.posY;

        // Length of ray from current position to next x or y-side
        double sideDistX;
        double sideDistY;

        // Length of ray from one x or y-side to next x or y-side
        double deltaDistX = (rayDirX == 0) ? 1e30 : fabs(1 / rayDirX);
        double deltaDistY = (rayDirY == 0) ? 1e30 : fabs(1 / rayDirY);
        double perpWallDist;

        // What direction to step in x or y direction
        int stepX;
        int stepY;

        int hit = 0;   // Was there a wall hit?
        int sideHit;   // Was a NS or EW wall hit?

        // Calculate step and initial sideDist
        if (rayDirX < 0) {
            stepX = -1;
            sideDistX = (camera.posX - mapX) * deltaDistX;
        } else {
            stepX = 1;
            sideDistX = (mapX + 1.0 - camera.posX) * deltaDistX;
        }
        if (rayDirY < 0) {
            stepY = -1;
            sideDistY = (camera.posY - mapY) * deltaDistY;
        } else {
            stepY = 1;
            sideDistY = (mapY + 1.0 - camera.posY) * deltaDistY;
        }

        // Perform DDA
        while (hit == 0) {
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

            // Check if ray hit a wall
            if (worldMap[mapX][mapY] > 0) hit = 1;
        }

        // Calculate distance from wall to camera plane
        if (sideHit == 0)
            perpWallDist = (sideDistX - deltaDistX);
        else
            perpWallDist = (sideDistY - deltaDistY);
        ZBuffer[x] = perpWallDist;

        // Calculate height of line to draw on screen
        int lineHeight = (int)(SCREEN_HEIGHT / perpWallDist);

        // Calculate lowest and highest pixel to fill in current stripe
        int drawStart = -lineHeight / 2 + SCREEN_HEIGHT / 2;
        if (drawStart < 0) drawStart = 0;
        int drawEnd = lineHeight / 2 + SCREEN_HEIGHT / 2;
        if (drawEnd > SCREEN_HEIGHT) drawEnd = SCREEN_HEIGHT;

        int texNum = (worldMap[mapX][mapY] % 5) - 1; // Texture index based on map value (0-4)
        double wallX; // Where exactly the wall was hit
        if (sideHit == 0) wallX = camera.posY + perpWallDist * rayDirY;
        else              wallX = camera.posX + perpWallDist * rayDirX;
        wallX -= floor(wallX);

        int texX = (int)(wallX * (double)TEX_WIDTH);
        if (sideHit == 0 && rayDirX > 0) texX = TEX_WIDTH - texX - 1;
        if (sideHit == 1 && rayDirY < 0) texX = TEX_WIDTH - texX - 1;

        // Calculate how much to increase the texture coordinate per screen pixel
        double step = 1.0 * TEX_HEIGHT / lineHeight;
        // Starting texture coordinate
        double texPos = (drawStart - SCREEN_HEIGHT / 2.0 + lineHeight / 2.0) * step;

        for (int y = drawStart; y < drawEnd; y++) {
            // Integer texture coordinate
            int texY = (TEX_HEIGHT - 1) - ((int)texPos & (TEX_HEIGHT - 1)); // Flip texture vertically
            texPos += step;
            uint16_t color = textures[texNum][texY * TEX_WIDTH + texX];

            // Make color darker for y-sides
            if (sideHit == 1) { color = (color >> 1) & 0x7BEF; }

            setPixelBuffer(x, y, color);
        }
    }
}

void RenderScene(void) {
    FPSCounter_Update();
    // Render left half (side 0)
    clearRenderBuffer();
    CastRays(0);
    RenderSprites(0);
    drawFGSpriteQueue(0);
    drawTextQueue(0);
    drawFPSOverlay(0);
    RenderBuffer(0);

    // Render right half (side 1)
    clearRenderBuffer();
    CastRays(1);
    RenderSprites(1);
    drawFGSpriteQueue(1);
    drawTextQueue(1);
    drawFPSOverlay(1);
    RenderBuffer(1);

    // Clear queues after both sides rendered
    textQueueCount = 0;
    fgSpriteQueueCount = 0;
}

void Graphics_Init(void) {
    Buffer_Init();
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

// Camera control functions

void Camera_SetPosition(double x, double y) {
    camera.posX = x;
    camera.posY = y;
}

void Camera_Move(double forward, double strafe) {
    // Move forward/backward along direction vector
    double newX = camera.posX + camera.dirX * forward;
    double newY = camera.posY + camera.dirY * forward;

    // Strafe (move perpendicular to direction)
    newX += camera.planeX * strafe;
    newY += camera.planeY * strafe;

    // Simple collision detection - only move if not hitting a wall
    if (worldMap[(int)newX][(int)camera.posY] == 0) {
        camera.posX = newX;
    }
    if (worldMap[(int)camera.posX][(int)newY] == 0) {
        camera.posY = newY;
    }
}

void Camera_Rotate(double degrees) {
    double radians = degrees * DEG_TO_RAD;
    double cosA = fast_cos(radians);
    double sinA = fast_sin(radians);

    // Rotate direction vector
    double oldDirX = camera.dirX;
    camera.dirX = camera.dirX * cosA - camera.dirY * sinA;
    camera.dirY = oldDirX * sinA + camera.dirY * cosA;

    // Rotate camera plane (must rotate same amount to maintain FOV)
    double oldPlaneX = camera.planeX;
    camera.planeX = camera.planeX * cosA - camera.planeY * sinA;
    camera.planeY = oldPlaneX * sinA + camera.planeY * cosA;
}

const Camera* Camera_Get(void) {
    return &camera;
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
