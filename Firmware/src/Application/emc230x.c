#include "board.h"
#include "emc230x.h"
#include "hardware/i2c.h"

#define MIN_LOG_LEVEL_INFO
#define LOGGER_TAG "EMC230X"
#include "logger.h"

// #define EMC230X_DEVICE_I2C_ADDRESS      0x2C
#define EMC230X_DEVICE_I2C_ADDRESS      0x2D
#define EMC230X_DEVICE_MAX_CHANNELS     5


#define EMC230X_REG_CONFIG              0x20
#define EMC230X_REG_DRIVE_FAIL_STATUS   0x27
#define EMC230X_REG_VENDOR              0xfe
#define EMC230X_FAN_MAX                 0xff
#define EMC230X_FAN_MIN                 0x00
#define EMC230X_FAN_MAX_STATE           10
#define EMC230X_DEVICE                  0x34
#define EMC230X_VENDOR                  0x5d
#define EMC230X_REG_PRODUCT_ID          0xfd
#define EMC230X_TACH_REGS_UNUSE_BITS    3
#define EMC230X_TACH_CNT_MULTIPLIER     0x02
#define EMC230X_TACH_RANGE_MIN          480

/*
 * Factor by equations [2] and [3] from data sheet; valid for fans where the number of edges
 * equal (poles * 2 + 1).
 */
#define EMC230X_RPM_FACTOR                  3932160     // Datasheet Eqation: 4-3

#define EMC2305_REG_FAN_DRIVE(n)            (0x30 + 0x10 * (n))
#define EMC2305_REG_FAN_CONFIG(n)           (0x32 + 0x10 * (n))
#define EMC2305_REG_FAN_CONFIG2(n)          (0x33 + 0x10 * (n))
#define EMC2305_REG_FAN_MIN_DRIVE(n)        (0x38 + 0x10 * (n))
#define EMC230X_REG_FAN_TARGET_TACH_H(n)    (0x3D + 0x10 * (n))
#define EMC230X_REG_FAN_TARGET_TACH_L(n)    (0x3C + 0x10 * (n))
#define EMC230X_REG_FAN_TACH(n)             (0x3E + 0x10 * (n))

#define I2C_COMM_TIMEOUT                    100000

const uint16_t EMC320X_FAN_TACH_RANGE_MIN[4] = {480, 968, 1935, 3870};

static void target_rpm_to_tach(uint16_t nRPM, uint8_t *pHighByte, uint8_t *pLowByte);
static uint16_t register_data_to_rpm(uint8_t high, uint8_t low, uint8_t range);

static bool emc230x_send(uint8_t *pData, uint16_t nLen);
static bool emc230x_read(uint8_t *pData, uint16_t nLen);
static bool emc230x_send_then_read(uint8_t *pTXData, uint16_t nTXLen, uint8_t *pRXData, uint16_t nRXLen);

static uint8_t i2c_address = EMC230X_DEVICE_I2C_ADDRESS;
static uint8_t rxBuff[30] = {0};
static uint8_t txBuff[30] = {0};
static uint16_t nLen = 0;

void emc230x_init(void)
{
    emc230x_write_register(EMC230X_REG_CONFIG, (1<<6)); // Disable SMBUS inactivity (I2C)
}

void emc230x_config_fans(void)
{
    for(uint8_t i=0; i<EMC230X_DEVICE_MAX_CHANNELS; i++)
    {
        // emc230x_write_register(EMC2305_REG_FAN_CONFIG(i), 0x2B);

        // Enabel Tach filter, both methods of control, 50 PRM tolerance
        emc230x_write_register(EMC2305_REG_FAN_CONFIG2(i), 0x58);
    }
}


void emc230x_set_address(uint8_t address)
{
    i2c_address = address;
}

void emc230x_read_fan_rpm(uint8_t channel, uint16_t *pRPM)
{
    if(channel >= EMC230X_DEVICE_MAX_CHANNELS)
    {
        Logger_ERROR("Invalid fan channel selection! (%d>=%d)", channel, EMC230X_DEVICE_MAX_CHANNELS);
        return;
    }

    if(pRPM == NULL)
    {
        Logger_ERROR("Invalid RPM pointer!");
        return;
    }

    uint16_t rpm=0;
    bool res;
    uint8_t range;
    uint8_t multiplier;

    emc230x_read_register(EMC2305_REG_FAN_CONFIG(channel), &range);
    range = (range >> 5) & 0x03;

    // Set to read Tach HIGH byte
    nLen=0;
    txBuff[nLen++] = EMC230X_REG_FAN_TACH(channel);
    res = emc230x_send_then_read(txBuff, nLen, rxBuff, 2);

    if(!res)
    {
        *pRPM =  0;
        return;
    }

    rpm = register_data_to_rpm(rxBuff[0], rxBuff[1], range);
    *pRPM = rpm;
}


