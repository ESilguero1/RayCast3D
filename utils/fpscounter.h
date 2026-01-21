/* fpscounter.h
 * RayCast3D FPS Counter Utility
 * Frame rate measurement and display
 *
 * Author: Elijah Silguero
 * Created: December 2025
 * Modified: January 2026
 * Hardware: MSPM0G3507 with Timer G12
 *
 * Uses hardware timer for accurate frame timing with
 * smoothing over multiple frames for stable display.
 */

#ifndef FPSCOUNTER_H_
#define FPSCOUNTER_H_

#include <stdint.h>

/*---------------------------------------------------------------------------
 * FPS Counter Functions
 *---------------------------------------------------------------------------*/

/* Initialize the FPS counter (starts Timer G12) */
void FPSCounter_Init(void);

/* Update FPS calculation - call once per frame
 * Returns: current smoothed FPS value */
uint32_t FPSCounter_Update(void);

/* Get current FPS without updating
 * Returns: last calculated FPS value */
uint32_t FPSCounter_Get(void);

#endif /* FPSCOUNTER_H_ */
