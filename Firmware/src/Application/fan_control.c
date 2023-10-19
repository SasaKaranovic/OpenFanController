#include "board.h"
#include "emc230x.h"
#include "fan_control.h"

#define MIN_LOG_LEVEL_INFO
#define LOGGER_TAG "FC"
#include "logger.h"

#define FAN_TICK_PERIOD         1000

uint32_t nFanTick = 0;
uint16_t fan_rpm[NUM_TOTAL_FAN] = {0};

// --- NOTE ---
// There are dedicated commands for operations that target all fans
// FANS are split into multiple banks.
// Fan index starts at 0 and ends at NUM_TOTAL_FAN-1.
//  -> Software will deal with converting zero indexed values to one indexed values
//  -> Firmware will deal with mapping logical channels to physical location


// End user and software will use FAN numbers as they appear on the PCB silkscreen (ie. 1-10).
// We call this logical channel number. The firmware will then take that logical number and convert
// it to physical mapping. Reason for this is because we can have multiple controllers that have
// same channels and/or that logical number (ie. FAN3) does not have to be physicall FAN3.
// Hopefully this is clear, but here is also the actual mapping to make things clearer

// Logical Fan Index (zero-indexed)                       1  2  3  4  5  6  7  8  9  10
static const uint8_t fan_controller_map[NUM_TOTAL_FAN] = {0, 0, 0, 0, 0, 1, 1, 1, 1, 1};    // Map fan to controller
static const uint8_t fan_channel_map[NUM_TOTAL_FAN]    = {4, 3, 2, 1, 0, 4, 3, 2, 1, 0};    // Map fan to channel
// Let's take fan index 3 which is this one                     ^
//                                                              |--- > If we read the map, it tells us that our logical
//                                                                     fan #3 is connected to the controller #0
//                                                                     and it's connected to it's channel #2.
//                                                                     In order to controll this fan we need to talk to
//                                                                     controller #0 and set/get channel #2 values.

static void switch_fan_controller_to(uint8_t controller);
static uint8_t map_channel_to_controller(uint8_t channel);



void fan_control_init(void)
{
    Logger_INFO("---Fan Controller---");
    Logger_INFO("Fan Controllers: %d", NUM_CONTROLLERS);
    Logger_INFO("Fans per controller: %d", NUM_FAN_PER_CONTROLLER);
    Logger_INFO("Total fans: %d", NUM_TOTAL_FAN);
    // Initialize each controller
    for (uint8_t i=0; i<NUM_CONTROLLERS; i++)
    {
        switch_fan_controller_to(i);
        emc230x_config_fans();
    }

    // Set all fans to 1k RPM
    for (uint8_t i=0; i<NUM_TOTAL_FAN; i++)
    {
        fan_control_set_fan_rpm(i, 1000);
    }
}

void fan_periodic_tick(void)
{
    if (time_us_32() >= nFanTick)
    {
        // Read RPM of all fans
        for(uint8_t i=0; i<NUM_TOTAL_FAN; i++)
        {
            switch_fan_controller_to(fan_controller_map[i]);
            emc230x_read_fan_rpm(fan_channel_map[i], &fan_rpm[i]);;
        }

        Logger_DEBUG("1:%4d 2:%4d 3:%4d 4:%4d 5:%4d 6:%4d 7:%4d 8:%4d 9:%4d 10:%4d",
                     fan_rpm[0],
                     fan_rpm[1],
                     fan_rpm[2],
                     fan_rpm[3],
                     fan_rpm[4],
                     fan_rpm[5],
                     fan_rpm[6],
                     fan_rpm[7],
                     fan_rpm[8],
                     fan_rpm[9]
                     );

        // uint8_t reg=0;

        // emc230x_read_register(0x25, &reg);
        // Logger_INFO("Fan Stall: 0x%02X", reg);

        // emc230x_read_register(0x26, &reg);
        // Logger_INFO("Fan SPIN: 0x%02X", reg);

        // emc230x_read_register(0x27, &reg);
        // Logger_INFO("Driver Fail: 0x%02X", reg);

        // emc230x_read_register(0x32, &reg);
        // Logger_INFO("Fan 1: 0x%02X", reg);


        nFanTick = time_us_32() + FAN_TICK_PERIOD;
    }
}

void fan_control_read_fan_rpm(uint8_t fan, uint16_t *pRPM)
{
    #if 1
    if(pRPM == NULL)
    {
        Logger_ERROR("%s: Null pointer. Aborting!", __FUNCTION__);
        return;
    }
    if(fan >= NUM_TOTAL_FAN)
    {
        Logger_ERROR("%s: Requested fan index (%d) is out of bounds", __FUNCTION__, fan);
        *pRPM = 0;
        return;
    }

    *pRPM = fan_rpm[fan];

    #else
    fan = map_channel_to_controller(fan);
    emc230x_read_fan_rpm(fan, pRPM);
    Logger_DEBUG("%s: Fan:%d RPM:%d", __FUNCTION__, fan, *pRPM);
    #endif
}