void emc230x_set_target_rpm(uint8_t channel, uint16_t nRPM)
{
    if(channel >= EMC230X_DEVICE_MAX_CHANNELS)
    {
        Logger_ERROR("Invalid fan channel selection! (%d>=%d)", channel, EMC230X_DEVICE_MAX_CHANNELS);
        return;
    }
    if(nRPM > 160000)
    {
        Logger_ERROR("Target RPM is higher than IC can support. Clipping.");
        nRPM = 16000;
    }

    uint32_t tach = 0;
    uint8_t range;
    uint8_t multiplier;
    uint8_t high;
    uint8_t low;

    emc230x_read_register(EMC2305_REG_FAN_CONFIG(channel), &range);
    range = (range >> 5) & 0x03;

    if (nRPM < EMC320X_FAN_TACH_RANGE_MIN[range])
    {
        high = 0xFF;
        low = 0xFF;
    }
    else
    {
        if(range <1)
        {
           multiplier = 1;
        }
        else
        {
            multiplier = 2*range;
        }


        tach = (EMC230X_RPM_FACTOR * multiplier) / nRPM;

        high = ((tach>>5) & 0xFF);
        low  = 0;
    }

    Logger_INFO("Setting RPM to %d (H:0x%02X L:0x%02X)", nRPM, high, low);

    emc230x_write_register(EMC2305_REG_FAN_CONFIG(channel), 0x09);
    emc230x_write_register(EMC230X_REG_FAN_TARGET_TACH_L(channel), low);
    emc230x_write_register(EMC230X_REG_FAN_TARGET_TACH_H(channel), high);
    emc230x_write_register(EMC2305_REG_FAN_CONFIG(channel), 0x89);
}


void emc230x_set_pwm(uint8_t channel, uint8_t nPWM)
{
    bool res;
    if(channel >= EMC230X_DEVICE_MAX_CHANNELS)
    {
        Logger_ERROR("Invalid fan channel selection! (%d>=%d)", channel, EMC230X_DEVICE_MAX_CHANNELS);
        return;
    }

    // Disable tach
    uint8_t reg;
    emc230x_read_register(EMC2305_REG_FAN_CONFIG(channel), &reg);
    reg = reg & 0x7F;
    emc230x_write_register(EMC2305_REG_FAN_CONFIG(channel), reg);

    nLen = 0;
    txBuff[nLen++] = EMC2305_REG_FAN_DRIVE(channel);
    txBuff[nLen++] = nPWM;
    res = emc230x_send(txBuff, nLen);
    if(res)
    {
        Logger_DEBUG("%s: Channel %d set to %d", __FUNCTION__, channel, nPWM);
    }
    else
    {
        Logger_ERROR("%s: emc230x_send failed!", __FUNCTION__);
    }
}


bool emc230x_read_register(uint8_t reg, uint8_t *pData)
{
    bool res;
    if(pData == NULL)
    {
        Logger_ERROR("%s: Null pointer! Aborting.", __FUNCTION__);
        return false;
    }
    nLen=0;
    txBuff[nLen++] = reg;
    res = emc230x_send_then_read(txBuff, nLen, rxBuff, 1);
    if(res)
    {
        *pData = rxBuff[0];
    }
    return res;
}

bool emc230x_write_register(uint8_t reg, uint8_t Data)
{
    bool res;
    nLen=0;
    txBuff[nLen++] = reg;
    txBuff[nLen++] = Data;
    res = emc230x_send(txBuff, nLen);
    return res;
}

static void target_rpm_to_tach(uint16_t nRPM, uint8_t *pHighByte, uint8_t *pLowByte)
{

}

static uint16_t register_data_to_rpm(uint8_t high, uint8_t low, uint8_t range)
{
    uint16_t tach;

    tach = ((high<<8) | (low));
    tach = tach >> EMC230X_TACH_REGS_UNUSE_BITS;

    if(range < 1)
    {
        tach = EMC230X_RPM_FACTOR / tach;
    }
    else
    {
        tach = EMC230X_RPM_FACTOR * 2 * range / tach;
    }

    if (tach <= EMC320X_FAN_TACH_RANGE_MIN[range])
    {
        return  0;
    }
    else
    {
        return  tach;
    }
}


bool emc230x_debug_registers(uint8_t startRegister, uint8_t *pData, uint16_t nReadCount)
{
    bool res;

    if(pData == NULL)
    {
        Logger_ERROR("%s: Null pointer! Aborting.", __FUNCTION__);
        return false;
    }

    Logger_INFO("Reading %d registers starting from 0x%02X", nReadCount, startRegister);

    nLen = 0;
    txBuff[nLen++] = startRegister;
    res = emc230x_send_then_read(txBuff, nLen, pData, nReadCount);
    return res;
}

static bool emc230x_send(uint8_t *pData, uint16_t nLen)
{
    int status;
    status = i2c_write_timeout_us(PICO_I2C_INSTANCE, i2c_address, pData, nLen, false, I2C_COMM_TIMEOUT);
    if(status)
    {
        Logger_ERROR("%s: Error 0x%02X", __FUNCTION__, status);
        return false;
    }
    return true;
}


static bool emc230x_read(uint8_t *pData, uint16_t nLen)
{
    int status;
    status = i2c_read_timeout_us(PICO_I2C_INSTANCE, i2c_address, pData, nLen, false, I2C_COMM_TIMEOUT);
    if(status)
    {
        Logger_ERROR("%s: Error 0x%02X", __FUNCTION__, status);
        return false;
    }
    return true;
}

static bool emc230x_send_then_read(uint8_t *pTXData, uint16_t nTXLen, uint8_t *pRXData, uint16_t nRXLen)
{
    int status;
    status = i2c_write_timeout_us(PICO_I2C_INSTANCE, i2c_address, pTXData, nTXLen, false, I2C_COMM_TIMEOUT);
    if(status)
    {
        Logger_ERROR("%s: write error 0x%02X", __FUNCTION__, status);
        return false;
    }

    status = i2c_read_timeout_us(PICO_I2C_INSTANCE, i2c_address, pRXData, nRXLen, false, I2C_COMM_TIMEOUT);
    if(status)
    {
        Logger_ERROR("%s: read error 0x%02X", __FUNCTION__, status);
        return false;
    }
    return true;
}
