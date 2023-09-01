// Copyright (c) 2023, Auterion AG
// SPDX-License-Identifier: BSD-3-Clause

#pragma once

#ifdef __cplusplus
extern "C"
{
#endif

#include <stdint.h>

enum
{
    // CONFIG_SCHED_INSTRUMENTATION
    EMDBG_TASK_START = 0,
    EMDBG_TASK_STOP = 1,
    EMDBG_TASK_SUSPEND = 2,
    EMDBG_TASK_RESUME = 3,
    EMDBG_TASK_RUNNABLE = 4, // custom
    // Semaphores custom
    EMDBG_SEMAPHORE_WAIT = 5,
    EMDBG_SEMAPHORE_POST = 6,
    // CONFIG_SCHED_INSTRUMENTATION_PREEMPTION
    EMDBG_PREEMPTION_LOCK = 7,
    EMDBG_PREEMPTION_UNLOCK = 8,
    // CONFIG_SCHED_INSTRUMENTATION_CSECTION
    EMDBG_CSECTION_ENTER = 9,
    EMDBG_CSECTION_LEAVE = 10,
    // CONFIG_SCHED_INSTRUMENTATION_SPINLOCKS
    EMDBG_SPINLOCK_LOCK = 11,
    EMDBG_SPINLOCK_LOCKED = 12,
    EMDBG_SPINLOCK_UNLOCK = 13,
    EMDBG_SPINLOCK_ABORT = 14,

    // Workqueue custom
    EMDBG_WORKQUEUE_START = 15,
    EMDBG_WORKQUEUE_STOP = 16,
    // Heap custom
    EMDBG_HEAP_REGIONS = 17,
    EMDBG_HEAP_MALLOC_ATTEMPT = 18,
    EMDBG_HEAP_MALLOC_RESULT = 19,
    EMDBG_HEAP_FREE = 20,
};

#define EMDBG_LOG_SEMAPHORE_WAIT(sem) \
    emdbg_itm16_block(EMDBG_SEMAPHORE_WAIT, (uint32_t)sem >> 3)

#define EMDBG_LOG_SEMAPHORE_POST(sem) \
    emdbg_itm16_block(EMDBG_SEMAPHORE_POST, (uint32_t)sem >> 3)

#define EMDBG_LOG_TASK_START(tcb) \
    for (const char *name = tcb->name, \
         *end = tcb->name + strnlen(tcb->name, CONFIG_TASK_NAME_SIZE); \
         name < end; name += 4) \
    { \
        uint32_t value; \
        memcpy(&value, name, 4); \
        emdbg_itm32_block(EMDBG_TASK_START, value); \
    } \
    emdbg_itm16_block(EMDBG_TASK_START, tcb->pid)

#define EMDBG_LOG_TASK_RESUME(tcb, prev_state) \
    emdbg_itm32_block(EMDBG_TASK_RESUME, (prev_state << 24) | (tcb->sched_priority << 16) | tcb->pid)


#define EMDBG_WORKQUEUE_START(item) \
    { emdbg_itm32_block(EMDBG_WORKQUEUE_START, (uint32_t)(item->ItemName())); }

#define EMDBG_WORKQUEUE_STOP(item) \
    { emdbg_itm8_block(EMDBG_WORKQUEUE_STOP, item->_run_count); }


#define EMDBG_HEAP_ADDREGION(start, size) \
    { emdbg_itm32_block(EMDBG_HEAP_REGIONS, (uint32_t)start | 0x80000000); \
      emdbg_itm_block(EMDBG_HEAP_REGIONS, (uint32_t)size);

#define EMDBG_HEAP_MALLOC(size) \
    emdbg_itm_block(EMDBG_HEAP_MALLOC_ATTEMPT, (uint32_t)size)

#define EMDBG_HEAP_MALLOC_RESULT(ptr) \
    emdbg_itm_block(EMDBG_HEAP_MALLOC_RESULT, (uint32_t)ptr)

#define EMDBG_HEAP_FREE(ptr) \
    emdbg_itm32_block(EMDBG_HEAP_FREE, (uint32_t)ptr)

#define EMDBG_HEAP_REALLOC(oldptr, size, newptr) \
    { EMDBG_HEAP_FREE(oldptr); EMDBG_HEAP_MALLOC(size); EMDBG_HEAP_MALLOC_RESULT(newptr); }

#define EMDBG_HEAP_MEMALIGN(oldptr, size, newptr) \
    EMDBG_HEAP_REALLOC(oldptr, size, newptr)


typedef struct
{
    volatile union
    {
        volatile uint8_t  u8;
        volatile uint16_t u16;
        volatile uint32_t u32;
    }                 PORT[32u];
             uint32_t RESERVED0[864u];
    volatile uint32_t TER;
} EMDBG_ITM_Type;
#define EMDBG_ITM ((EMDBG_ITM_Type*)0xE0000000ul)


static inline void emdbg_itm8(uint8_t channel, uint8_t value);
static inline void emdbg_itm16(uint8_t channel, uint16_t value);
static inline void emdbg_itm32(uint8_t channel, uint32_t value);
static inline void emdbg_itm(uint8_t channel, uint32_t value);

void emdbg_itm8(uint8_t channel, uint8_t value)
{
    if (EMDBG_ITM->PORT[channel].u32)
        EMDBG_ITM->PORT[channel].u8 = value;
}

void emdbg_itm16(uint8_t channel, uint16_t value)
{
    if (EMDBG_ITM->PORT[channel].u32)
        EMDBG_ITM->PORT[channel].u16 = value;
}

void emdbg_itm32(uint8_t channel, uint32_t value)
{
    if (EMDBG_ITM->PORT[channel].u32)
        EMDBG_ITM->PORT[channel].u32 = value;
}

void emdbg_itm(uint8_t channel, uint32_t value)
{
    if (value & 0xffff0000ul) emdbg_itm32(channel, value);
    else if (value & 0xff00u) emdbg_itm16(channel, value);
    else emdbg_itm8(channel, value);
}

static inline void emdbg_itm8_block(uint8_t channel, uint8_t value);
static inline void emdbg_itm16_block(uint8_t channel, uint16_t value);
static inline void emdbg_itm32_block(uint8_t channel, uint32_t value);
static inline void emdbg_itm_block(uint8_t channel, uint32_t value);

void emdbg_itm8_block(uint8_t channel, uint8_t value)
{
    if (EMDBG_ITM->TER & (1ul << channel)) {
        while (!EMDBG_ITM->PORT[channel].u32) ;
        EMDBG_ITM->PORT[channel].u8 = value;
    }
}

void emdbg_itm16_block(uint8_t channel, uint16_t value)
{
    if (EMDBG_ITM->TER & (1ul << channel)) {
        while (!EMDBG_ITM->PORT[channel].u32) ;
        EMDBG_ITM->PORT[channel].u16 = value;
    }
}

void emdbg_itm32_block(uint8_t channel, uint32_t value)
{
    if (EMDBG_ITM->TER & (1ul << channel)) {
        while (!EMDBG_ITM->PORT[channel].u32) ;
        EMDBG_ITM->PORT[channel].u32 = value;
    }
}

void emdbg_itm_block(uint8_t channel, uint32_t value)
{
    if (value & 0xffff0000ul) emdbg_itm32_block(channel, value);
    else if (value & 0xff00u) emdbg_itm16_block(channel, value);
    else emdbg_itm8_block(channel, value);
}

#undef EMDBG_ITM

#ifdef __cplusplus
}
#endif
