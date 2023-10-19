#ifndef __HOST_COMMUNICATION_INC_H__
#define __HOST_COMMUNICATION_INC_H__

#include <stdint.h>
#include <stdbool.h>

#define COMM_START_CHARACTER        '>'
#define COMM_END_CHARACTER          '\n'
#define COMM_ALT_END_CHARACTER      '\r'
#define COMM_MIN_MESSAGE_LEN        3
#define COMM_RESPONSE_CHARACTER     '<'
#define COMM_RX_ASCII_BUFFER_LEN    128
#define COMM_RX_HEX_BUFFER_LEN      COMM_RX_ASCII_BUFFER_LEN/2 - 1
#define COMM_TX_BUFFER_LEN          128

#define COMM_PROTOCOL_VERSION       1

typedef enum comm_cmd
{
    CMD_FIRST,
    CMD_FAN_ALL_GET_RPM     = 0x00,
    CMD_FAN_GET_RPM         = 0x01,
    CMD_FAN_SET_PWM         = 0x02,
    CMD_FAN_SET_ALL_PWM     = 0x03,
    CMD_FAN_SET_RPM         = 0x04,
    CMD_HW_INFO             = 0x05,
    CMD_FW_INFO             = 0x06,
    CMD_JUMP_TO_BOOTLOADER  = 0x07,

    // FIXME: These are debug functions
    // They can be at the same time useful and dangerous in production
    CMD_EMC_DEBUG_REG       = 0x08,
    CMD_EMC_READ_REG        = 0x09,
    CMD_EMC_WRITE_REG       = 0x0A,
    CMD_LAST                = CMD_EMC_WRITE_REG,
} comm_cmd_t;



void host_comm_init(void);
void host_comm_process_request(comm_cmd_t cmd, uint8_t *pData, uint32_t nDataLen);
void host_comm_parse_package(uint8_t *pPackageStart, uint32_t nLen);
void host_comm_receive_data(uint8_t *pData, uint32_t nDataLen);
void host_comm_tick(void);

#endif /* __HOST_COMMUNICATION_INC_H__ */
