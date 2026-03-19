/**
 * @file      map.h
 * @brief     RayCast3D Map Management Module - World map loading and access
 *
 * @author    Elijah Silguero
 * @date      December 2025
 * @hardware  MSPM0G3507 with ST7735 LCD
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

/** Map width in tiles */
#define MAP_WIDTH 24
/** Map height in tiles */
#define MAP_HEIGHT 24

/*---------------------------------------------------------------------------
 * Public Variables
 *---------------------------------------------------------------------------*/

/** World map array - Row-major: [row/Y][column/X]
 *  Values: 0 = empty, 1+ = wall texture index */
extern uint8_t Map_WorldMap[MAP_HEIGHT][MAP_WIDTH];

/*---------------------------------------------------------------------------
 * Map Loading Functions
 *---------------------------------------------------------------------------*/

/**
 * @brief Load a map from a constant array
 * @param map  2D array of tile values
 */
void Map_Load(const uint8_t map[MAP_HEIGHT][MAP_WIDTH]);

/**
 * @brief Load a map from an array of maps by index
 * @param maps   Array of map pointers
 * @param index  Which map to load
 */
void Map_LoadFromList(const uint8_t (*const maps[])[MAP_WIDTH], int index);

/*---------------------------------------------------------------------------
 * Map Access Functions
 *---------------------------------------------------------------------------*/

/**
 * @brief Get tile value at a world position (floating-point)
 * @param x  World X coordinate
 * @param y  World Y coordinate
 * @return Tile value at that position (0 = empty, 1+ = wall texture index)
 */
uint8_t Map_GetValue(double x, double y);

/**
 * @brief Get tile value at a world position (fixed-point)
 * @param x  World X coordinate in Q16.16 format
 * @param y  World Y coordinate in Q16.16 format
 * @return Tile value at that position (0 = empty, 1+ = wall texture index)
 */
uint8_t Map_GetValueFixed(fixed_t x, fixed_t y);

#endif /* MAP_H_SERVICE_ */
