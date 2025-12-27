/* map.c
 * Map loading and management functions
 */

#include "map.h"

// World map (owned by this module)
// Row-major: first index = row (Y), second index = column (X)
uint8_t worldMap[MAP_HEIGHT][MAP_WIDTH];

void FillMap(const uint8_t map[MAP_HEIGHT][MAP_WIDTH]) {
    for (int row = 0; row < MAP_HEIGHT; row++) {
        for (int col = 0; col < MAP_WIDTH; col++) {
            worldMap[row][col] = map[row][col];
        }
    }
}

void FillMapFromList(const uint8_t (*const maps[])[MAP_WIDTH], int index) {
    const uint8_t (*map)[MAP_WIDTH] = maps[index];
    for (int row = 0; row < MAP_HEIGHT; row++) {
        for (int col = 0; col < MAP_WIDTH; col++) {
            worldMap[row][col] = map[row][col];
        }
    }
}

uint8_t getMapVal(double x, double y){
    int x_coord = (int)x, y_coord = (int)y;
    return worldMap[y_coord][x_coord];
}