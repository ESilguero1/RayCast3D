/* SPI_DMA.c
 * DMA-accelerated SPI transfers for ST7735 LCD
 *
 * Implementation follows TI DriverLib EXACTLY:
 *   https://github.com/TexasInstruments/mspm0-sdk
 *   source/ti/driverlib/dl_dma.h
 *   source/ti/driverlib/dl_spi.h
 *
 * Uses constants from ti/devices/msp/peripherals/hw_dma.h and hw_spi.h
 *
 * Key insight: DMA does NOT require explicit power enable like GPIO/SPI.
 * TI's SysConfig examples show no DMA power enable sequence.
 */

#include <ti/devices/msp/msp.h>
#include "ti/devices/msp/peripherals/hw_dma.h"
#include "ti/devices/msp/peripherals/hw_spi.h"
#include "SPI_DMA.h"

/*---------------------------------------------------------------------------
 * DMA Channel Selection
 *---------------------------------------------------------------------------*/
#define DMA_CH  0

/*---------------------------------------------------------------------------
 * Module State
 *---------------------------------------------------------------------------*/
static volatile int dmaBusy = 0;
static SPI_DMA_Callback userCallback = 0;

/*---------------------------------------------------------------------------
 * DL_Common_updateReg - helper from dl_common.h
 * Performs read-modify-write to update specific bits
 *---------------------------------------------------------------------------*/
static void updateReg(volatile uint32_t *reg, uint32_t val, uint32_t mask) {
    uint32_t tmp;
    tmp = *reg;
    tmp = tmp & ~mask;
    *reg = tmp | (val & mask);
}

/*---------------------------------------------------------------------------
 * DL_DMA_configTransfer - exact implementation from dl_dma.h
 * Configures DMACTL register for transfer mode, width, and increment
 *---------------------------------------------------------------------------*/
static void DMA_configTransfer(uint8_t channelNum,
    uint32_t transferMode, uint32_t extendedMode,
    uint32_t srcWidth, uint32_t destWidth,
    uint32_t srcIncrement, uint32_t destIncrement)
{
    /* This is the EXACT formula from TI's DL_DMA_configTransfer:
     * Dest fields are shifted 4 bits from source fields */
    DMA->DMACHAN[channelNum].DMACTL =
        (transferMode | extendedMode |
         ((destIncrement) << 4) | srcIncrement |
         ((destWidth) << 4) | srcWidth);
}

/*---------------------------------------------------------------------------
 * DL_DMA_setTrigger - exact implementation from dl_dma.h
 * Configures DMATCTL register for trigger source
 *---------------------------------------------------------------------------*/
static void DMA_setTrigger(uint8_t channelNum, uint8_t trigger, uint32_t triggerType) {
    /* This is the EXACT formula from TI's DL_DMA_setTrigger */
    updateReg(&DMA->DMATRIG[channelNum].DMATCTL,
        trigger | triggerType,
        DMA_DMATCTL_DMATSEL_MASK | DMA_DMATCTL_DMATINT_MASK);
}

/*---------------------------------------------------------------------------
 * SPI_DMA_Init
 * Follows TI SysConfig pattern - no explicit DMA power enable needed
 *---------------------------------------------------------------------------*/
