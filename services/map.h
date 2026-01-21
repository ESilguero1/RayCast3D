/* map.h
 * RayCast3D Map Management Module
 * World map loading and access functions
 *
 * Author: Elijah Silguero
 * Created: December 2025
 * Modified: January 2026
 * Hardware: MSPM0G3507 with ST7735 LCD
 *
 * Manages the 2D grid map used for raycasting walls.
 * Map values represent wall texture indices (0 = empty).
 */

#ifndef MAP_H_SERVICE_
#define MAP_H_SERVICE_

#include <stdint.h>
#include "../utils/fixed.h"

/*---------------------------------------------------------------------------
 * Constants
 *---------------------------------------------------------------------------*/

/* Map dimensions in tiles */
#define MAP_WIDTH 24
#define MAP_HEIGHT 24

/*---------------------------------------------------------------------------
 * Public Variables
 *---------------------------------------------------------------------------*/

/* World map array - Row-major: [row/Y][column/X]
 * Values: 0 = empty, 1+ = wall texture index */
extern uint8_t Map_WorldMap[MAP_HEIGHT][MAP_WIDTH];

/*---------------------------------------------------------------------------
 * Map Loading Functions
 *---------------------------------------------------------------------------*/

/* Load a map from a constant array
 * Inputs: map - 2D array of tile values */
void Map_Load(const uint8_t map[MAP_HEIGHT][MAP_WIDTH]);

/* Load a map from an array of maps by index
 * Inputs: maps - array of map pointers
 *         index - which map to load */
void Map_LoadFromList(const uint8_t (*const maps[])[MAP_WIDTH], int index);

/*---------------------------------------------------------------------------
 * Map Access Functions
 *---------------------------------------------------------------------------*/

/* Get tile value at a world position (floating-point)
 * Inputs: x, y - world coordinates
 * Returns: tile value at that position */
uint8_t Map_GetValue(double x, double y);

/* Get tile value at a world position (fixed-point)
 * Inputs: x, y - world coordinates in Q16.16 format
 * Returns: tile value at that position */
uint8_t Map_GetValueFixed(fixed_t x, fixed_t y);

#endif /* MAP_H_SERVICE_ */
