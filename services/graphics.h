#include <stdint.h>

#define MAP_WIDTH 24
#define MAP_HEIGHT 24
#define SCREEN_WIDTH 160
#define SCREEN_HEIGHT 128
#define BUFFER_WIDTH SCREEN_WIDTH / 2
#define BUFFER_HEIGHT SCREEN_HEIGHT
#define BACKGROUND_COLOR ST7735_BLACK

#define MATRIX_DARK_GREEN   0x0320  // Dark green, subtle glow
#define MATRIX_DARKER_GREEN 0x0150  // Even darker green
#define MATRIX_GREEN        0x07E0  // Standard bright green
#define MATRIX_NEON_GREEN   0x07F0  // Intense neon green
#define MATRIX_LIME_GREEN   0x07E6  // Almost white-green
#define MATRIX_EMERALD      0x03C0  // Deep emerald green
#define MATRIX_SOFT_GREEN   0x05A0  // Muted soft green
#define MATRIX_GLOW_GREEN   0x06E0  // Slight glow effect
#define MATRIX_HACKER_GREEN 0x04E0  // Classic "hacker" terminal green

#define SKY_HEIGHT_START (SCREEN_HEIGHT / 2)
#define MAX_FALLING_BARS 10
#define BAR_THICKNESS 2

void Graphics_Init();
void RenderScene();
void FillMap(const uint8_t map[MAP_WIDTH][MAP_HEIGHT]);