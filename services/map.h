/**
 * @file      map.h
 * @brief     RayCast3D Map Management Module - World map loading and access
 *
 * @author    Elijah Silguero
 * @date      December 2025
 *
 * Manages the 2D grid map used for raycasting walls.
 * Map values represent wall texture indices (0 = empty).
 */

/**
 * @defgroup Map Map
 * @brief World map loading and tile access.
 *
 * The Map module stores and provides access to the 24x24 tile grid
 * used by the raycaster. Each cell holds a wall texture index (0 means
 * empty space, 1+ selects a texture from textures.h). Maps are created
 * in RayCast3D Studio and exported to maps.h as constant arrays.
 *
 * Use Map_Load() or Map_LoadFromList() to copy a map into the active
 * world grid, and Map_GetValue() / Map_GetValueFixed() to query tile
 * values at runtime (e.g., for collision detection).
 *
 * @{
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
 * Types
 *---------------------------------------------------------------------------*/

/**
 * @brief Complete map descriptor exported by RayCast3D Studio.
 *
 * Bundles the tile grid with per-map floor and ceiling texture settings.
 * Wall textures are encoded per-cell in the grid (0 = empty, 1+ = texture).
 * Floor/ceiling textures use the same convention: 0 = disabled (gradient
 * floor / solid sky), 1+ = texture index into textures[] (1-based).
 */
typedef struct {
    const uint8_t (*grid)[MAP_WIDTH]; /**< Pointer to 24x24 tile grid */
    int8_t floorTexture;              /**< 0 = gradient, 1+ = textures[value-1] */
    int8_t ceilingTexture;            /**< 0 = solid sky, 1+ = textures[value-1] */
} MapInfo;

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
 * @brief Load a map from a Studio-exported MapInfo descriptor.
 *
 * Copies the tile grid into the active world and applies floor/ceiling
 * texture settings. Use the map descriptors exported by RayCast3D Studio
 * in maps.h (e.g., @c map1, @c map2).
 *
 * @par Example
 * @code
 * // Load a map by name (from maps.h)
 * Map_Load(&map1);
 *
 * // Or load by index from the map list
 * Map_LoadFromList(mapList, 0);  // equivalent to Map_Load(&mapList[0])
 * @endcode
 *
 * @param map  Pointer to a MapInfo descriptor
 */
void Map_Load(const MapInfo* map);

/**
 * @brief Load a map by index from the Studio-generated map list.
 *
 * Equivalent to @c Map_Load(&maps[index]).
 *
 * @param maps   Array of MapInfo descriptors (e.g., @c mapList from maps.h)
 * @param index  Zero-based index of the map to load
 */
void Map_LoadFromList(const MapInfo maps[], int index);

/*---------------------------------------------------------------------------
 * Map Access Functions
 *---------------------------------------------------------------------------*/

/**
 * @brief Get the tile value at a world position (floating-point).
 *
 * Truncates the coordinates to integer tile indices and returns the
 * value stored in the world grid. Useful for collision detection:
 * a return value of 0 means open space; any non-zero value means a wall.
 *
 * @param x  World X coordinate (column)
 * @param y  World Y coordinate (row)
 * @return Tile value (0 = empty, 1+ = wall texture index)
 */
uint8_t Map_GetValue(double x, double y);

/**
 * @brief Get the tile value at a world position (fixed-point).
 *
 * Same as Map_GetValue() but accepts Q16.16 fixed-point coordinates,
 * avoiding a float-to-fixed conversion in performance-critical code
 * paths such as the raycaster inner loop.
 *
 * @param x  World X coordinate in Q16.16 format
 * @param y  World Y coordinate in Q16.16 format
 * @return Tile value (0 = empty, 1+ = wall texture index)
 */
uint8_t Map_GetValueFixed(fixed_t x, fixed_t y);

#endif /* MAP_H_SERVICE_ */
