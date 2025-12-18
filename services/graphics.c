/* main.c
 * Elijah Silguero
 * date
 */
 
#include <stdio.h>
 #include <stdint.h>
 #include <stdlib.h>
 #include <math.h>
#include "Inventory.h"
 #include "ti/devices/msp/msp.h"
 #include "ST7735_SDC.h"
 #include "../inc/SPI.h"
 #include "../inc/Clock.h"
 #include "../inc/Timer.h"
 #include "../inc/LaunchPad.h"
 #include "Graphics.h"
 #include "Sounds.h"
 #include "sprites.h"
 #include "Buffer.h"
 #include "Textures.h"
 #include "Input.h"
 #include "Sync.h"
 #include "integer.h"
#include "diskio.h"
#include "ff.h"

static FATFS g_sFatFs;
FIL Handle,Handle2;
FRESULT MountFresult;
FRESULT Fresult;
DRESULT Result;
DSTATUS InitStatus;
unsigned char buffer[512];
 
 uint8_t worldMap[MAP_WIDTH][MAP_HEIGHT];
 uint16_t miniMap[MAP_WIDTH * MAP_HEIGHT];
 
 void FillMap(const uint8_t map[MAP_WIDTH][MAP_HEIGHT]) {
  for (int i = MAP_WIDTH - 1; i >= 0; i--) {
   for (int j = 0; j < MAP_HEIGHT; j++) {
    worldMap[i][j] = map[i][j];
    int index = (MAP_WIDTH - 1 - i) * MAP_HEIGHT + j;
    miniMap[index] = (map[i][j] != 0) ? ST7735_WHITE : 0;
   }
  }
 }

extern uint8_t accuracyRad;
extern Inventory inventory;
extern uint8_t language; 

 double ZBuffer[SCREEN_WIDTH];
 
 void CastRays(int side) {
   //Determine loop bounds.
  int startX = (side == 0) ? 0 : SCREEN_WIDTH / 2;
  int endX = (side == 0) ? SCREEN_WIDTH / 2 : SCREEN_WIDTH;
 
  for (int x = startX; x < endX; x++) {
   // Calculate ray position and direction
   double cameraX = 2 * x / (double)SCREEN_WIDTH - 1;
   double rayDirX = self.dirX + self.planeX * cameraX;
   double rayDirY = self.dirY + self.planeY * cameraX;
 
   // Which box of the map we're in
   int mapX = (int)self.posX;
   int mapY = (int)self.posY;
 
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
   int sideHit;  // Was a NS or EW wall hit?
 
   // Calculate step and initial sideDist
   if (rayDirX < 0) {
    stepX = -1;
    sideDistX = (self.posX - mapX) * deltaDistX;
   } else {
    stepX = 1;
    sideDistX = (mapX + 1.0 - self.posX) * deltaDistX;
   }
   if (rayDirY < 0) {
    stepY = -1;
    sideDistY = (self.posY - mapY) * deltaDistY;
   } else {
    stepY = 1;
    sideDistY = (mapY + 1.0 - self.posY) * deltaDistY;
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
   if (drawEnd >= SCREEN_HEIGHT) drawEnd = SCREEN_HEIGHT - 1;
 
   int texNum = (worldMap[mapX][mapY] % 5) - 1; // Texture index based on map value (0-4)
    double wallX; // Where exactly the wall was hit
    if (sideHit == 0) wallX = self.posY + perpWallDist * rayDirY;
    else           wallX = self.posX + perpWallDist * rayDirX;
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

        // Make color darker for y-sides: R, G and B byte each divided through two with a "shift" and an "and"
        if (sideHit == 1) {color = (color >> 1) & 0x7BEF;}
        
        setPixelBuffer(x, y, color);
    }
  }
 }

 void RenderSky(){
    for (int i = 0; i < MAX_FALLING_BARS; i++) {
        uint8_t barX = rand() % BUFFER_WIDTH;
        uint8_t yStartOffset = rand() % (SCREEN_HEIGHT / 2); // Random start within the sky
        uint8_t length = 24 + i/2; // Random-ish length
        uint16_t color = MATRIX_GLOW_GREEN + ((rand()%100 - 50) << 5);

        uint8_t startY = SKY_HEIGHT_START + yStartOffset;
        uint8_t endY = startY + length;

        for (int y = startY; y < endY && y < SCREEN_HEIGHT; y++) {
            for (int xOffset = 0; xOffset < BAR_THICKNESS; xOffset++) {
                int currentX = barX + xOffset;
                if (currentX < BUFFER_WIDTH) {
                    setPixelBuffer(currentX, y, color);
                }
            }
        }
    }
 }

