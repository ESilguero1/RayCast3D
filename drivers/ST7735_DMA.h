/* ST7735_DMA.h
 * RayCast3D DMA-Accelerated ST7735 Display Driver
 * Non-blocking bitmap transfers using DMA
 *
 * Author: Elijah Silguero
 * Created: December 2025
 * Modified: January 2026
 * Hardware: MSPM0G3507 with ST7735 LCD
 *
 * Self-contained driver that works alongside existing ST7735.c.
 * Enables asynchronous bitmap transfers for double-buffering.
 */

#ifndef __ST7735_DMA_H__
#define __ST7735_DMA_H__

#include <stdint.h>

typedef void (*ST7735_DMA_Callback)(void);

/**
 * Initialize DMA display system.
 * Must be called after ST7735_InitR().
 */
void ST7735_DMA_Init(void);

/**
 * Draw bitmap using DMA (non-blocking).
 * Image buffer must remain valid until callback fires.
 *
 * @param x        Horizontal position of bottom-left corner
 * @param y        Vertical position of bottom-left corner
 * @param image    Pointer to 16-bit color image data
 * @param w        Width in pixels
 * @param h        Height in pixels
 * @param callback Function called when transfer completes (NULL for no callback)
 * @return 0 on success, -1 if busy
 */
int ST7735_DrawBitmapDMA(int16_t x, int16_t y, const uint16_t *image,
                         int16_t w, int16_t h, ST7735_DMA_Callback callback);

/**
 * Check if DMA bitmap transfer is in progress.
 * @return 1 if busy, 0 if idle
 */
int ST7735_DMA_IsBusy(void);

/**
 * Wait (blocking) for any pending DMA bitmap transfer.
 */
void ST7735_DMA_WaitComplete(void);

#endif /* __ST7735_DMA_H__ */
