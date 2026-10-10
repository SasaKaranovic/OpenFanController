#include <hardware/flash.h>
#include <tusb.h>

#define DESC_STR_MAX 20

#define USBD_VID 0x2E8A /* Raspberry Pi */
#define USBD_PID 0x000A /* Raspberry Pi Pico SDK CDC */

#define USBD_DESC_LEN (TUD_CONFIG_DESC_LEN + TUD_CDC_DESC_LEN * CFG_TUD_CDC)
#define USBD_MAX_POWER_MA 500

#define USBD_ITF_MAX (CFG_TUD_CDC * 2)

#define CDC_EP_CMD(n) (0x81 + (n) * 2)
#define CDC_EP_OUT(n) (0x01 + (n) * 2)
#define CDC_EP_IN(n)  (0x82 + (n) * 2)

#define USBD_CDC_CMD_MAX_SIZE 8
#define USBD_CDC_IN_OUT_MAX_SIZE 64

#define USBD_STR_0 0x00
#define USBD_STR_MANUF 0x01
#define USBD_STR_PRODUCT 0x02
#define USBD_STR_SERIAL 0x03
#define USBD_STR_SERIAL_LEN 17
#define USBD_STR_CDC 0x04

static const tusb_desc_device_t usbd_desc_device = {
    .bLength = sizeof(tusb_desc_device_t),
    .bDescriptorType = TUSB_DESC_DEVICE,
    .bcdUSB = 0x0200,
    #if (CFG_TUD_CDC == 1)
    .bDeviceClass = TUSB_CLASS_CDC,
    #else
    .bDeviceClass = TUSB_CLASS_MISC,
    #endif
    .bDeviceSubClass = MISC_SUBCLASS_COMMON,
    .bDeviceProtocol = MISC_PROTOCOL_IAD,
    .bMaxPacketSize0 = CFG_TUD_ENDPOINT0_SIZE,
    .idVendor = USBD_VID,
    .idProduct = USBD_PID,
    .bcdDevice = 0x0100,
    .iManufacturer = USBD_STR_MANUF,
    .iProduct = USBD_STR_PRODUCT,
    .iSerialNumber = USBD_STR_SERIAL,
    .bNumConfigurations = 1,
};

static uint8_t usbd_desc_cfg[256];
static uint16_t usbd_desc_cfg_len;

static char usbd_serial[USBD_STR_SERIAL_LEN] = "000000000000";

static const char *const usbd_desc_str[] = {
    [USBD_STR_MANUF] = "Karanovic Research",
    [USBD_STR_PRODUCT] = "OpenFan-Controller",
    [USBD_STR_SERIAL] = usbd_serial,
    [USBD_STR_CDC] = "Board CDC",
};

const uint8_t *tud_descriptor_device_cb(void)
{
    return (const uint8_t *) &usbd_desc_device;
}

const uint8_t *tud_descriptor_configuration_cb(uint8_t index)
{
    if (usbd_desc_cfg_len == 0) {
        uint8_t *desc = usbd_desc_cfg;
        uint8_t itf_num = 0;
        uint8_t *p = desc;

        uint8_t config_desc[TUD_CONFIG_DESC_LEN] = {
            TUD_CONFIG_DESCRIPTOR(
                1, USBD_ITF_MAX, USBD_STR_0, USBD_DESC_LEN,
                TUSB_DESC_CONFIG_ATT_REMOTE_WAKEUP, USBD_MAX_POWER_MA
            )
        };
        memcpy(p, config_desc, TUD_CONFIG_DESC_LEN);
        p += TUD_CONFIG_DESC_LEN;

        for (int i = 0; i < CFG_TUD_CDC; i++) {
            uint8_t ep_cmd = CDC_EP_CMD(i);
            uint8_t ep_out = CDC_EP_OUT(i);
            uint8_t ep_in = CDC_EP_IN(i);

            uint8_t cdc_desc[TUD_CDC_DESC_LEN] = {
                TUD_CDC_DESCRIPTOR(itf_num, USBD_STR_CDC,
                    ep_cmd, USBD_CDC_CMD_MAX_SIZE,
                    ep_out, ep_in, USBD_CDC_IN_OUT_MAX_SIZE
                )
            };
            memcpy(p, cdc_desc, TUD_CDC_DESC_LEN);
            p += TUD_CDC_DESC_LEN;
            itf_num += 2;
        }

        usbd_desc_cfg_len = p - desc;
    }

    return usbd_desc_cfg;
}

const uint16_t *tud_descriptor_string_cb(uint8_t index, uint16_t langid)
{
    static uint16_t desc_str[DESC_STR_MAX];
    uint8_t len;

    if (index == 0) {
        desc_str[1] = 0x0409;
        len = 1;
    } else {
        const char *str;
        char serial[USBD_STR_SERIAL_LEN];

        if (index >= sizeof(usbd_desc_str) / sizeof(usbd_desc_str[0]))
        {
            return NULL;
        }

        str = usbd_desc_str[index];
        for (len = 0; len < DESC_STR_MAX - 1 && str[len]; ++len)
        {
            desc_str[1 + len] = str[len];
        }
    }

    desc_str[0] = (TUSB_DESC_STRING << 8) | (2 * len + 2);

    return desc_str;
}

void usbd_serial_init(void)
{
    uint8_t id[8];

    flash_get_unique_id(id);

    snprintf(usbd_serial, USBD_STR_SERIAL_LEN, "%02X%02X%02X%02X%02X%02X%02X%02X",
         id[0], id[1], id[2], id[3], id[4], id[5], id[6], id[7]);
}
