#ifndef GRAPHICS_H_
#define GRAPHICS_H_

#include <stdint.h>
#include "../drivers/ST7735.h"

// Map dimensions
#define MAP_WIDTH 24
#define MAP_HEIGHT 24

// Screen dimensions
#define SCREEN_WIDTH 160
#define SCREEN_HEIGHT 128
#define BUFFER_WIDTH (SCREEN_WIDTH / 2)
#define BUFFER_HEIGHT SCREEN_HEIGHT

// Camera state structure (owned by library)
typedef struct {
    double posX;
    double posY;
    double dirX;
    double dirY;
    double planeX;
    double planeY;
} Camera;

// World map and depth buffer
extern uint8_t worldMap[MAP_WIDTH][MAP_HEIGHT];
extern double ZBuffer[SCREEN_WIDTH];

// Core functions
void Graphics_Init(void);
void Graphics_SetFloorColor(uint16_t color);
void Graphics_SetSkyColor(uint16_t color);
void Graphics_SetFloorGradient(double intensity);
void RenderScene(void);
void FillMap(const uint8_t map[MAP_WIDTH][MAP_HEIGHT]);
void CastRays(int side);

// Camera control functions
void Camera_SetPosition(double x, double y);
void Camera_Move(double forward, double strafe);
void Camera_Rotate(double degrees);
const Camera* Camera_Get(void);

// FPS display - enables/disables FPS overlay on screen
void Graphics_DisplayFPS(int x, int y, uint16_t color);
void Graphics_DisableFPS(void);

// Per-frame text rendering (call before RenderScene, cleared after render)
void Graphics_Text(const char* text, int x, int y, uint16_t color);

// Per-frame foreground sprite rendering (call before RenderScene, cleared after render)
void Graphics_ForegroundSprite(const uint16_t* image, int x, int y, int width, int height, int scale, uint16_t transparent);

#endif /* GRAPHICS_H_ */