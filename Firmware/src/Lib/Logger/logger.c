// Project includes
#include "logger.h"

// Define uart function that takes char buffer and buffer lenght
#ifndef LOGGER_SEND_STR
#include "usb_cdc.h"
#define LOGGER_SEND_STR    usb_cdc_send_arr
#endif

// Define uart function that returns sys tick
#ifndef LOGGER_SYS_TICK
#include <hardware/timer.h>
#define LOGGER_SYS_TICK    time_us_32
#endif

static const char LogLevels[LOG_LAST] = {'T', 'D', 'I', 'W', 'E', 'F', 'O'};


//Static functions
static uint32_t Log_CreateHeader(const char *tag, LogLevel_t level);


#define LOG_BUFFER_MAX_LEN  250
char gLogBuffer[LOG_BUFFER_MAX_LEN] = {0};


bool Logger_Print(const char* tag, LogLevel_t level, const char* format, ...)
{
    int32_t hlen = 0;
    int32_t mlen = 0;
    int32_t total_len = 0;

    // todo... Check Log level
    hlen = Log_CreateHeader(tag, level);


    // Create log message
    va_list arglist;
    va_start(arglist, format);
    // append the body.
    mlen = vsnprintf(&gLogBuffer[hlen], LOG_BUFFER_MAX_LEN - hlen, format, arglist);
    va_end(arglist);
    if (mlen <= 0)
    {
        return false;
    }


    // Calculate total lenght and check for overflow
    if(mlen + hlen >= LOG_BUFFER_MAX_LEN)
    {
        total_len = LOG_BUFFER_MAX_LEN;
    }
    else
    {
        total_len = mlen+hlen;
        gLogBuffer[total_len++] = '\r';
        gLogBuffer[total_len++] = '\n';
    }

    LOGGER_SEND_STR((uint8_t *)gLogBuffer, total_len);

    return true;
}

bool Logger_PrintBuffer(const char* tag, LogLevel_t level, const char* buffer, const char nLen)
{
    int32_t mlen = 0;
    int32_t snplen = 0;
    int32_t bpos = 0;
    int32_t total_len = 0;

    // todo... Check Log level
    mlen = Log_CreateHeader(tag, level);
    bpos = mlen;

    for (char i=0; i<nLen; i++)
    {
        snplen = snprintf(&gLogBuffer[bpos], (LOG_BUFFER_MAX_LEN - mlen), "0x%02X ", buffer[i]);
        if(snplen <=0)
        {
            return false;
        }
        
        bpos += snplen;
        mlen += snplen;
    }

    // Calculate total lenght and check for overflow
    if(mlen >= LOG_BUFFER_MAX_LEN)
    {
        total_len = LOG_BUFFER_MAX_LEN;
    }
    else
    {
        total_len = mlen;
    }

    LOGGER_SEND_STR((uint8_t *)gLogBuffer, total_len);
    LOGGER_SEND_STR((uint8_t *)"\r\n", 2);

    return true;
}


static uint32_t Log_CreateHeader(const char *tag, LogLevel_t level)
{
    int32_t len = 0;

    len = snprintf(gLogBuffer, LOG_BUFFER_MAX_LEN-1, "[%010lu][%c][%s] ", (LOGGER_SYS_TICK()/1000), LogLevels[level], tag);

    if(len < 0)
    {
        return 0;
    }

    return len;
}
