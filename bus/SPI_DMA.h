/* SPI_DMA.h
 * RayCast3D DMA-Accelerated SPI Bus Driver
 * Asynchronous SPI transfers using DMA controller
 *
 * Author: Elijah Silguero
 * Created: December 2025
 * Modified: January 2026
 * Hardware: MSPM0G3507 with SPI1
 *
 * Implements TI DriverLib-compatible DMA transfers for
 * high-speed non-blocking display updates.
 * Reference: https://github.com/TexasInstruments/mspm0-sdk
 */

#ifndef __SPI_DMA_H__
#define __SPI_DMA_H__

#include <stdint.h>

typedef void (*SPI_DMA_Callback)(void);

/**
 * Initialize DMA for SPI1 TX transfers.
 * Must be called after SPI_Init().
 */
void SPI_DMA_Init(void);

/**
 * Start an asynchronous DMA transfer to SPI1.
 * RS pin must already be set HIGH for data mode before calling.
 *
 * @param data     Pointer to source data buffer (must remain valid until callback)
 * @param length   Number of bytes to transfer (max 65535)
 * @param callback Function to call when transfer completes (NULL for no callback)
 * @return 0 on success, -1 if DMA is busy or invalid params
 */
int SPI_DMA_StartTransfer(const uint8_t* data, uint32_t length,
                          SPI_DMA_Callback callback);

/**
 * Check if a DMA transfer is currently in progress.
 * @return 1 if DMA is busy, 0 if idle
 */
int SPI_DMA_IsBusy(void);

/**
 * Wait (blocking) for any pending DMA transfer to complete.
 */
void SPI_DMA_WaitComplete(void);

#endif /* __SPI_DMA_H__ */
