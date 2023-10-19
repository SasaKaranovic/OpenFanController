#include "pico/bootrom.h"
#include "host_communication.h"
#include "usb_cdc.h"
#include "fan_control.h"
#include "emc230x.h"

#define MIN_LOG_LEVEL_DEBUG
#define LOGGER_TAG "HCOMM"
#include "logger.h"

// ---- TODO ---
//
// 1. Communication is ASCII only, so we could use non-ASCII characters to indicate start and end of package
//

uint8_t pTxBuffer[COMM_TX_BUFFER_LEN] = {0};
uint32_t nTxBufferLen = 1;
uint8_t pRxBuffer[COMM_RX_ASCII_BUFFER_LEN] = {0};
uint32_t nRxBufferLen = 0;
uint8_t pPackage[COMM_RX_HEX_BUFFER_LEN] = {0};
uint32_t nPackageLen = 0;
bool bRxStarted = false;
bool bRxComplete = false;

static void host_comm_send_response(void);
static void host_comm_rearm(void);
static uint8_t buffer_to_uint8(uint8_t *pBuffer);
static uint8_t ascii_to_hex(uint8_t ascii);
static bool ascii_array_to_hex_array(uint8_t *pASCII, uint32_t nLen, uint8_t *pHex, uint32_t *nHexLen);
static void response_add_data(uint8_t *pData, uint32_t nLen);
static void response_add_byte(uint8_t data);
static void response_add_u32(uint32_t data);
static void response_add_u16(uint16_t data);
static void response_add_str(const char *pStr);
static void response_add_chr(char data);
static void jump_to_bootloader(void);

void host_comm_init(void)
{

}

void host_comm_process_request(comm_cmd_t cmd, uint8_t *pData, uint32_t nDataLen)
{
    uint16_t rpm = 0;
    pTxBuffer[0] = COMM_RESPONSE_CHARACTER;
    nTxBufferLen = 1;
    response_add_byte(cmd);
    response_add_chr('|');

    switch (cmd)
    {
        case CMD_FAN_ALL_GET_RPM:
            Logger_DEBUG("CMD_FAN_ALL_GET_RPM");
            for(uint8_t i=0; i<NUM_TOTAL_FAN; i++)
            {
                rpm=0;
                fan_control_read_fan_rpm(i, &rpm);
                response_add_byte(i);
                response_add_chr(':');
                response_add_u16(rpm);
                if(i<NUM_TOTAL_FAN)
                {
                    response_add_chr(';');
                }
            }
            break;

        case CMD_FAN_GET_RPM:
            Logger_DEBUG("CMD_FAN_GET_RPM");
            rpm=0;
            fan_control_read_fan_rpm(pData[0], &rpm);
            response_add_byte(pData[0]);
            response_add_chr(':');
            response_add_u16(rpm);
            break;

        case CMD_FAN_SET_PWM:
            Logger_DEBUG("CMD_FAN_SET_PWM");
            fan_control_set_fan_pwm(pData[0], pData[1]);
            response_add_byte(pData[0]);
            response_add_chr(':');
            response_add_byte(pData[1]);
            break;

        case CMD_FAN_SET_ALL_PWM:
            Logger_DEBUG("CMD_FAN_SET_PWM");
            fan_control_set_all_pwm(pData[0]);
            response_add_byte(pData[0]);
            break;

        case CMD_FAN_SET_RPM:
            rpm = (pData[1]<<8) | pData[2];
            Logger_DEBUG("CMD_FAN_SET_RPM");
            fan_control_set_fan_rpm(pData[0], rpm);
            response_add_byte(pData[0]);
            response_add_chr(':');
            response_add_byte(pData[1]);
            response_add_byte(pData[2]);
            break;

        case CMD_HW_INFO:
            Logger_DEBUG("CMD_HW_INFO");
            response_add_str("\r\n");
            response_add_str("HW_REV:03\r\n");
            response_add_str("MCU:PICO2040\r\n");
            response_add_str("USB:NATIVE\r\n");
            response_add_str("FAN_CHANNELS_TOTAL:10\r\n");
            response_add_str("FAN_CHANNELS_ARCH:5+5\r\n");
            response_add_str("FAN_CHANNELS_DRIVER:EMC2305\r\n");
            break;

        case CMD_FW_INFO:
            Logger_DEBUG("CMD_SW_INFO");
            response_add_str("FW_REV:01\r\n");
            response_add_str("PROTOCOL_VERSION:01\r\n");
            break;

        // --- Debug Commands. These should be disabled in release version
        case CMD_EMC_DEBUG_REG:
            Logger_DEBUG("CMD_EMC_DEBUG_REG");
            bool res;
            uint8_t read_buff[256] = {0};
            uint16_t read_len = pData[1];

            res = emc230x_debug_registers(pData[0], read_buff, read_len);
            if(!res)
            {
                Logger_ERROR("%s: emc230x_debug_registers failed.", __FUNCTION__);
                response_add_str("emc230x_debug_registers failed.");
            }
            else
            {
                for(uint16_t i=0; i<read_len; i++)
                {
                    response_add_byte( pData[0]+i );
                    response_add_chr('=');
                    response_add_byte(read_buff[i]);
                    response_add_chr('\r');
                }
            }

            break;

        case CMD_EMC_READ_REG:
            Logger_DEBUG("CMD_EMC_READ_REG");
            uint8_t reg = 0;
            emc230x_read_register(pData[0], &reg);
            response_add_byte(reg);
            break;

        case CMD_EMC_WRITE_REG:
            Logger_DEBUG("CMD_EMC_WRITE_REG");
            emc230x_write_register(pData[0], pData[1]);
            response_add_str("OK");
            break;

        case CMD_JUMP_TO_BOOTLOADER:
            Logger_DEBUG("CMD_JUMP_TO_BOOTLOADER");
            jump_to_bootloader();
            break;


        default:
            Logger_ERROR("%s: Unsupported or invalid command", __FUNCTION__);
    }

    host_comm_send_response();
}

