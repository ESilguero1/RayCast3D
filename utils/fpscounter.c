/* fpscounter.c
 * RayCast3D FPS Counter Utility
 * Frame rate measurement and display
 *
 * Author: Elijah Silguero
 * Created: December 2025
 * Modified: January 2026
 * Hardware: MSPM0G3507 with Timer G12
 */

#include "fpscounter.h"
#include "../drivers/Timer.h"
#include "../inc/Clock.h"
#include <ti/devices/msp/msp.h>

/*---------------------------------------------------------------------------
 * Private Constants
 *---------------------------------------------------------------------------*/

/* Number of frames to average for smooth FPS display */
#define FPS_SMOOTHING_FRAMES 16

/*---------------------------------------------------------------------------
 * Private Variables
 *---------------------------------------------------------------------------*/

static uint32_t LastTime;
static uint32_t FrameCount;
static uint32_t AccumulatedCycles;
static uint32_t CurrentFPS;

/*---------------------------------------------------------------------------
 * Public Functions
 *---------------------------------------------------------------------------*/

void FPSCounter_Init(void) {
    TimerG12_Init();
    LastTime = TIMG12->COUNTERREGS.CTR;
    FrameCount = 0;
    AccumulatedCycles = 0;
    CurrentFPS = 0;
}

uint32_t FPSCounter_Update(void) {
    uint32_t now = TIMG12->COUNTERREGS.CTR;

    /* Timer counts down, so elapsed = LastTime - now */
    uint32_t elapsed = LastTime - now;
    LastTime = now;

    AccumulatedCycles += elapsed;
    FrameCount++;

    /* Update FPS every FPS_SMOOTHING_FRAMES frames */
    if (FrameCount >= FPS_SMOOTHING_FRAMES) {
        /* FPS = frames * clock / cycles */
        CurrentFPS = (uint32_t)(((uint64_t)FrameCount * Clock_Freq()) /
                                AccumulatedCycles);
        FrameCount = 0;
        AccumulatedCycles = 0;
    }

    return CurrentFPS;
}

uint32_t FPSCounter_Get(void) {
    return CurrentFPS;
}
