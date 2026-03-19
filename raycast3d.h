/**
 * @file      raycast3d.h
 * @brief     RayCast3D - Fixed-Point Raycasting Engine
 *
 * Main header that includes all library components.
 *
 * @author    Elijah Silguero
 * @date      December 2025
 *
 * This library provides a complete raycasting engine optimized
 * for embedded systems using Q16.16 fixed-point math.
 *
 * Usage:
 *   1. Call RayCast3D_Init() once at startup
 *   2. Configure scene: Map_Load(), Camera_SetPosition(), etc.
 *   3. In main loop: RayCast3D_Render()
 */

/**
 * @defgroup EngineCore Engine Core
 * @brief Top-level engine initialization and per-frame rendering.
 *
 * The Engine Core provides the two entry points for the RayCast3D library.
 * Call RayCast3D_Init() once at startup to configure the display and DMA
 * hardware, then call RayCast3D_Render() once per iteration of your main
 * loop to cast rays, draw sprites and overlays, and transfer the frame
 * to the ST7735 display via DMA.
 *
 * @{
 */

#ifndef RAYCAST3D_H
#define RAYCAST3D_H

/*---------------------------------------------------------------------------
 * Engine API
 *---------------------------------------------------------------------------*/

/**
 * @brief Initialize the raycasting engine.
 *
 * Configures the ST7735 display, SPI bus, and DMA channel 0 for
 * asynchronous frame transfers. Must be called once at startup
 * before any other RayCast3D function.
 */
void RayCast3D_Init(void);

/**
 * @brief Render one complete frame to the display.
 *
 * Performs the full rendering pipeline for each of the four screen
 * quarters: clears the depth buffer, casts rays to draw textured walls,
 * renders world sprites with depth sorting, draws queued UI overlays
 * (text, foreground sprites, FPS counter), and transfers each quarter
 * to the ST7735 via DMA. Call once per iteration of your main loop.
 */
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
