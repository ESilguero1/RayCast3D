/* map.c
 * Map loading and management functions
 */

#include "map.h"

// World map (owned by this module)
uint8_t worldMap[MAP_WIDTH][MAP_HEIGHT];

void FillMap(const uint8_t map[MAP_WIDTH][MAP_HEIGHT]) {
    for (int i = 0; i < MAP_WIDTH; i++) {
        for (int j = 0; j < MAP_HEIGHT; j++) {
            worldMap[i][j] = map[i][j];
        }
    }
}

void FillMapFromList(const uint8_t (*const maps[])[MAP_HEIGHT], int index) {
    const uint8_t (*map)[MAP_HEIGHT] = maps[index];
    for (int i = 0; i < MAP_WIDTH; i++) {
        for (int j = 0; j < MAP_HEIGHT; j++) {
            worldMap[i][j] = map[i][j];
        }
    }
}
