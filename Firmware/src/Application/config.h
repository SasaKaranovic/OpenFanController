#ifndef __OPENFAN_CONFIG_INC_H__
#define __OPENFAN_CONFIG_INC_H__

#include <stdint.h>
#include <stdbool.h>

#define OPENFAN_CFG_VALID_FLAG  0x53
#define OPENFAN_CFG_VERSION     0x01


typedef struct openfan_config {
    uint8_t valid_flag;
    uint8_t cfg_version;
    bool blink_led_heartbeat : 1;
} openfan_config_s;

typedef enum openfan_config_flag {
    OPENFAN_CONFIG_BLINK_LED = 1,
    OPENFAN_CONFIG_BLINK_LAST
} openfan_config_flag_t;


// Core funcions
bool openfan_config_init(void);
bool openfan_config_load_defaults(bool save_cfg);

// Config flag set/reset functions
bool openfan_config_flag_get(openfan_config_flag_t flag);
bool openfan_config_flag_set(openfan_config_flag_t flag, bool newValue, bool save_cfg);

#endif
