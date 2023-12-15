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
    // Tasks
    EMDBG_TASK_START = 0,
    EMDBG_TASK_STOP = 1,
    EMDBG_TASK_RESUME = 2,
    EMDBG_TASK_RUNNABLE = 3, // custom
    // Workqueues
    EMDBG_WORKQUEUE = 4,
    // Semaphores
    EMDBG_SEMAPHORE_INIT = 5,
    EMDBG_SEMAPHORE_DECR = 6,
    EMDBG_SEMAPHORE_INCR = 7,

    // Heap
    EMDBG_HEAP_REGIONS = 8,
    EMDBG_HEAP_MALLOC_ATTEMPT = 9,
    EMDBG_HEAP_MALLOC_RESULT = 10,
    EMDBG_HEAP_FREE = 11,

    // DMA
    EMDBG_DMA_CONFIG = 12,
    EMDBG_DMA_START = 13,
    EMDBG_DMA_STOP = 14,

    // the rest are optional user channels
    EMDBG_UART4_TX = 30,
    EMDBG_UART4_RX = 31,
};

#define EMDBG_LOG_TASK_START(tcb) \
    for (const char *name = tcb->name, \
         *end = tcb->name + strnlen(tcb->name, CONFIG_TASK_NAME_SIZE); \
         name < end; name += 4) \
    { \
        uint32_t value; \
        memcpy(&value, name, 4); \
        emdbg_itm32_block(EMDBG_TASK_START, value); \
    } \
    emdbg_itm_block(EMDBG_TASK_START, tcb->pid)

#define EMDBG_LOG_TASK_STOP(tcb) \
    emdbg_itm_block(EMDBG_TASK_STOP, tcb->pid)

#define EMDBG_LOG_TASK_RESUME(tcb, prev_state) \
    emdbg_itm32_block(EMDBG_TASK_RESUME, (prev_state << 24) | (tcb->sched_priority << 16) | tcb->pid)

#define EMDBG_LOG_TASK_RUNNABLE(tcb) \
    emdbg_itm_block(EMDBG_TASK_RUNNABLE, tcb->pid)


#define EMDBG_LOG_SEMAPHORE_INIT(sem) \
    { emdbg_itm32_block(EMDBG_SEMAPHORE_INIT, (uint32_t)sem); \
      emdbg_itm16_block(EMDBG_SEMAPHORE_INIT, sem->semcount); }

#define EMDBG_LOG_SEMAPHORE_DECR(sem) \
    emdbg_itm32_block(EMDBG_SEMAPHORE_DECR, (uint32_t)sem)

#define EMDBG_LOG_SEMAPHORE_INCR(sem) \
    emdbg_itm32_block(EMDBG_SEMAPHORE_INCR, (uint32_t)sem)


#define EMDBG_LOG_WORKQUEUE_START(item) \
    emdbg_itm32_block(EMDBG_WORKQUEUE, (uint32_t)(item->ItemName()));

#define EMDBG_LOG_WORKQUEUE_STOP(item) \
    emdbg_itm8_block(EMDBG_WORKQUEUE, 0);


#define EMDBG_LOG_HEAP_ADDREGION(start, size) \
    { emdbg_itm32_block(EMDBG_HEAP_REGIONS, (uint32_t)start | 0x80000000); \
      emdbg_itm_block(EMDBG_HEAP_REGIONS, (uint32_t)size); }

#define EMDBG_LOG_HEAP_MALLOC(size) \
    emdbg_itm_block(EMDBG_HEAP_MALLOC_ATTEMPT, (uint32_t)size)

#define EMDBG_LOG_HEAP_MALLOC_RESULT(ptr) \
    emdbg_itm_block(EMDBG_HEAP_MALLOC_RESULT, (uint32_t)ptr)

#define EMDBG_LOG_HEAP_FREE(ptr) \
    emdbg_itm32_block(EMDBG_HEAP_FREE, (uint32_t)ptr)

#define EMDBG_LOG_HEAP_REALLOC(oldptr, size, newptr) \
    { EMDBG_LOG_HEAP_FREE(oldptr); EMDBG_LOG_HEAP_MALLOC(size); EMDBG_LOG_HEAP_MALLOC_RESULT(newptr); }

#define EMDBG_LOG_HEAP_MEMALIGN(oldptr, size, newptr) \
    EMDBG_LOG_HEAP_REALLOC(oldptr, size, newptr)

#define EMDBG_LOG_DMA_CONFIGURE(channel, config) \
    { \
        uint16_t mask = 0x8000; \
        if (channel->cfg.ndata != config->ndata) mask |= 0x0100; \
        if (channel->cfg.paddr != config->paddr) mask |= 0x0200; \
        if (channel->cfg.maddr != config->maddr) mask |= 0x0400; \
        if (channel->cfg.cfg1 != config->cfg1) mask |= 0x0800; \
        if (mask & 0x0f00) { \
            emdbg_itm16_block(EMDBG_DMA_CONFIG, (mask | ((uint16_t)channel->ctrl << 5) | (uint16_t)channel->chan)); \
            if (mask & 0x0100) emdbg_itm_block(EMDBG_DMA_CONFIG, config->ndata); \
            if (mask & 0x0200) emdbg_itm32_block(EMDBG_DMA_CONFIG, (uint32_t)config->paddr); \
            if (mask & 0x0400) emdbg_itm32_block(EMDBG_DMA_CONFIG, (uint32_t)config->maddr); \
            if (mask & 0x0800) emdbg_itm32_block(EMDBG_DMA_CONFIG, (uint32_t)config->cfg1); \
            channel->cfg = *cfg; \
        } \
    }

#define EMDBG_LOG_DMA_START(channel) \
    { emdbg_itm8_block(EMDBG_DMA_START, ((uint8_t)channel->ctrl << 5) | (uint8_t)channel->chan); }

#define EMDBG_LOG_DMA_STOP(channel) \
    { emdbg_itm8_block(EMDBG_DMA_STOP, ((uint8_t)channel->ctrl << 5) | (uint8_t)channel->chan); }

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
