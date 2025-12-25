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
extern uint8_t worldMap[MAP_WIDTH][MAP_HEIGHT];

// Map loading functions
void FillMap(const uint8_t map[MAP_WIDTH][MAP_HEIGHT]);
void FillMapFromList(const uint8_t (*const maps[])[MAP_HEIGHT], int index);

// Map helper function - tells caller what is stored at map location
uint8_t getMapVal(double x, double y);

#endif /* MAP_H_SERVICE_ */
