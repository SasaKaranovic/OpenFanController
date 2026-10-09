/**
 * @file flash_eeprom.c
 * @brief EEPROM emulation with wear leveling for RP2040 / RP2350.
 *
 * Device-specific details come from the Pico SDK (FLASH_SECTOR_SIZE,
 * FLASH_PAGE_SIZE, PICO_FLASH_SIZE_BYTES, XIP_BASE, flash_range_* and
 * flash_safe_execute), so the same source builds for both chips.
 *
 * Note for RP2350: data is read back through XIP_BASE + offset. If the
 * application runs from a partition with address translation enabled, make
 * sure the EEPROM region is reachable at that address (or keep the default
 * layout, where the image starts at the beginning of flash).
 */
#include "flash_eeprom.h"

#include <stdbool.h>
#include <string.h>

#include "pico.h"
#include "pico/flash.h"            /* flash_safe_execute */
#include "pico/time.h"             /* make_timeout_time_ms, time_reached */
#include "hardware/flash.h"        /* flash_range_erase / flash_range_program */
#include "hardware/regs/addressmap.h" /* XIP_BASE */

/* ------------------------------------------------------------------------- */
/* Layout                                                                     */
/* ------------------------------------------------------------------------- */

#define SLOTS_PER_EU (FLASH_EEPROM_ERASE_UNIT / FLASH_EEPROM_SLOT_STRIDE)
#define NUM_EU       (FLASH_EEPROM_REGION_SIZE / FLASH_EEPROM_ERASE_UNIT)
#define TOTAL_SLOTS  (NUM_EU * SLOTS_PER_EU)

#define SLOT_MAGIC   0x45455046u /* "FPEE" */

_Static_assert(FLASH_EEPROM_SIZE > 0u, "FLASH_EEPROM_SIZE must be > 0");
_Static_assert((FLASH_EEPROM_FLASH_OFFSET % FLASH_SECTOR_SIZE) == 0u,
               "FLASH_EEPROM_FLASH_OFFSET must be sector aligned");
_Static_assert((FLASH_EEPROM_REGION_SIZE % FLASH_EEPROM_ERASE_UNIT) == 0u,
               "FLASH_EEPROM_REGION_SIZE must be a multiple of the erase unit");
_Static_assert(NUM_EU >= 2u,
               "FLASH_EEPROM_REGION_SIZE must hold at least two erase units "
               "(needed so the last good copy survives an erase)");
#ifdef PICO_FLASH_SIZE_BYTES
_Static_assert((uint64_t)FLASH_EEPROM_FLASH_OFFSET + FLASH_EEPROM_REGION_SIZE
                   <= (uint64_t)PICO_FLASH_SIZE_BYTES,
               "EEPROM region extends past the end of flash");
#endif

typedef struct {
    uint32_t magic;
    uint32_t seq;    /* incremented on every commit, wrap-safe comparison */
    uint32_t length; /* FLASH_EEPROM_SIZE at the time of writing */
    uint32_t crc;    /* CRC32 over seq, length and data */
} slot_header_t;

_Static_assert(sizeof(slot_header_t) == FLASH_EEPROM_HEADER_SIZE, "header size");

/* ------------------------------------------------------------------------- */
/* State                                                                      */
/* ------------------------------------------------------------------------- */

static uint8_t  s_mirror[FLASH_EEPROM_SIZE];  /* current EEPROM contents */
static uint8_t  s_page_buf[FLASH_PAGE_SIZE];  /* RAM source for programming */
static bool     s_initialised;
static bool     s_have_valid;                 /* a valid slot exists in flash */
static uint32_t s_cur_slot;                   /* index of newest valid slot */
static uint32_t s_seq;                        /* its sequence number */

/* ------------------------------------------------------------------------- */
/* Helpers                                                                    */
/* ------------------------------------------------------------------------- */

static uint32_t crc32_update(uint32_t crc, const uint8_t *p, size_t n) {
    static const uint32_t tbl[16] = {
        0x00000000u, 0x1DB71064u, 0x3B6E20C8u, 0x26D930ACu,
        0x76DC4190u, 0x6B6B51F4u, 0x4DB26158u, 0x5005713Cu,
        0xEDB88320u, 0xF00F9344u, 0xD6D6A3E8u, 0xCB61B38Cu,
        0x9B64C2B0u, 0x86D3D2D4u, 0xA00AE278u, 0xBDBDF21Cu,
    };
    while (n--) {
        crc ^= *p++;
        crc = (crc >> 4) ^ tbl[crc & 0x0Fu];
        crc = (crc >> 4) ^ tbl[crc & 0x0Fu];
    }
    return crc;
}

