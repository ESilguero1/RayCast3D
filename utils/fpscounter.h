#ifndef FPSCOUNTER_H_
#define FPSCOUNTER_H_

#include <stdint.h>

// Initialize the FPS counter (initializes Timer G12)
void FPSCounter_Init(void);

// Call once per frame to update timing - returns current FPS
// Averages over multiple frames for smooth display
uint32_t FPSCounter_Update(void);

// Get the current FPS value without updating
uint32_t FPSCounter_Get(void);

#endif /* FPSCOUNTER_H_ */
