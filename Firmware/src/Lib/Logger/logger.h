#ifndef __LIB_LOGGER_H__
#define __LIB_LOGGER_H__

#include <stdio.h>
#include <stdbool.h>
#include <string.h>
#include <stdarg.h>

typedef enum LogLevel_t {
	LOG_TRACE = 0,
	LOG_DEBUG,
	LOG_INFO,
	LOG_WARN,
	LOG_ERROR,
	LOG_FATAL,
	LOG_OFF,
	LOG_LAST
} LogLevel_t;


// If no debug level is defined, default to INFO
#if (!defined(MIN_LOG_LEVEL_TRACE) &&    \
        !defined(MIN_LOG_LEVEL_DEBUG) && \
        !defined(MIN_LOG_LEVEL_INFO) &&  \
        !defined(MIN_LOG_LEVEL_WARN) &&  \
        !defined(MIN_LOG_LEVEL_ERROR) && \
        !defined(MIN_LOG_LEVEL_FATAL) && \
        !defined(MIN_LOG_LEVEL_OFF))
    #define MIN_LOG_LEVEL_INFO	// Default to MIN_LOG_LEVEL_DEBUG
#endif

// Common for all defs
#define Logger_COMMON(level, ...) \
	Logger_Print(LOGGER_TAG, level, __VA_ARGS__)

#define Logger_SHOWBUFFER(buffer, nLen) \
	Logger_PrintBuffer(LOGGER_TAG, LOG_DEBUG, buffer, nLen)


// Various logger levels

// -- Trace
#ifdef MIN_LOG_LEVEL_TRACE
#define MIN_LOG_LEVEL_DEBUG
#define Logger_TRACE(...) Logger_COMMON(LOG_TRACE, __VA_ARGS__)
#else
#define Logger_TRACE(...);
#endif

#ifndef LOGGER_TAG
#define LOGGER_TAG "??"
#endif

// -- Debug
#ifdef MIN_LOG_LEVEL_DEBUG
#define MIN_LOG_LEVEL_INFO
#define Logger_DEBUG(...) Logger_COMMON(LOG_DEBUG, __VA_ARGS__)
#else
#define Logger_DEBUG(...);
#endif

// -- Info
#ifdef MIN_LOG_LEVEL_INFO
#define MIN_LOG_LEVEL_WARN
#define Logger_INFO(...) Logger_COMMON(LOG_INFO, __VA_ARGS__)
#else
#define Logger_INFO(...) ;
#endif

// -- Warn
#ifdef MIN_LOG_LEVEL_WARN
#define MIN_LOG_LEVEL_ERROR
#define Logger_WARN(...) Logger_COMMON(LOG_WARN, __VA_ARGS__)
#else
#define Logger_WARN(...) ;
#endif

// -- Error
#ifdef MIN_LOG_LEVEL_ERROR
#define MIN_LOG_LEVEL_FATAL
#define Logger_ERROR(...) Logger_COMMON(LOG_ERROR, __VA_ARGS__)
#else
#define Logger_ERROR(...);
#endif

// -- Fatal
#ifdef MIN_LOG_LEVEL_FATAL
#define MIN_LOG_LEVEL_DATA
#define Logger_FATAL(...) Logger_COMMON(LOG_FATAL, __VA_ARGS__)
#else
#define Logger_FATAL(...);
#endif


bool Logger_Print(const char* module_tag, LogLevel_t level,
	const char* format, ...)
	__attribute__((format(gnu_printf, 3, 4)));


bool Logger_PrintBuffer(const char* tag, LogLevel_t level, const char* buffer, const char nLen);

#endif