static uint32_t slot_crc(uint32_t seq, uint32_t length, const uint8_t *data) {
    uint32_t crc = 0xFFFFFFFFu;
    crc = crc32_update(crc, (const uint8_t *)&seq, sizeof seq);
    crc = crc32_update(crc, (const uint8_t *)&length, sizeof length);
    crc = crc32_update(crc, data, FLASH_EEPROM_SIZE);
    return ~crc;
}

/** Flash offset (from start of flash) of a slot. */
static inline uint32_t slot_offset(uint32_t slot) {
    return FLASH_EEPROM_FLASH_OFFSET
         + (slot / SLOTS_PER_EU) * FLASH_EEPROM_ERASE_UNIT
         + (slot % SLOTS_PER_EU) * FLASH_EEPROM_SLOT_STRIDE;
}

/** Memory-mapped (XIP) pointer to a slot. */
static inline const uint8_t *slot_ptr(uint32_t slot) {
    return (const uint8_t *)(uintptr_t)(XIP_BASE + slot_offset(slot));
}

/** True if the slot holds a complete, CRC-valid copy of the current size. */
static bool slot_is_valid(uint32_t slot, uint32_t *seq_out) {
    const uint8_t *p = slot_ptr(slot);
    slot_header_t h;
    memcpy(&h, p, sizeof h);
    if (h.magic != SLOT_MAGIC || h.length != FLASH_EEPROM_SIZE) {
        return false;
    }
    if (slot_crc(h.seq, h.length, p + FLASH_EEPROM_HEADER_SIZE) != h.crc) {
        return false;
    }
    *seq_out = h.seq;
    return true;
}

/** True if every byte that would be programmed in the slot is erased. */
static bool slot_is_blank(uint32_t slot) {
    const uint32_t *p = (const uint32_t *)slot_ptr(slot);
    for (uint32_t i = 0; i < FLASH_EEPROM_SLOT_PROG_SIZE / 4u; i++) {
        if (p[i] != 0xFFFFFFFFu) {
            return false;
        }
    }
    return true;
}

/** Load the mirror from the newest valid slot, or 0xFF if there is none. */
static void reload_mirror(void) {
    if (s_have_valid) {
        memcpy(s_mirror, slot_ptr(s_cur_slot) + FLASH_EEPROM_HEADER_SIZE, FLASH_EEPROM_SIZE);
    } else {
        memset(s_mirror, 0xFF, sizeof s_mirror);
    }
}

/* ------------------------------------------------------------------------- */
/* Flash operation (runs with interrupts off and the other core locked out)   */
/* ------------------------------------------------------------------------- */

typedef struct {
    uint32_t             slot;
    bool                 erase;
    const slot_header_t *hdr;
} flash_op_t;

/** Byte @p pos of the serialised slot image: header | data | 0xFF padding. */
static inline uint8_t image_byte(const slot_header_t *hdr, uint32_t pos) {
    if (pos < FLASH_EEPROM_HEADER_SIZE) {
        return ((const uint8_t *)hdr)[pos];
    }
    pos -= FLASH_EEPROM_HEADER_SIZE;
    return (pos < FLASH_EEPROM_SIZE) ? s_mirror[pos] : 0xFFu;
}

static void flash_op(void *param) {
    const flash_op_t *op = (const flash_op_t *)param;
    const uint32_t base = slot_offset(op->slot);

    if (op->erase) {
        flash_range_erase(base, FLASH_EEPROM_ERASE_UNIT);
    }

    /* Program pages last-to-first so the header page goes in last: a slot
     * interrupted mid-write never has a header in front of missing data. */
    const uint32_t pages = FLASH_EEPROM_SLOT_PROG_SIZE / FLASH_PAGE_SIZE;
    for (uint32_t pg = pages; pg-- > 0u;) {
        const uint32_t pos = pg * FLASH_PAGE_SIZE;
        for (uint32_t i = 0; i < FLASH_PAGE_SIZE; i++) {
            s_page_buf[i] = image_byte(op->hdr, pos + i);
        }
        flash_range_program(base + pos, s_page_buf, FLASH_PAGE_SIZE);
    }
}

/**
 * Run the flash operation with the other core paused.
 *
 * flash_safe_execute() returns PICO_ERROR_NOT_PERMITTED while the other core
 * is running but has not (yet) called flash_safe_execute_core_init(). Right
 * after multicore_launch_core1() that is a normal start-up race, so keep
 * retrying until the lockout timeout expires before reporting it.
 */
static int run_flash_op(flash_op_t *op) {
    const absolute_time_t until = make_timeout_time_ms(FLASH_EEPROM_LOCKOUT_TIMEOUT_MS);
    int rc;
    while ((rc = flash_safe_execute(flash_op, op, FLASH_EEPROM_LOCKOUT_TIMEOUT_MS))
               == PICO_ERROR_NOT_PERMITTED &&
           !time_reached(until)) {
        busy_wait_us(100);
    }
    return rc;
}