static void host_comm_send_response(void)
{
    pTxBuffer[nTxBufferLen++] = '\r';
    pTxBuffer[nTxBufferLen++] = '\n';
    usb_cdc_send_arr(pTxBuffer, nTxBufferLen);

    memset(pTxBuffer, '\0', COMM_TX_BUFFER_LEN);
    nTxBufferLen = 0;
}

void host_comm_receive_data(uint8_t *pData, uint32_t nDataLen)
{
    if (pData == NULL)
    {
        return;
    }

    // We already received a package and parse is pending
    if (bRxComplete)
    {
        return;
    }

    // Receive data
    for (uint32_t i=0; i<nDataLen; i++)
    {
        if (( (pData[i] == COMM_END_CHARACTER) || (pData[i] == COMM_ALT_END_CHARACTER)) && (!bRxComplete))
        {
            bRxComplete = true;
            nRxBufferLen = i;
            return;
        }
        else
        {
            pRxBuffer[i] = pData[i];
        }

    }
}

void host_comm_parse_package(uint8_t *pPackageStart, uint32_t nLen)
{
    Logger_DEBUG("%s", __FUNCTION__);

    // Convert entire array from ASCII to raw values
    if (ascii_array_to_hex_array(pPackageStart, nLen, pPackage, &nPackageLen))
    {
        host_comm_process_request(pPackage[0], &pPackage[1], nPackageLen-1);
    }
}



void host_comm_tick(void)
{
    bool bValidMsg = false;

    if (bRxComplete)
    {
        Logger_INFO("%s", pRxBuffer);

        if(nRxBufferLen < COMM_MIN_MESSAGE_LEN)
        {
            Logger_ERROR("%s: Invalid message lenght (%ld<%d)", __FUNCTION__, nRxBufferLen, COMM_MIN_MESSAGE_LEN);
            host_comm_rearm();
            return;
        }

        // Search for start character
        for(uint32_t i=0; i<nRxBufferLen; i++)
        {
            if(pRxBuffer[i] == COMM_START_CHARACTER)
            {
                Logger_DEBUG("%s: Start character found (Len=%ld)", __FUNCTION__, nRxBufferLen-i-1);
                host_comm_parse_package(&pRxBuffer[i+1], nRxBufferLen-i-1);
                bValidMsg = true;
                break;
            }
        }

        if(!bValidMsg)
        {
            Logger_ERROR("%s: No start character found. Ignoring package.", __FUNCTION__);
        }

        host_comm_rearm();
        return;
    }
}