void DrawMinimap() {
    int minimapDestX = 0;
    int minimapDestY = SCREEN_HEIGHT - 24;

    blitBufferToRenderBuffer(miniMap, MAP_WIDTH, MAP_HEIGHT, minimapDestX, minimapDestY);

    // Draw player position on the minimap (remains the same)
    int playerMinimapY = (SCREEN_HEIGHT - 24) + ((MAP_HEIGHT - 1) - (int)self.posX);
    int playerMinimapX = (int)self.posY;

    if (playerMinimapY >= SCREEN_HEIGHT - 24 && playerMinimapY < SCREEN_HEIGHT && playerMinimapX >= 0 && playerMinimapX < 24) {
        setPixelBuffer(playerMinimapX, playerMinimapY, MATRIX_GREEN);
    }
}

static void DrawBar(int16_t x, int16_t y, uint8_t health) {
  uint16_t color = health >= 30 ? MATRIX_DARK_GREEN
                  : health >= 15 ? ST7735_YELLOW
                                 : ST7735_RED;
  for(int yy=y; yy<y+8; yy++){
    for(int xx=x; xx<x+50; xx++){
      if(xx < x + health) setPixelBuffer(xx, yy, color);
    }
  }
}

void DrawHealthBar(){
    int16_t barWidth = 50;

    DrawBar(SCREEN_WIDTH-50, SCREEN_HEIGHT-14, self.playerHealth);
    DrawBar(SCREEN_WIDTH-50, SCREEN_HEIGHT-26, other.playerHealth);


    // Labels
    printToBuffer("M0", SCREEN_WIDTH - barWidth - 16, (IS_DOMINANT_CONTROLLER) ? 18 : 6, ST7735_WHITE, 1);
    printToBuffer("Y", SCREEN_WIDTH - barWidth - 16, (IS_DOMINANT_CONTROLLER) ? 6 : 18, ST7735_WHITE, 1);
}

void DrawCrosshair(int side, uint16_t color) {
    int size      = Inventory_currentItem(&inventory)->crosshair_size;
    int spacing   = size / 6;
    int thickness = 2;
    int halfT     = thickness >> 1;
    int cx        = SCREEN_WIDTH  >> 1;
    int cy        = SCREEN_HEIGHT >> 1;

    // Vertical segments: [cy - size .. cy - spacing)  and  (cy + spacing+1 .. cy + size+1)
    int y0[2] = { cy - size,        cy + 1 + spacing };
    int y1[2] = { cy - spacing,    cy + 1 + size    };
    for (int seg = 0; seg < 2; seg++) {
        int ys = y0[seg], ye = y1[seg];
        if (side == 0) {
            // draw only one column instead of two to clip that extra pixel
            int xBase = cx - thickness + 1;  
            for (int y = ys; y < ye; y++) {
                setPixelBuffer(xBase, y, color);
            }
        } else {
            for (int y = ys; y < ye; y++) {
                for (int t = 0; t < thickness; t++) {
                    setPixelBuffer(t, y, color);
                }
            }
        }
    }

    // Horizontal bar: y in [cy - halfT .. cy + halfT]
    int yStart = cy - halfT, yEnd = cy + halfT;
    int xStart = (side == 0) ? (cx - size)      : (1 + spacing);
    int xEnd   = (side == 0) ? (cx - spacing)   : (size + 1);

    for (int y = yStart; y <= yEnd; y++) {
        for (int x = xStart; x < xEnd; x++) {
            setPixelBuffer(x, y, color);
        }
    }
}