/** Store the RAM mirror in the next usable slot. */
static flash_eeprom_status_t commit(void) {
    slot_header_t hdr;
    hdr.magic  = SLOT_MAGIC;
    hdr.seq    = s_seq + 1u;
    hdr.length = FLASH_EEPROM_SIZE;
    hdr.crc    = slot_crc(hdr.seq, hdr.length, s_mirror);

    const uint32_t cur_eu = s_cur_slot / SLOTS_PER_EU;
    uint32_t slot = s_cur_slot;

    /* A verify failure is retried once in a fresh slot (worn cells). If that
     * fails too the problem is systematic, so stop instead of erasing more. */
    uint32_t verify_failures = 0;

    for (uint32_t tries = 0; tries < TOTAL_SLOTS; tries++) {
        slot = (slot + 1u) % TOTAL_SLOTS;
        const bool erase = (slot % SLOTS_PER_EU) == 0u;

        if (erase) {
            /* Never erase the unit holding the last good copy. */
            if (s_have_valid && (slot / SLOTS_PER_EU) == cur_eu) {
                return FLASH_EEPROM_ERR_FLASH;
            }
        } else if (!slot_is_blank(slot)) {
            continue; /* left over from an interrupted write: skip it */
        }

        flash_op_t op = { .slot = slot, .erase = erase, .hdr = &hdr };
        const int rc = run_flash_op(&op);
        if (rc != PICO_OK) {
            /* Nothing was written. */
            return (rc == PICO_ERROR_TIMEOUT) ? FLASH_EEPROM_ERR_TIMEOUT
                                              : FLASH_EEPROM_ERR_LOCKOUT;
        }

        uint32_t seq;
        if (slot_is_valid(slot, &seq) && seq == hdr.seq &&
            memcmp(slot_ptr(slot) + FLASH_EEPROM_HEADER_SIZE, s_mirror, FLASH_EEPROM_SIZE) == 0) {
            s_cur_slot   = slot;
            s_seq        = hdr.seq;
            s_have_valid = true;
            return FLASH_EEPROM_OK;
        }
        if (++verify_failures >= 2u) {
            return FLASH_EEPROM_ERR_FLASH;
        }
    }
    return FLASH_EEPROM_ERR_FLASH;
}

/* ------------------------------------------------------------------------- */
/* Public API                                                                 */
/* ------------------------------------------------------------------------- */

flash_eeprom_status_t flash_eeprom_init(void) {
    s_initialised = false;

#if !PICO_NO_FLASH
    /* Make sure the region does not overlap the program stored in flash. */
    extern char __flash_binary_end;
    if ((uintptr_t)XIP_BASE + FLASH_EEPROM_FLASH_OFFSET < (uintptr_t)&__flash_binary_end) {
        return FLASH_EEPROM_ERR_LAYOUT;
    }
#endif

    s_have_valid = false;
    s_seq        = 0u;
    s_cur_slot   = TOTAL_SLOTS - 1u; /* so the first write goes to slot 0 */

    for (uint32_t slot = 0; slot < TOTAL_SLOTS; slot++) {
        uint32_t seq;
        if (!slot_is_valid(slot, &seq)) {
            continue;
        }
        if (!s_have_valid || (int32_t)(seq - s_seq) > 0) {
            s_have_valid = true;
            s_seq        = seq;
            s_cur_slot   = slot;
        }
    }

    reload_mirror();
    s_initialised = true;
    return FLASH_EEPROM_OK;
}

flash_eeprom_status_t flash_eeprom_read(uint32_t addr, void *buf, size_t len) {
    if (!s_initialised) {
        return FLASH_EEPROM_ERR_NOT_INIT;
    }
    if (len == 0u) {
        return FLASH_EEPROM_OK;
    }
    if (buf == NULL || addr >= FLASH_EEPROM_SIZE || len > FLASH_EEPROM_SIZE - addr) {
        return FLASH_EEPROM_ERR_PARAM;
    }
    memcpy(buf, &s_mirror[addr], len);
    return FLASH_EEPROM_OK;
}

flash_eeprom_status_t flash_eeprom_write(uint32_t addr, const void *buf, size_t len) {
    if (!s_initialised) {
        return FLASH_EEPROM_ERR_NOT_INIT;
    }
    if (len == 0u) {
        return FLASH_EEPROM_OK;
    }
    if (buf == NULL || addr >= FLASH_EEPROM_SIZE || len > FLASH_EEPROM_SIZE - addr) {
        return FLASH_EEPROM_ERR_PARAM;
    }
    if (memcmp(&s_mirror[addr], buf, len) == 0) {
        return FLASH_EEPROM_OK; /* unchanged: no flash wear */
    }

    memcpy(&s_mirror[addr], buf, len);
    flash_eeprom_status_t st = commit();
    if (st != FLASH_EEPROM_OK) {
        reload_mirror(); /* keep RAM consistent with what is in flash */
    }
    return st;
}
