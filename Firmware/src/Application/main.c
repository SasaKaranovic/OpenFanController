#include <tusb.h>
#include <pico/multicore.h>
#include <hardware/clocks.h>
#include "pico/bootrom.h"
#include "board.h"
#include "fan_control.h"
#include "host_communication.h"
#include "usb_cdc.h"

#define MIN_LOG_LEVEL_DEBUG
#define LOGGER_TAG "MAIN"
#include "logger.h"

#ifndef CFG_NOLED_BLINK
bool led_state = false;
bool systick_callback(repeating_timer_t *rt);
#endif

int main(void)
{
    set_sys_clock_khz(250000, false);
    stdio_init_all();

    gpio_init(LED_PIN);
    gpio_set_dir(LED_PIN, GPIO_OUT);
    gpio_put(LED_PIN, 0);

    i2c_init(PICO_I2C_INSTANCE, 400 * 1000);
    gpio_set_function(PICO_I2C_SDA_PIN, GPIO_FUNC_I2C);
    gpio_set_function(PICO_I2C_SCL_PIN, GPIO_FUNC_I2C);

    fan_control_init();
    host_comm_init();

#ifndef CFG_NOLED_BLINK
    // Setup systick timer
    repeating_timer_t timer;
    // negative timeout means exact delay (rather than delay between callbacks)
    if (!add_repeating_timer_us(-500000, systick_callback, NULL, &timer)) {
        gpio_put(LED_PIN, 1);
        return 1;
    }
#endif

    Logger_INFO("Up and running");

    usbd_serial_init();
    tusb_init();
    while (1) {
        usb_cdc_tick();
        fan_periodic_tick();
        host_comm_tick();
    }

    return 0;
}

#ifndef CFG_NOLED_BLINK
bool systick_callback(repeating_timer_t *rt)
{
    gpio_put(LED_PIN, led_state);
    led_state = !led_state;
    return true; // keep repeating
}
#endif