void DrawHitIndicator(void){
  if (hitTimer == 0) return;
  hitTimer--;

  int W  = 40, H = 2;         // rectangle size
  int x, y;

  switch(hitDir){
    case HIT_FRONT:
      x = (SCREEN_WIDTH - W)/2; y = 0;
      break;
    case HIT_RIGHT:
      x = SCREEN_WIDTH - H;      y = (SCREEN_HEIGHT - W)/2;
      // swap W/H for orientation:
      { int tmp = W; /*W*/; /*H*/; W=H; H=tmp; }
      break;
    case HIT_BACK:
      x = (SCREEN_WIDTH - W)/2;  y = SCREEN_HEIGHT - H;
      break;
    case HIT_LEFT:
      x = 0;                      y = (SCREEN_HEIGHT - W)/2;
      { int tmp = W; W=H; H=tmp; }
      break;
  }
  // fast filled rectangle in ST7735:
  ST7735_FillRect(x, y, W, H, ST7735_RED);
}

const char* ammoText[] = {"Ammo", "Municion", "Plork"};

void printAmmo(int side) {
    char buffer[32];
    // Format the ammo string using sprintf
    sprintf(buffer, "%s:%d/%d", ammoText[language],Inventory_currentItem(&inventory)->ammo, Inventory_currentItem(&inventory)->tot_ammo);
    // display the ammo
    printToBuffer(buffer, 0, SCREEN_HEIGHT-24, (Inventory_currentItem(&inventory)->ammo == 0) ? ST7735_RED : ST7735_WHITE, side);
}

void printItem(int side){
    // Display item you're holding
    printToBuffer(Inventory_currentItem(&inventory)->name[language], 0, SCREEN_HEIGHT-32, ST7735_WHITE, side);
}

void printLeaderboard(int side){
    // Display leaderboard, showing kill count
    char buffer1[16];
    char buffer2[16];
    if (IS_DOMINANT_CONTROLLER){ // So the names are correct
        sprintf(buffer1, "%d Agent Y", self.kills);
        sprintf(buffer2,"%d Dr. M0", other.kills);
    }
    else{
        sprintf(buffer1, "%d Dr. M0", self.kills);
        sprintf(buffer2,"%d Agent Y", other.kills);
    }
    if (self.kills > other.kills){
        printToBuffer(buffer1, 0, 28, MATRIX_NEON_GREEN, side);
        printToBuffer(buffer2, 0, 36, ST7735_RED, side);   
    }
    else{
        printToBuffer(buffer2, 0, 28, ST7735_RED, side);
        printToBuffer(buffer1, 0, 36, MATRIX_NEON_GREEN, side);  
    }
}

 void RenderHUD(int side){
    uint16_t crosshair_color = (self.isOnTarget) ? ST7735_RED : ST7735_WHITE;
    DrawCrosshair(side, crosshair_color);
    if (side == 0){
        DrawMinimap();
        printItem(side);
        if (Item_isWeapon(Inventory_currentItem(&inventory)) && Inventory_currentItem(&inventory)->type != RAILGUN) printAmmo(side);
        printLeaderboard(side);
    }
    else{
        DrawHealthBar();
    }
    RenderForegroundSprites(side);
}

 
 void RenderScene(){
  static int side = 0;
  //Clear buffer
  clearRenderBuffer();
  // Render random falling bars in the sky
  RenderSky();
  //Draw background elements like walls to renderBuffer
  CastRays(side);
  RenderSprites(side);
  RenderHUD(side);
  RenderBuffer(side);
  DrawHitIndicator();
  side = !side;
 }

void Graphics_Init(void){
  SPI_Init();
  InitStatus = disk_initialize(0);
  MountFresult = f_mount(&g_sFatFs, "", 0);
  if(MountFresult){
    ST7735_DrawString(0, 2, "f_mount error", ST7735_Color565(0, 0, 255));
    while(1){};
  }
  ST7735_InitPrintf();  
  ST7735_SetRotation(1);
  PrecalculateFloorGradient();
}