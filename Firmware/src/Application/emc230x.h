#ifndef __EMC230X_H__
#define __EMC230X_H__

#include <stdint.h>
#include <stdbool.h>

typedef enum emc230x_fan_rpm_range
{
    RANGE_MIN_500RPM  = 0,
    RANGE_MIN_1000RPM = 1,
    RANGE_MIN_2000RPM = 2,
    RANGE_MIN_4000RPM = 3,
} emc230x_fan_rpm_range_t;

typedef enum emc230x_fan_edges
{
    EDGES_3_1POLE = 0,
    EDGES_5_2POLE = 1,
    EDGES_7_3POLE = 2,
    EDGES_9_4POLE = 3,
} emc230x_fan_edges_t;

void emc230x_init(void);
void emc230x_config_fans(void);
void emc230x_set_address(uint8_t address);
void emc230x_read_fan_rpm(uint8_t channel, uint16_t *pRPM);
void emc230x_set_target_rpm(uint8_t channel, uint16_t nRPM);
void emc230x_set_pwm(uint8_t channel, uint8_t nPWM);
bool emc230x_debug_registers(uint8_t startRegister, uint8_t *pData, uint16_t nReadCount);
void emc230x_set_rpm(uint8_t channel, uint16_t nRPM);
bool emc230x_read_register(uint8_t reg, uint8_t *pData);
bool emc230x_write_register(uint8_t reg, uint8_t Data);

#endif