void fan_control_read_all_rpm(uint16_t *pRPM, uint8_t nLen)
{
    if(pRPM == NULL)
    {
        Logger_ERROR("%s: Null pointer! Aborting.", __FUNCTION__);
        return;
    }
    if(nLen > NUM_TOTAL_FAN)
    {
        Logger_ERROR("%s: Requested number of fans (%d) is greater than total number of fans (%d). Clipping.", __FUNCTION__, nLen, NUM_TOTAL_FAN);
        nLen = NUM_TOTAL_FAN;
    }

    for(uint8_t i=0; i<nLen; i++)
    {
        pRPM[i] = fan_rpm[i];
    }
}


void fan_control_set_fan_rpm(uint8_t fan, uint16_t nRPM)
{
    if(fan>=NUM_TOTAL_FAN)
    {
        Logger_ERROR("%s: Requested fan index (%d) is out of bounds", __FUNCTION__, fan);
        return;
    }

    Logger_DEBUG("%s: Fan:%d RPM:%d", __FUNCTION__, fan, nRPM);
    switch_fan_controller_to(fan_controller_map[fan]);
    emc230x_set_target_rpm(fan_channel_map[fan], nRPM);
}

void fan_control_set_fan_pwm(uint8_t fan, uint8_t pwm)
{
    if(pwm>255)
    {
        Logger_ERROR("%s: Requested PWM[%d] > 255. Clipping to 255", __FUNCTION__, pwm);
        pwm = 255;
    }
    if(fan>=NUM_TOTAL_FAN)
    {
        Logger_ERROR("%s: Requested fan index (%d) is out of bounds", __FUNCTION__, fan);
        return;
    }

    Logger_DEBUG("%s: Fan:%d PWM:%d", __FUNCTION__, fan, pwm);
    switch_fan_controller_to(fan_controller_map[fan]);
    emc230x_set_pwm(fan_channel_map[fan], pwm);
}

void fan_control_set_all_pwm(uint8_t pwm)
{
    if(pwm>255)
    {
        Logger_ERROR("%s: Requested PWM[%d] > 255. Clipping to 255", __FUNCTION__, pwm);
        pwm = 255;
    }

    Logger_DEBUG("%s: Setting ALL fans to PWM:%d", __FUNCTION__, pwm);
    // We are setting all fans to same value so channel/controller mapping is irrelevant
    for(uint8_t controller=0; controller<NUM_CONTROLLERS; controller++)
    {
        for(uint8_t fan=0; fan<NUM_FAN_PER_CONTROLLER; fan++)
        {
            switch_fan_controller_to(controller);
            emc230x_set_pwm(fan, pwm);
        }
    }
}

static void switch_fan_controller_to(uint8_t controller)
{
    if(controller==0)
    {
        emc230x_set_address(EMC_CTRL_1_ADDRESS);
    }
    else if(controller==1)
    {
        emc230x_set_address(EMC_CTRL_2_ADDRESS);
    }
    else
    {
        Logger_ERROR("%s: Unknown or unsupported controller!", __FUNCTION__);
    }
}

#if 0
//
static uint8_t map_channel_to_controller(uint8_t channel)
{
    switch(channel)
    {
        case 1:
            emc230x_set_address(EMC_CTRL_1_ADDRESS);
            return 4;
            break;

        case 2:
            emc230x_set_address(EMC_CTRL_1_ADDRESS);
            return 3;
            break;

        case 3:
            emc230x_set_address(EMC_CTRL_1_ADDRESS);
            return 2;
            break;

        case 4:
            emc230x_set_address(EMC_CTRL_1_ADDRESS);
            return 1;
            break;

        case 5:
            emc230x_set_address(EMC_CTRL_1_ADDRESS);
            return 0;
            break;


        case 6:
            emc230x_set_address(EMC_CTRL_2_ADDRESS);
            return 4;
            break;

        case 7:
            emc230x_set_address(EMC_CTRL_2_ADDRESS);
            return 3;
            break;

        case 8:
            emc230x_set_address(EMC_CTRL_2_ADDRESS);
            return 2;
            break;

        case 9:
            emc230x_set_address(EMC_CTRL_2_ADDRESS);
            return 1;
            break;

        case 10:
            emc230x_set_address(EMC_CTRL_2_ADDRESS);
            return 0;
            break;

        default:
            Logger_ERROR("Unknown FAN location.");
            emc230x_set_address(EMC_CTRL_1_ADDRESS);
            return 0;
            break;

    }

}
#endif
