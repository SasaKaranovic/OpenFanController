#include <tusb.h>
#include "usb_cdc.h"
#include "pico/bootrom.h"
#include "host_communication.h"

#define BUFFER_SIZE 2560
typedef struct rbuff_s
{
    uint32_t head;
    uint32_t tail;
    uint32_t count;
    char data[BUFFER_SIZE];
} rbuff_s;

char rxBuffer[BUFFER_SIZE] = {0};
rbuff_s txBuffer = { .head =0, .tail=0, .count=0, .data = {0} };

void usb_read_bytes(uint8_t itf)
{
    uint32_t len = tud_cdc_n_available(itf);

    if (len) {
        len = MIN(len, BUFFER_SIZE);
        if (len){
            uint32_t count;
            count = tud_cdc_n_read(itf, rxBuffer, len);

            // Loopback
            #if 0
            memcpy(txBuffer, rxBuffer, len);
            nTxLen += len;
            #endif

            // Copy to host communication
            host_comm_receive_data(rxBuffer, len);
        }
    }
}

void usb_write_bytes(uint8_t itf)
{
    if ( txBuffer.tail > txBuffer.head )
    {
        uint32_t count;
        uint32_t tx_available = tud_cdc_n_write_available(itf);
        tx_available = MIN(tx_available, (txBuffer.tail-txBuffer.head));

        count = tud_cdc_n_write(itf, &txBuffer.data[txBuffer.head], tx_available);

        if (count)
        {
            tud_cdc_n_write_flush(itf);
            txBuffer.head += count;

            if(txBuffer.head >= txBuffer.tail)
            {
                txBuffer.head = 0;
                txBuffer.tail = 0;
                txBuffer.count = 0;
            }
        }
    }
}
void usb_cdc_process(uint8_t itf)
{
    usb_read_bytes(itf);
    usb_write_bytes(itf);
}

// Support for default BOOTSEL reset by changing baud rate
void tud_cdc_line_coding_cb(__unused uint8_t itf, cdc_line_coding_t const* p_line_coding) {
    if (p_line_coding->bit_rate == 1200) {
        reset_usb_boot(0, 0);
    }
}

void usb_cdc_tick(void)
{
    int itf;

    tud_task();
    for (itf = 0; itf < CFG_TUD_CDC; itf++) {
        if (tud_cdc_n_connected(itf)) {
            usb_cdc_process(itf);
        }
    }
}

void usb_cdc_send_arr(uint8_t *pData, uint32_t nLenght)
{
    uint32_t len = MIN(nLenght, (BUFFER_SIZE-txBuffer.tail));
    memcpy(&txBuffer.data[txBuffer.tail], pData, len);
    txBuffer.tail += len;
}

void usb_cdc_send_str(const char *pData)
{
    int nLenght = strlen(pData);
    if(nLenght > 0)
    {
        uint32_t len = MIN(nLenght, (BUFFER_SIZE-txBuffer.tail));
        memcpy(&txBuffer.data[txBuffer.tail], pData, len);
        txBuffer.tail += len;
    }
}
