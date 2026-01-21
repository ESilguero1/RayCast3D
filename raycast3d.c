/* raycast3d.c
 * RayCast3D - Fixed-Point Raycasting Engine
 * Main engine facade providing initialization and rendering
 *
 * Author: Elijah Silguero
 * Created: December 2025
 * Modified: January 2026
 * Hardware: MSPM0G3507 with ST7735 LCD
 *
 * This module provides the top-level API for the raycasting engine.
 * Users should call RayCast3D_Init() once at startup, then
 * RayCast3D_Render() each frame.
 */

#include <stdint.h>
#include "../inc/Clock.h"
#include "services/graphics.h"
#include "services/sprites.h"
#include "hal/buffer.h"
#include "utils/fixed.h"
#include "utils/fpscounter.h"

/*---------------------------------------------------------------------------
 * Private Functions
 *---------------------------------------------------------------------------*/

/* Clear Z-buffer to maximum depth (sprites behind everything) */
static void clearZBuffer(void) {
    for (int i = 0; i < SCREEN_WIDTH; i++) {
        ZBuffer[i] = FIXED_LARGE;  /* Max distance = infinitely far */
    }
}

/*---------------------------------------------------------------------------
 * Public Functions
 *---------------------------------------------------------------------------*/

void RayCast3D_Init(void) {
    Clock_Init80MHz(0);     /* Fast clock for performance */
    Fixed_Init();           /* Initialize fixed-point math tables */
    Graphics_Init();        /* Initialize display pipeline */
}

void RayCast3D_Render(void) {
    /* Update frame timing for FPS calculation */
    FPSCounter_Update();

    /* Clear Z-buffer once per frame (shared between all quarters) */
    clearZBuffer();

    /* Render all 4 screen quarters */
    for (int side = 0; side < 4; side++) {
        Buffer_Clear();

        /* Cast rays for this quarter */
        CastRays(side);

        /* Render world sprites */
        Sprites_RenderAll(side);

        /* Render 2D overlays */
        Graphics_RenderOverlays(side);

        /* Transfer to display via DMA (async) */
        Buffer_WaitComplete();
        Buffer_RenderDMA(side, 0);
    }

    /* Clear overlay queues after all 4 sides rendered */
    Graphics_ClearOverlayQueues();
}
