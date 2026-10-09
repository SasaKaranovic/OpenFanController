#include "config.h"
#include "flash_eeprom.h"

#define MIN_LOG_LEVEL_DEBUG
#define LOGGER_TAG "CFG"
#include "logger.h"

static bool openfan_config_load(void);
static bool openfan_config_save(void);
static openfan_config_s device_cfg = {0};


bool openfan_config_init(void)
{
    flash_eeprom_status_t status;
    status = flash_eeprom_init();

    if (status != FLASH_EEPROM_OK)
    {
        Logger_ERROR("%s:%d: Failed to init flash eeprom (%d)", __FUNCTION__, __LINE__, status);
        return false;
    }
    else
    {
        if (openfan_config_load())
        {
            Logger_INFO("Config init+load complete.");
            return true;
        }
        else
        {
            Logger_ERROR("%s:%d: Config init complete.", __FUNCTION__, __LINE__);
            return true;

        }
    }
}

static bool openfan_config_load(void)
{
    flash_eeprom_status_t status;
    status = flash_eeprom_read(0, &device_cfg, sizeof(openfan_config_s));
    if (status != FLASH_EEPROM_OK)
    {
        Logger_ERROR("%s:%d: Failed to read flash eeprom (%d)", __FUNCTION__, __LINE__, status);
        return false;
    }
    else
    {
    }

    if (device_cfg.valid_flag == OPENFAN_CFG_VALID_FLAG)
    {
        Logger_INFO("Config read complete.");
        return true;
    }
    else
    {
        Logger_INFO("Config read complete but cfg is not initialized. Resetting to default...");
        openfan_config_load_defaults(true);
        Logger_INFO("Config load complete.");

        return true;
    }
}

bool openfan_config_load_defaults(bool save_cfg)
{
    device_cfg.valid_flag = OPENFAN_CFG_VALID_FLAG;
    device_cfg.cfg_version = OPENFAN_CFG_VERSION;
    device_cfg.blink_led_heartbeat = true;

    if (save_cfg)
    {
        return openfan_config_save();
    }

    return true;
}

static bool openfan_config_save(void)
{
    flash_eeprom_status_t status;
    status = flash_eeprom_write(0, &device_cfg, sizeof(openfan_config_s));
    if (status != FLASH_EEPROM_OK)
    {
        Logger_ERROR("%s:%d: Failed to write flash eeprom (%d)", __FUNCTION__, __LINE__, status);
        return false;
    }
    else
    {
        Logger_INFO("Config write complete.");
        return true;
    }
}


bool openfan_config_flag_get(openfan_config_flag_t flag)
{
    switch (flag)
    {
        case OPENFAN_CONFIG_BLINK_LED:
            return device_cfg.blink_led_heartbeat;

        default:
            Logger_ERROR("%s:%d: Unknown flag %d", __FUNCTION__, __LINE__, flag);
            return false;
    }
}

bool openfan_config_flag_set(openfan_config_flag_t flag, bool newValue, bool save_cfg)
{
    switch (flag)
    {
        case OPENFAN_CONFIG_BLINK_LED:
            device_cfg.blink_led_heartbeat = newValue;
            Logger_DEBUG("%s:%d OPENFAN_CONFIG_BLINK_LED set to 0x%02X", __FUNCTION__, __LINE__, newValue);
            break;

        default:
            Logger_ERROR("%s:%d: Unknown flag %d", __FUNCTION__, __LINE__, flag);
            return false;
    }

    if (save_cfg)
    {
        return openfan_config_save();
    }

    return true;
}


