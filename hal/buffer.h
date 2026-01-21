/* buffer.h
 * Double-Buffered Rendering HAL for RayCast3D
 * Manages quarter-screen render buffers with DMA transfer
 *
 * Author: Elijah Silguero
 * Created: December 2025
 * Modified: January 2026
 * Hardware: MSPM0G3507 with ST7735 LCD
 *
 * Uses double-buffering to allow rendering while DMA transfers.
 * Screen is divided into 4 quarters for memory efficiency.
 */

#ifndef BUFFER_H_
#define BUFFER_H_

#include <stdint.h>
#include "../services/graphics.h"
#include "../services/sprites.h"

/* Buffer dimensions - quarter-screen for DMA double-buffering */
#define BUFFER_WIDTH (SCREEN_WIDTH / 4)
#define BUFFER_HEIGHT SCREEN_HEIGHT

/* Current render buffer pointer (swapped with DMA buffer) */
extern uint16_t* Buffer_RenderBuffer;

/*---------------------------------------------------------------------------
 * Initialization
 *---------------------------------------------------------------------------*/

/* Initialize buffer system, SPI, and ST7735 display */
void Buffer_Init(void);

/*---------------------------------------------------------------------------
 * Configuration
 *---------------------------------------------------------------------------*/

/* Set floor color for gradient rendering
 * Inputs: color - 16-bit RGB565 color value */
void Buffer_SetFloorColor(uint16_t color);

/* Set sky/ceiling color
 * Inputs: color - 16-bit RGB565 color value */
void Buffer_SetSkyColor(uint16_t color);

/* Set floor gradient intensity
 * Inputs: intensity - 0.0 (solid) to 1.0 (full gradient to black) */
void Buffer_SetFloorGradient(double intensity);

/*---------------------------------------------------------------------------
 * Rendering Operations
 *---------------------------------------------------------------------------*/

/* Clear render buffer with sky and floor gradient */
void Buffer_Clear(void);

/* Set a single pixel in the render buffer
 * Inputs: x, y - buffer-local coordinates (0 to BUFFER_WIDTH-1)
 *         color - 16-bit RGB565 color value */
void Buffer_SetPixel(int x, int y, uint16_t color);

/* Draw a foreground sprite to the buffer
 * Inputs: side - which quarter (0-3)
 *         sprite - sprite data to render */
void Buffer_DrawForegroundSprite(int side, Sprite sprite);

/* Blit a source buffer to the render buffer
 * Inputs: srcBuffer - source pixel data
 *         srcWidth, srcHeight - source dimensions
 *         destX, destY - destination position */
void Buffer_Blit(uint16_t* srcBuffer, int srcWidth, int srcHeight,
                 int destX, int destY);

/* Print text to the render buffer
 * Inputs: text - null-terminated string
 *         screenX, screenY - screen position
 *         color - text color
 *         side - which quarter (0-3) */
void Buffer_PrintText(const char *text, int screenX, int screenY,
                      uint16_t color, int side);

/*---------------------------------------------------------------------------
 * DMA Transfer Operations
 *---------------------------------------------------------------------------*/

/* Start DMA transfer of render buffer to display (non-blocking)
 * Inputs: side - which quarter (0-3)
 *         callback - function to call when complete (NULL for none)
 * Returns: 0 on success, -1 if DMA busy */
int Buffer_RenderDMA(int side, void (*callback)(void));

/* Check if DMA transfer is in progress
 * Returns: 1 if busy, 0 if idle */
int Buffer_IsBusy(void);

/* Block until DMA transfer completes */
void Buffer_WaitComplete(void);

#endif /* BUFFER_H_ */