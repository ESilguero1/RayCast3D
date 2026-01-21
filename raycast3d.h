/* raycast3d.h
 * RayCast3D - Fixed-Point Raycasting Engine
 * Main header that includes all library components
 *
 * Author: Elijah Silguero
 * Created: December 2025
 * Modified: January 2026
 * Hardware: MSPM0G3507 with ST7735 LCD
 *
 * This library provides a complete raycasting engine optimized
 * for embedded systems using Q16.16 fixed-point math.
 *
 * Usage:
 *   1. Call RayCast3D_Init() once at startup
 *   2. Configure scene: Map_Load(), Camera_SetPosition(), etc.
 *   3. In main loop: RayCast3D_Render()
 */

#ifndef RAYCAST3D_H
#define RAYCAST3D_H

/*---------------------------------------------------------------------------
 * Engine API
 *---------------------------------------------------------------------------*/

/* Initialize the raycasting engine
 * Sets up: clock (80MHz), fixed-point math, display, DMA
 * Call once at startup before using any other functions */
void RayCast3D_Init(void);

/* Render one complete frame
 * Casts rays, renders sprites, draws overlays, transfers to display
 * Call once per frame in your main loop */
void RayCast3D_Render(void);

/*---------------------------------------------------------------------------
 * Component Headers
 *---------------------------------------------------------------------------*/

#include "assets/maps.h"
#include "assets/images.h"
#include "assets/colors.h"
#include "services/graphics.h"
#include "services/sprites.h"
#include "services/camera.h"
#include "services/map.h"
#include "utils/fixed.h"

#endif /* RAYCAST3D_H */