void SPI_DMA_Init(void) {
    /* Configure DMA channel - same pattern as DL_DMA_initChannel() which calls:
     * 1. DL_DMA_configTransfer()
     * 2. DL_DMA_setTrigger() */

    /* Step 1: Configure transfer parameters
     * Using hw_dma.h constants for DMASRCWDTH, DMASRCINCR positions */
    DMA_configTransfer(DMA_CH,
        DMA_DMACTL_DMATM_SINGLE,        /* Single transfer per trigger (bits 29:28 = 0) */
        DMA_DMACTL_DMAEM_NORMAL,        /* Normal extended mode (bits 25:24 = 0) */
        DMA_DMACTL_DMASRCWDTH_BYTE,     /* Source: 8-bit (bits 10:8 = 0) */
        DMA_DMACTL_DMASRCWDTH_BYTE,     /* Dest: 8-bit (will be shifted for bits 14:12) */
        DMA_DMACTL_DMASRCINCR_INCREMENT, /* Source: increment (bits 19:16) */
        DMA_DMACTL_DMASRCINCR_UNCHANGED); /* Dest: fixed (will be shifted for bits 23:20) */

    /* Step 2: Configure trigger
     * External trigger type = 0 (bit 7 clear) */
    DMA_setTrigger(DMA_CH, DMA_SPI1_TX_TRIG, DMA_DMATCTL_DMATINT_EXTERNAL);

    /* Set destination address: SPI1 TXDATA register
     * Same as DL_DMA_setDestAddr() */
    DMA->DMACHAN[DMA_CH].DMADA = (uint32_t)&SPI1->TXDATA;

    /* Enable SPI1 to generate DMA TX triggers
     * Same as DL_SPI_enableDMATransmitEvent(SPI1) */
    SPI1->DMA_TRIG_TX.IMASK = SPI_DMA_TRIG_TX_IMASK_TX_SET;

    /* Enable DMA channel interrupt
     * Same as DL_DMA_enableInterrupt() */
    DMA->CPU_INT.IMASK |= DMA_CPU_INT_IMASK_DMACH0_SET;

    /* Enable in NVIC (DMA_INT_IRQn = 31 from mspm0g350x.h) */
    NVIC_EnableIRQ(DMA_INT_IRQn);
    NVIC_SetPriority(DMA_INT_IRQn, 2);

    dmaBusy = 0;
    userCallback = 0;
}

/*---------------------------------------------------------------------------
 * SPI_DMA_StartTransfer
 * Follows TI pattern for runtime DMA configuration
 *---------------------------------------------------------------------------*/
int SPI_DMA_StartTransfer(const uint8_t* data, uint32_t length,
                          SPI_DMA_Callback callback) {
    if (dmaBusy) {
        return -1;
    }

    if (data == 0 || length == 0 || length > 65535) {
        return -1;
    }

    dmaBusy = 1;
    userCallback = callback;

    /* Set source address - same as DL_DMA_setSrcAddr() */
    DMA->DMACHAN[DMA_CH].DMASA = (uint32_t)data;

    /* Set transfer size - same as DL_DMA_setTransferSize() */
    DMA->DMACHAN[DMA_CH].DMASZ = (uint16_t)length;

    /* Enable channel - same as DL_DMA_enableChannel()
     * This uses OR to set DMAEN without disturbing other bits */
    DMA->DMACHAN[DMA_CH].DMACTL |= DMA_DMACTL_DMAEN_ENABLE;

    return 0;
}

/*---------------------------------------------------------------------------
 * SPI_DMA_IsBusy
 *---------------------------------------------------------------------------*/
int SPI_DMA_IsBusy(void) {
    return dmaBusy;
}

/*---------------------------------------------------------------------------
 * SPI_DMA_WaitComplete
 *---------------------------------------------------------------------------*/
void SPI_DMA_WaitComplete(void) {
    while (dmaBusy) {
        __WFI();
    }
}

/*---------------------------------------------------------------------------
 * DMA_IRQHandler
 * DMA Interrupt Service Routine
 *---------------------------------------------------------------------------*/
void DMA_IRQHandler(void) {
    /* Clear interrupt - same as DL_DMA_clearInterruptStatus() */
    DMA->CPU_INT.ICLR = DMA_CPU_INT_IMASK_DMACH0_SET;

    /* Wait for SPI to finish shifting out the last bytes
     * STAT bit 4 = BUSY */
    while (SPI1->STAT & 0x10);

    dmaBusy = 0;

    /* Invoke user callback if registered */
    if (userCallback) {
        SPI_DMA_Callback cb = userCallback;
        userCallback = 0;
        cb();
    }
}
