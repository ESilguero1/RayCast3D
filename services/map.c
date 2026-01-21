/* map.c
 * RayCast3D Map Management Module
 * World map loading and access functions
 *
 * Author: Elijah Silguero
 * Created: December 2025
 * Modified: January 2026
 * Hardware: MSPM0G3507 with ST7735 LCD
 */

#include "map.h"

/*---------------------------------------------------------------------------
 * Public Variables
 *---------------------------------------------------------------------------*/

/* World map - Row-major: first index = row (Y), second index = column (X) */
uint8_t Map_WorldMap[MAP_HEIGHT][MAP_WIDTH];

/*---------------------------------------------------------------------------
 * Map Loading Functions
 *---------------------------------------------------------------------------*/

void Map_Load(const uint8_t map[MAP_HEIGHT][MAP_WIDTH]) {
    for (int row = 0; row < MAP_HEIGHT; row++) {
        for (int col = 0; col < MAP_WIDTH; col++) {
            Map_WorldMap[row][col] = map[row][col];
        }
    }
}

void Map_LoadFromList(const uint8_t (*const maps[])[MAP_WIDTH], int index) {
    const uint8_t (*map)[MAP_WIDTH] = maps[index];
    for (int row = 0; row < MAP_HEIGHT; row++) {
        for (int col = 0; col < MAP_WIDTH; col++) {
            Map_WorldMap[row][col] = map[row][col];
        }
    }
}

/*---------------------------------------------------------------------------
 * Map Access Functions
 *---------------------------------------------------------------------------*/

uint8_t Map_GetValue(double x, double y) {
    int xCoord = (int)x;
    int yCoord = (int)y;
    return Map_WorldMap[yCoord][xCoord];
}

uint8_t Map_GetValueFixed(fixed_t x, fixed_t y) {
    int xCoord = FIXED_TO_INT(x);
    int yCoord = FIXED_TO_INT(y);
    return Map_WorldMap[yCoord][xCoord];
}