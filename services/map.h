/* map.h
 * Map loading and management functions
 */

#ifndef MAP_H_SERVICE_
#define MAP_H_SERVICE_

#include <stdint.h>

// Map dimensions
#define MAP_WIDTH 24
#define MAP_HEIGHT 24

// World map (extern declaration - defined in map.c)
// Row-major: first index = row (Y), second index = column (X)
extern uint8_t worldMap[MAP_HEIGHT][MAP_WIDTH];

// Map loading functions
void FillMap(const uint8_t map[MAP_HEIGHT][MAP_WIDTH]);
void FillMapFromList(const uint8_t (*const maps[])[MAP_WIDTH], int index);

// Map helper function - tells caller what is stored at map location
uint8_t getMapVal(double x, double y);

#endif /* MAP_H_SERVICE_ */
