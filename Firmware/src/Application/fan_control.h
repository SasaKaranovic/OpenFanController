#ifndef __FAN_CONTROL_INC_H__
#define __FAN_CONTROL_INC_H__

#define NUM_FAN_PER_CONTROLLER  5
#define NUM_CONTROLLERS         2
#define NUM_TOTAL_FAN           (NUM_FAN_PER_CONTROLLER*NUM_CONTROLLERS)

#define EMC_CTRL_1_ADDRESS  0x2C
#define EMC_CTRL_1_FAN_CNT  5

#define EMC_CTRL_2_ADDRESS  0x2D
#define EMC_CTRL_2_FAN_CNT  5

void fan_control_init(void);
void fan_periodic_tick(void);
void fan_control_read_fan_rpm(uint8_t fan, uint16_t *pRPM);
void fan_control_read_all_rpm(uint16_t *pRPM, uint8_t nLen);
void fan_control_set_fan_rpm(uint8_t fan, uint16_t nRPM);
void fan_control_set_fan_pwm(uint8_t fan, uint8_t pwm);
void fan_control_set_all_pwm(uint8_t pwm);

#endif /* __FAN_CONTROL_INC_H__ */
