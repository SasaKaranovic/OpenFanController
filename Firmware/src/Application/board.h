#ifndef __BOARD_INC_H__
#define __BOARD_INC_H__

#include <stdio.h>
#include <stdbool.h>
#include <string.h>
#include <stdio.h>
#include <hardware/irq.h>
#include <hardware/gpio.h>
#include <hardware/structs/sio.h>
#include <hardware/timer.h>
#include <hardware/i2c.h>
#include <pico/stdlib.h>

#define LED_PIN 25

#define PICO_I2C_INSTANCE   i2c1
#define PICO_I2C_SDA_PIN    2
#define PICO_I2C_SCL_PIN    3


static inline uint32_t Board_GetTick(void)
{
    return time_us_32()/1000;
}

#endif /* __BOARD_INC_H__ */