static void host_comm_rearm(void)
{
    memset(pRxBuffer, '\0', COMM_RX_ASCII_BUFFER_LEN);
    memset(pPackage, '\0', COMM_RX_HEX_BUFFER_LEN);
    nRxBufferLen = 0;
    nPackageLen = 0;
    bRxComplete = false;
}

static uint8_t buffer_to_uint8(uint8_t *pBuffer)
{
    if(pBuffer==NULL)
    {
        Logger_ERROR("%s Invalid pointer!", __FUNCTION__);
        return 0;
    }

    uint8_t upper = ascii_to_hex(pBuffer[0]);
    uint8_t lower = ascii_to_hex(pBuffer[1]);

    return (upper<<4) | lower;
}

// Convert ASCII HEX character 0-9 or A-F to HEX value
static uint8_t ascii_to_hex(uint8_t ascii)
{

    if( (ascii>='0') && (ascii<='9') )
    {
        return ascii - '0';
    }
    else if ( (ascii >= 'A') && (ascii <= 'F') )
    {
        return ascii - 'A' + 10;
    }
    else if ( (ascii >= 'a') && (ascii <= 'f') )
    {
        return ascii - 'a' + 10;
    }
    else
    {
        Logger_ERROR("%s:%d Invalid character! (%c - 0x%02X)", __FUNCTION__, __LINE__, ascii, ascii);
        return 0;
    }
}

// Convert ASCII HEX array to HEX array
// This function will rewrite an ASCII HEX array (2 characters per byte) to hex array (1 byte per byte)
// The resulting array will be half the size and contain RAW HEX values
static bool ascii_array_to_hex_array(uint8_t *pASCII, uint32_t nLen, uint8_t *pTarget, uint32_t *nHexLen)
{
    if(pASCII==NULL)
    {
        Logger_ERROR("%s Invalid pointer!", __FUNCTION__);
        return false;
    }

    if(nLen<=0)
    {
        Logger_ERROR("%s:%d Invalid buffer length (%ld)", __FUNCTION__, __LINE__, nLen);
        return false;
    }

    uint8_t raw = 0;
    uint32_t raw_pos = 0;

    // Lenght is converted from USART ASCII package
    // so we need to multiply it by 2 to account for
    // ASCII values (2 byte)
    for (uint32_t i=0; i<nLen; i+=2)
    {
        // Convert ASCII bytes ie. FA to raw hex
        raw = (ascii_to_hex(pASCII[i]) << 4);
        raw |= ascii_to_hex(pASCII[i+1]);

        Logger_DEBUG("A=%c%c H:0x%02X", pASCII[i], pASCII[i+1], raw);

        // Finally update raw byte
        pTarget[raw_pos++] = raw;
    }

    *nHexLen = raw_pos;
    return true;
}


static void response_add_data(uint8_t *pData, uint32_t nLen)
{
    if(pData==NULL)
    {
        Logger_ERROR("%s Invalid pointer!", __FUNCTION__);
        return;
    }

    for(uint32_t i=0; i<nLen; i++)
    {
        response_add_byte(pData[i]);
    }
}

static void response_add_byte(uint8_t data)
{
    sprintf((char *)&pTxBuffer[nTxBufferLen], "%02X", data);
    nTxBufferLen += 2;
}

static void response_add_u32(uint32_t data)
{
    sprintf((char *)&pTxBuffer[nTxBufferLen], "%08lX", data);
    nTxBufferLen += 8;
}

static void response_add_u16(uint16_t data)
{
    sprintf((char *)&pTxBuffer[nTxBufferLen], "%04X", data);
    nTxBufferLen += 4;
}

static void response_add_str(const char *pStr)
{
    uint32_t nLen = strlen(pStr);
    strncpy((char *)&pTxBuffer[nTxBufferLen], pStr, nLen);
    nTxBufferLen += nLen;
}

static void response_add_chr(char data)
{
    pTxBuffer[nTxBufferLen++] = data;
}



static void jump_to_bootloader(void)
{
    reset_usb_boot(0, 0);
}
