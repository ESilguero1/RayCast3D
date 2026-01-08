/* ST7735_DMA.c
 * DMA-accelerated bitmap display for ST7735 LCD
 *
 * Self-contained: replicates needed code from SPI.c and ST7735.c
 * Does NOT modify existing files.
 */

#include <ti/devices/msp/msp.h>
#include "ST7735_DMA.h"
#include "../bus/SPI_DMA.h"

/*---------------------------------------------------------------------------
 * ST7735 Commands (from ST7735.c)
 *---------------------------------------------------------------------------*/
#define ST7735_CASET   0x2A
#define ST7735_RASET   0x2B
#define ST7735_RAMWR   0x2C

/*---------------------------------------------------------------------------
 * Display configuration for INITR_REDTAB rotation 1
 * Must match your ST7735_InitR() and ST7735_SetRotation() settings
 *---------------------------------------------------------------------------*/
static uint8_t colStart = 0;
static uint8_t rowStart = 0;
static int16_t displayWidth = 160;
static int16_t displayHeight = 128;

/*---------------------------------------------------------------------------
 * Transmit buffer for byte-swapped pixels
 * Sized for half-screen (80x128 = 10240 pixels = 20480 bytes)
 *---------------------------------------------------------------------------*/
static uint16_t txBuffer[80 * 128];

/*---------------------------------------------------------------------------
 * RS pin control PA13 (replicated from SPI.c)
 *---------------------------------------------------------------------------*/
#define RS_DATA()    (GPIOA->DOUTSET31_0 = (1<<13))
#define RS_COMMAND() (GPIOA->DOUTCLR31_0 = (1<<13))

/*---------------------------------------------------------------------------
 * User callback storage
 *---------------------------------------------------------------------------*/
static ST7735_DMA_Callback dmaUserCallback = 0;

/*---------------------------------------------------------------------------
 * Internal callback wrapper
 *---------------------------------------------------------------------------*/
static void DMA_InternalCallback(void) {
    if (dmaUserCallback) {
        ST7735_DMA_Callback cb = dmaUserCallback;
        dmaUserCallback = 0;
        cb();
    }
}

/*---------------------------------------------------------------------------
 * Polling-based SPI output (replicated from SPI.c)
 * RS pin needs toggling between command and data
 *---------------------------------------------------------------------------*/
static void spiOutCommand(uint8_t cmd) {
    while (SPI1->STAT & 0x10);  /* Wait while BUSY */
    RS_COMMAND();
    SPI1->TXDATA = cmd;
    while (SPI1->STAT & 0x10);  /* Wait for completion */
}

static void spiOutData(uint8_t data) {
    while ((SPI1->STAT & 0x02) == 0);  /* Wait for TNF (TX FIFO not full) */
    RS_DATA();
    SPI1->TXDATA = data;
}

/*---------------------------------------------------------------------------
 * Set address window (replicated from ST7735.c)
 * Must use polling - RS pin toggles between command and data
 *---------------------------------------------------------------------------*/
static void setAddrWindow(uint8_t x0, uint8_t y0, uint8_t x1, uint8_t y1) {
    spiOutCommand(ST7735_CASET);
    spiOutData(0x00);
    spiOutData(x0 + colStart);
    spiOutData(0x00);
    spiOutData(x1 + colStart);

    spiOutCommand(ST7735_RASET);
    spiOutData(0x00);
    spiOutData(y0 + rowStart);
    spiOutData(0x00);
    spiOutData(y1 + rowStart);

    spiOutCommand(ST7735_RAMWR);
}

/*---------------------------------------------------------------------------
 * ST7735_DMA_Init
 *---------------------------------------------------------------------------*/
void ST7735_DMA_Init(void) {
    SPI_DMA_Init();

    /* Configuration for INITR_REDTAB with rotation 1
     * Adjust these values if using different display/rotation:
     * - INITR_REDTAB rotation 0: colStart=2, rowStart=1
     * - INITR_REDTAB rotation 1: colStart=0, rowStart=0 (what we use)
     * - INITR_GREENTAB: different offsets
     */
    colStart = 0;
    rowStart = 0;
    displayWidth = 160;
    displayHeight = 128;
}

/*---------------------------------------------------------------------------
 * ST7735_DrawBitmapDMA
 * Non-blocking bitmap transfer using DMA
 *---------------------------------------------------------------------------*/
int ST7735_DrawBitmapDMA(int16_t x, int16_t y, const uint16_t *image,
                         int16_t w, int16_t h, ST7735_DMA_Callback callback) {
    if (SPI_DMA_IsBusy()) {
        return -1;
    }

    /* Basic bounds check (matches ST7735_DrawBitmap logic) */
    if (x >= displayWidth || y < 0 || (x + w) <= 0 || (y - h + 1) >= displayHeight) {
        return 0;  /* Nothing to draw, not an error */
    }

    /* Set address window (polling - RS pin toggles) */
    setAddrWindow(x, y - h + 1, x + w - 1, y);

    /* Wait for SPI to finish window setup commands */
    while (SPI1->STAT & 0x10);

    /* Byte-swap pixels into transmit buffer
     * Problem: ST7735 expects MSB first, ARM stores little-endian
     *
     * Match DrawBitmap row order: the original DrawBitmap iterates
     * from bottom-left to top-right of the image, sending MSB first.
     *
     * For a bitmap stored with row 0 at bottom:
     * srcIdx starts at w*(h-1) and decrements by w each row
     */
    uint32_t pixelCount = (uint32_t)w * (uint32_t)h;
    int srcIdx = w * (h - 1);  /* Bottom-left of source image */
    int dstIdx = 0;

    for (int row = 0; row < h; row++) {
        for (int col = 0; col < w; col++) {
            uint16_t pixel = image[srcIdx + col];
            /* Swap bytes: 0xABCD -> 0xCDAB (puts MSB first in memory) */
            txBuffer[dstIdx++] = (pixel >> 8) | (pixel << 8);
        }
        srcIdx -= w;  /* Move up one row in source */
    }

    /* Set RS HIGH for data mode before DMA starts */
    RS_DATA();

    /* Store callback and start DMA transfer */
    dmaUserCallback = callback;
    return SPI_DMA_StartTransfer((const uint8_t*)txBuffer, pixelCount * 2,
                                 DMA_InternalCallback);
}

/*---------------------------------------------------------------------------
 * ST7735_DMA_IsBusy
 *---------------------------------------------------------------------------*/
int ST7735_DMA_IsBusy(void) {
    return SPI_DMA_IsBusy();
}

/*---------------------------------------------------------------------------
 * ST7735_DMA_WaitComplete
 *---------------------------------------------------------------------------*/
void ST7735_DMA_WaitComplete(void) {
    SPI_DMA_WaitComplete();
}
