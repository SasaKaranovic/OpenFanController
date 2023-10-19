#ifndef __USB_CDC_INC_H__
#define __USB_CDC_INC_H__

#include <stdint.h>
#include <stdbool.h>

#if !defined(MIN)
#define MIN(a, b) ((a > b) ? b : a)
#endif /* MIN */

void usb_read_bytes(uint8_t itf);
void usb_write_bytes(uint8_t itf);
void usb_cdc_process(uint8_t itf);
void usb_cdc_tick(void);
void usb_cdc_send_arr(uint8_t *pData, uint32_t nLenght);
void usb_cdc_send_str(const char *pData);

#endif /* __USB_CDC_INC_H__ */
