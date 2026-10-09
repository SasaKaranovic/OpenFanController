/**
 * @file flash_eeprom.h
 * @brief EEPROM emulation in the external QSPI flash of RP2040 / RP2350.
 *
 * The emulated EEPROM is a fixed-size byte array whose size is set at compile
 * time. A RAM mirror holds the current contents, so reads never touch flash.
 * Every write that changes data stores a complete new copy ("slot") of the
 * EEPROM in the next free location of a dedicated flash region:
 *
 *   region  = N erase units (EU), N >= 2
 *   EU      = one flash sector, or several sectors if one slot does not fit
 *   slot    = 16-byte header + EEPROM data, rounded up to a flash page
 *
 * Slots are written round-robin across the whole region, so each sector is
 * erased only once every (slots per EU) writes. The newest valid slot is
 * found at init by a sequence number and verified with a CRC32, so a power
 * failure during a write leaves the previous contents intact.
 *
 * Configuration (define on the compiler command line so the library and the
 * application see the same values, e.g. target_compile_definitions in CMake):
 *
 *   FLASH_EEPROM_SIZE             EEPROM size in bytes             (default 32)
 *   FLASH_EEPROM_REGION_SIZE      flash bytes reserved, a multiple of the
 *                                 erase unit, at least 2 of them   (default 2 EU)
 *   FLASH_EEPROM_FLASH_OFFSET     region start, as an offset from the start of
 *                                 flash, sector aligned            (default: end of flash)
 *   FLASH_EEPROM_LOCKOUT_TIMEOUT_MS  timeout for flash_safe_execute (default 1000)
 *
 * Wear estimate: writes before wear-out ~= flash endurance (typically 100k
 * erase cycles) x total number of slots in the region. Increase
 * FLASH_EEPROM_REGION_SIZE to get more slots.
 *
 * Requirements: link with pico_flash and hardware_flash.
 *
 * Multicore: when pico_multicore is linked and core 1 has been launched, the
 * core that does NOT call flash_eeprom_write() must call
 * flash_safe_execute_core_init() once (e.g. first line of core1's entry
 * function; if writes are made from core 1, core 0 must call it instead).
 * multicore_launch_core1() does NOT do this for you; without it every write
 * fails with FLASH_EEPROM_ERR_LOCKOUT after waiting the lockout timeout.
 * That core must also not sit with interrupts disabled for long, or writes
 * fail with FLASH_EEPROM_ERR_TIMEOUT.
 *
 * FreeRTOS: SMP builds need no extra step. Non-SMP FreeRTOS on RP2040 with
 * pico_multicore linked is not supported by flash_safe_execute (always
 * FLASH_EEPROM_ERR_LOCKOUT) unless PICO_FLASH_ASSUME_CORE1_SAFE /
 * PICO_FLASH_ASSUME_CORE0_SAFE is defined.
 *
 * The functions are not reentrant; protect them with a mutex if they are
 * called from more than one thread/core.
 */
#ifndef FLASH_EEPROM_H
#define FLASH_EEPROM_H

#include <stddef.h>
#include <stdint.h>
#include "hardware/flash.h" /* FLASH_SECTOR_SIZE, FLASH_PAGE_SIZE */

#ifdef __cplusplus
extern "C" {
#endif

/* ------------------------------------------------------------------------- */
/* User configuration                                                         */
/* ------------------------------------------------------------------------- */

#ifndef FLASH_EEPROM_SIZE
#define FLASH_EEPROM_SIZE 64u
#endif

#ifndef FLASH_EEPROM_LOCKOUT_TIMEOUT_MS
#define FLASH_EEPROM_LOCKOUT_TIMEOUT_MS 1000u
#endif

/* ------------------------------------------------------------------------- */
/* Derived layout (computed from the configuration, do not edit)              */
/* ------------------------------------------------------------------------- */

#define FLASH_EEPROM_HEADER_SIZE 16u
#define FLASH_EEPROM_ROUND_UP(x, a) ((((x) + (a) - 1u) / (a)) * (a))

/** Bytes actually programmed per slot (header + data, page aligned). */
#define FLASH_EEPROM_SLOT_PROG_SIZE \
    FLASH_EEPROM_ROUND_UP(FLASH_EEPROM_HEADER_SIZE + FLASH_EEPROM_SIZE, FLASH_PAGE_SIZE)

/** Erase unit: one sector, or as many sectors as one slot needs. */
#define FLASH_EEPROM_ERASE_UNIT                                  \
    ((FLASH_EEPROM_SLOT_PROG_SIZE <= FLASH_SECTOR_SIZE)          \
         ? FLASH_SECTOR_SIZE                                     \
         : FLASH_EEPROM_ROUND_UP(FLASH_EEPROM_SLOT_PROG_SIZE, FLASH_SECTOR_SIZE))

/** Address stride between slots. */
#define FLASH_EEPROM_SLOT_STRIDE                                 \
    ((FLASH_EEPROM_SLOT_PROG_SIZE <= FLASH_SECTOR_SIZE)          \
         ? FLASH_EEPROM_SLOT_PROG_SIZE                           \
         : FLASH_EEPROM_ERASE_UNIT)

#ifndef FLASH_EEPROM_REGION_SIZE
#define FLASH_EEPROM_REGION_SIZE (2u * FLASH_EEPROM_ERASE_UNIT)
#endif

#ifndef FLASH_EEPROM_FLASH_OFFSET
#define FLASH_EEPROM_FLASH_OFFSET (PICO_FLASH_SIZE_BYTES - FLASH_EEPROM_REGION_SIZE)
#endif

/* ------------------------------------------------------------------------- */
/* API                                                                        */
/* ------------------------------------------------------------------------- */

typedef enum {
    FLASH_EEPROM_OK             =  0,
    FLASH_EEPROM_ERR_PARAM      = -1, /**< NULL buffer or address/length out of range */
    FLASH_EEPROM_ERR_NOT_INIT   = -2, /**< flash_eeprom_init() not called / failed */
    FLASH_EEPROM_ERR_FLASH      = -3, /**< data read back after programming did not match */
    FLASH_EEPROM_ERR_LAYOUT     = -4, /**< region overlaps the program image */
    FLASH_EEPROM_ERR_LOCKOUT    = -5, /**< other core not set up for flash_safe_execute (see above) */
    FLASH_EEPROM_ERR_TIMEOUT    = -6, /**< other core did not pause within the lockout timeout */
} flash_eeprom_status_t;

/**
 * Initialise the library: validate the flash layout, scan the region for the
 * newest valid copy and load it into RAM. If none exists (blank flash, or the
 * EEPROM size changed), the EEPROM reads as all 0xFF until the first write.
 */
flash_eeprom_status_t flash_eeprom_init(void);

/** Read @p len bytes starting at EEPROM address @p addr into @p buf. */
flash_eeprom_status_t flash_eeprom_read(uint32_t addr, void *buf, size_t len);

/**
 * Write @p len bytes from @p buf starting at EEPROM address @p addr.
 * The data is committed to flash before the function returns. Writes that do
 * not change the contents do not touch flash. Interrupts are disabled and the
 * other core is paused while flash is programmed/erased.
 */
flash_eeprom_status_t flash_eeprom_write(uint32_t addr, const void *buf, size_t len);

#ifdef __cplusplus
}
#endif

#endif /* FLASH_EEPROM_H */
