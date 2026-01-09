#include "fpscounter.h"
#include "../drivers/Timer.h"
#include "../inc/Clock.h"
#include <ti/devices/msp/msp.h>

#define SMOOTHING_FRAMES 16

static uint32_t lastTime;
static uint32_t frameCount;
static uint32_t accumulatedCycles;
static uint32_t currentFPS;

void FPSCounter_Init(void) {
    TimerG12_Init();
    lastTime = TIMG12->COUNTERREGS.CTR;
    frameCount = 0;
    accumulatedCycles = 0;
    currentFPS = 0;
}

uint32_t FPSCounter_Update(void) {
    uint32_t now = TIMG12->COUNTERREGS.CTR;

    // Timer counts down, so elapsed = lastTime - now
    uint32_t elapsed = lastTime - now;
    lastTime = now;

    accumulatedCycles += elapsed;
    frameCount++;

    // Update FPS every SMOOTHING_FRAMES frames
    if (frameCount >= SMOOTHING_FRAMES) {
        // FPS = frames / seconds = frames / (cycles / clock)
        // FPS = frames * clock / cycles
        currentFPS = (uint32_t)(((uint64_t)frameCount * Clock_Freq()) / accumulatedCycles);
        frameCount = 0;
        accumulatedCycles = 0;
    }

    return currentFPS;
}

uint32_t FPSCounter_Get(void) {
    return currentFPS;
}
