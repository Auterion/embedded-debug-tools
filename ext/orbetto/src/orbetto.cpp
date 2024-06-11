// Copyright (c) 2019-2023, Orbcode Project
// Copyright (c) 2023, Auterion AG
// SPDX-License-Identifier: BSD-3-Clause
// This file is a modified version of orbuculum/orbcat.c

#include <stdlib.h>
#include <unistd.h>
#include <ctype.h>
#include <stdio.h>
#include <string.h>
#include <string>
#include <assert.h>
#include <inttypes.h>
#include <getopt.h>
#include <time.h>
#include <set>
#include <iostream>
#include <fstream>
#include <cxxabi.h>

using namespace std::string_literals;

#include "nw.h"
#include "git_version_info.h"
#include "generics.h"
#include "tpiuDecoder.h"
#include "itmDecoder.h"
#include "msgDecoder.h"
#include "msgSeq.h"
#include "stream.h"
#include "loadelf.h"
#include "device.hpp"
#include "mortrall.hpp"

// To get the ITM channel list
#include "../../src/emdbg/patch/data/itm.h"

#include <protos/perfetto/trace/trace.pb.h>

#define MSG_REORDER_BUFLEN  (10)          /* Maximum number of samples to re-order for timekeeping */

// Record for options, either defaults or from command line
struct
{
    /* Config information */
    bool useTPIU{false};
    uint32_t tpiuChannel{1};
    uint64_t cps{0};
    std::string file;
    std::string elfFile;
    bool outputDebugFile;
} options;

struct
{
    /* The decoders and the packets from them */
    struct ITMDecoder i;
    struct MSGSeq    d;
    struct ITMPacket h;
    struct TPIUDecoder t;
    struct TPIUPacket p;
    uint64_t timeStamp;                  /* Latest received time */
    uint64_t ns;                         /* Latest received time in ns */
    struct symbol *symbols;              /* symbols from the elf file */
} _r;

static Device device;

static perfetto::protos::Trace *perfetto_trace;
static perfetto::protos::FtraceEventBundle *ftrace;
Mortrall mortrall;

// ====================================================================================================

static constexpr uint32_t PID_TSK{0};
static constexpr uint32_t PID_STOP{10000};
static constexpr uint32_t PID_PC{100000};
static constexpr uint32_t PID_DMA{200000};
static constexpr uint32_t PID_UART{300000};
static constexpr uint32_t PID_SEMAPHORE{1000000};
static uint16_t prev_tid{0};
static std::set<uint16_t> active_threads;
static void _switchTo(uint16_t tid, bool begin, int priority = -1, int prev_state = -1)
{
    if (begin)
    {
        auto *event = ftrace->add_event();
        event->set_timestamp(_r.ns);
        event->set_pid(prev_tid);

        auto *sched_switch = event->mutable_sched_switch();
        sched_switch->set_prev_pid(prev_tid);
        if (prev_state <= 0 or prev_tid == 0) {
            sched_switch->set_prev_state(prev_tid == 0 ? 0x4000 : 0x8000);
        }
        else {
            /*
            TSTATE_TASK_PENDING = 1,        // READY_TO_RUN - Pending preemption unlock
            TSTATE_TASK_READYTORUN = 2,     // READY-TO-RUN - But not running
            TSTATE_TASK_RUNNING = 3,        // READY_TO_RUN - And running

            TSTATE_TASK_INACTIVE = 4,       // BLOCKED      - Initialized but not yet activated
            TSTATE_WAIT_SEM = 5,            // BLOCKED      - Waiting for a semaphore
            TSTATE_WAIT_SIG = 6,            // BLOCKED      - Waiting for a signal

                needs to be translated to these flags:

            kRunnable = 0x0000,  // no flag (besides kPreempted) means "running"
            kInterruptibleSleep = 0x0001,
            kUninterruptibleSleep = 0x0002,
            kStopped = 0x0004,
            kTraced = 0x0008,
            kExitDead = 0x0010,
            kExitZombie = 0x0020,

            // Starting from here, different kernels have different values:
            kParked = 0x0040,

            // No longer reported on 4.14+:
            kTaskDead = 0x0080,
            kWakeKill = 0x0100,
            kWaking = 0x0200,
            kNoLoad = 0x0400,

            // Special states that don't map onto the scheduler's constants:
            kIdle = 0x4000,
            kPreempted = 0x8000,  // exclusive as only running tasks can be preempted
            */
            switch(prev_state)
            {
                case 1: sched_switch->set_prev_state(0x4000); break;
                case 2:
                case 3: sched_switch->set_prev_state(0x8000); break;
                case 4: sched_switch->set_prev_state(0x0200); break;
                case 5:
                case 6: sched_switch->set_prev_state(0x0001); break;
            }

        }
        sched_switch->set_next_pid(tid);
        if (priority >= 0) sched_switch->set_next_prio(priority);

        prev_tid = tid;
        mortrall.update_tid(tid);
    }
}

// ====================================================================================================
static std::unordered_map<uint32_t, uint32_t> heap_regions;
static std::unordered_map<uint32_t, std::pair<uint32_t, uint32_t>> heap_allocations;
static uint32_t heap_size_total{0};
static uint32_t heap_size_remaining{0};
static void _writeHeapTotal(uint64_t ns, int32_t size)
{
    heap_size_total += size;
    heap_size_remaining -= size;
    {
        auto *event = ftrace->add_event();
        event->set_timestamp(ns);
        event->set_pid(0);
        auto *print = event->mutable_print();
        char buffer[100];
        snprintf(buffer, 100, "C|0|Heap Usage|%u", heap_size_total);
        print->set_buf(buffer);
    }
    {
        auto *event = ftrace->add_event();
        event->set_timestamp(ns);
        event->set_pid(0);
        auto *print = event->mutable_print();
        char buffer[100];
        snprintf(buffer, 100, "C|0|Heap Available|%u", heap_size_remaining);
        print->set_buf(buffer);
    }
}
static void _writeMalloc(uint64_t ns, uint32_t address, uint32_t alignsize, uint32_t size)
{
    _writeHeapTotal(ns, alignsize);
    auto *event = ftrace->add_event();
    event->set_timestamp(_r.ns);
    event->set_pid(prev_tid);
    auto *print = event->mutable_print();
    // print->set_ip(address);
    char buffer[100];
    snprintf(buffer, 100, "I|0|malloc(%u) -> [0x%08x, %u]", size, address, alignsize);
    print->set_buf(buffer);

}
static void _writeFree(uint64_t ns, uint32_t address, uint32_t alignsize, uint32_t size)
{
    _writeHeapTotal(ns, -alignsize);
    auto *event = ftrace->add_event();
    event->set_timestamp(_r.ns);
    event->set_pid(prev_tid);
    auto *print = event->mutable_print();
    // print->set_ip(address | 0x1'0000'0000);
    char buffer[100];
    snprintf(buffer, 100, "I|0|free(0x%08x) <- %u (%u)", address, size, alignsize);
    print->set_buf(buffer);
}

// ====================================================================================================
static std::unordered_map<uint16_t, uint32_t> workqueue_map;
static std::unordered_map<uint32_t, std::string> workqueue_names;
static std::set<uint16_t> stopped_threads;
static std::unordered_map<uint16_t, std::string> thread_names;
static std::unordered_map<uint32_t, int16_t> semaphores;
struct dma_config_t
{
    uint32_t size;
    uint32_t paddr;
    uint32_t maddr;
    uint32_t config;
};
static std::unordered_map<uint32_t, dma_config_t> dma_channel_config;
static std::unordered_map<uint32_t, uint64_t> dma_channel_transfer;
static std::unordered_map<uint32_t, std::string> dma_channel_name;
static std::unordered_map<uint32_t, bool> dma_channel_state;
static void _handleSW( struct swMsg *m, struct ITMDecoder *i )
{
    const uint64_t ns = _r.ns;

    static std::string thread_name;
    uint16_t tid = (m->value & 0xfffful);
    const bool tid_tl = tid > 3000;
    if (stopped_threads.contains(tid)) tid += PID_STOP;
    else if (tid != 0) tid += PID_TSK;

    switch (m->srcAddr)
    {
        case EMDBG_TASK_START: // start
        {
            if (m->len == 4) {
                char name[5]{0,0,0,0,0};
                memcpy(name, &m->value, 4);
                thread_name += name;
            }
            if (m->len <= 2) {
                if (tid_tl) {
                    thread_name.clear();
                    return;
                }
                if (not thread_name.empty())
                {
                    if (tid)
                    {
                        auto *event = ftrace->add_event();
                        event->set_timestamp(ns);
                        event->set_pid(prev_tid);
                        auto *renametask = event->mutable_task_rename();
                        renametask->set_pid(tid);
                        renametask->set_newcomm(thread_name.c_str());
                    }
                    thread_names[tid] = thread_name;
                    active_threads.insert(tid);
                }
                thread_name.clear();
            }
            break;
        }
        case EMDBG_TASK_STOP: // stop
        {
            if (tid_tl or not active_threads.contains(tid)) return;
            active_threads.erase(tid);
            if (workqueue_map.contains(tid))
            {
                auto *event = ftrace->add_event();
                event->set_timestamp(ns);
                event->set_pid(tid);
                event->mutable_workqueue_execute_end();
                workqueue_map.erase(tid);
            }
            break;
        }
        case EMDBG_TASK_RESUME: // resume
        {
            if (tid_tl) return;
            if (not active_threads.contains(tid)) return;
            const uint8_t priority = m->value >> 16;
            const uint8_t prev_state = m->value >> 24;
            _switchTo(tid, true, priority, prev_state);
            if(prev_tid < PID_STOP && prev_tid != 0)
            {
                auto *event = ftrace->add_event();
                event->set_timestamp(ns);
                event->set_pid(PID_TSK + prev_tid);
                auto *print = event->mutable_print();
                char buffer[100];
                snprintf(buffer, sizeof(buffer), "C|%u|Priorities %s|%u",PID_TSK,thread_names[prev_tid].c_str() ,priority);
                print->set_buf(buffer);
            }
            break;
        }
        case EMDBG_TASK_RUNNABLE: // ready
        {
            if (tid_tl) return;
            auto *event = ftrace->add_event();
            event->set_timestamp(ns);
            event->set_pid(prev_tid);
            auto *sched_waking = event->mutable_sched_waking();
            sched_waking->set_pid(tid);
            sched_waking->set_success(1);
            break;
        }
        case EMDBG_WORKQUEUE: // workqueue start/stop
        {
            if (prev_tid == 0) return;
            if (m->value) // workqueue start
            {
                if (workqueue_map.contains(prev_tid))
                {
                    auto *event = ftrace->add_event();
                    event->set_timestamp(ns);
                    event->set_pid(prev_tid);
                    event->mutable_workqueue_execute_end();
                }
                auto *event = ftrace->add_event();
                event->set_timestamp(ns);
                event->set_pid(prev_tid);
                auto *workqueue_start = event->mutable_workqueue_execute_start();
                workqueue_start->set_function(m->value);
                workqueue_map[prev_tid] = m->value;
                if (_r.symbols and not workqueue_names.contains(m->value))
                {
                    if (const char *name = (const char *) symbolCodeAt(_r.symbols, m->value, NULL); name)
                    {
                        printf("Found Name %s for 0x%08x\n", name, m->value);
                        workqueue_names[m->value] = name;
                    }
                    else {
                        printf("No match found for 0x%08x\n", m->value);
                    }
                }
            }
            else // workqueue stop
            {
                if (workqueue_map.contains(prev_tid))
                {
                    auto *event = ftrace->add_event();
                    event->set_timestamp(ns);
                    event->set_pid(prev_tid);
                    event->mutable_workqueue_execute_end();
                    workqueue_map.erase(prev_tid);
                }
            }
            break;
        }
        case EMDBG_SEMAPHORE_INIT:
        {
            static uint32_t addr{0};
            if (m->len == 4) addr = m->value;
            else if (m->len == 2) {
                semaphores[addr] = m->value == uint16_t(-1) ? 0 : m->value;
            }
            break;
        }
        case EMDBG_SEMAPHORE_DECR:
        case EMDBG_SEMAPHORE_INCR:
        {
            const bool increment = (m->srcAddr == EMDBG_SEMAPHORE_INCR);
            increment ? semaphores[m->value]++ : semaphores[m->value]--;

            {
                auto *event = ftrace->add_event();
                event->set_timestamp(ns);
                event->set_pid(PID_SEMAPHORE + m->value);
                auto *print = event->mutable_print();
                char buffer[100];
                snprintf(buffer, sizeof(buffer), "C|%u|Semaphore %#08x|%d", PID_SEMAPHORE, m->value, semaphores[m->value]);
                print->set_buf(buffer);
            }
            {
                auto *event = ftrace->add_event();
                event->set_timestamp(ns);
                event->set_pid(prev_tid);
                auto *print = event->mutable_print();
                char buffer[100];
                snprintf(buffer, sizeof(buffer), "I|0|%s semaphore %#08x", increment ? "Post" : "Wait on", m->value);
                print->set_buf(buffer);
            }
            break;
        }
        case EMDBG_HEAP_REGIONS: // heap region
        {
            static uint32_t start = 0;
            if (m->value & 0x80000000) {
                start = m->value & ~0x80000000;
            }
            else if (start)
            {
                const uint32_t end = start + m->value;
                heap_regions[start] = end;
                printf("Heap region added: [%08x, %08x] (%ukiB)\n", start, end, (end - start) / 1024);
                heap_size_remaining += end - start;
                start = 0;
                {
                    auto *event = ftrace->add_event();
                    event->set_timestamp(ns);
                    event->set_pid(0);
                    auto *print = event->mutable_print();
                    char buffer[100];
                    snprintf(buffer, 100, "C|0|Heap Available|%u", heap_size_remaining);
                    print->set_buf(buffer);
                }
            }
            break;
        }
        case EMDBG_HEAP_MALLOC_ATTEMPT:  // malloc attempt
        case EMDBG_HEAP_MALLOC_RESULT:   // and malloc result
        {
            static uint32_t size = 0;
            static uint32_t alignsize = 0;
            if (m->srcAddr == EMDBG_HEAP_MALLOC_ATTEMPT) {
                size = m->value;
                alignsize = ((size + 16) + 0xf) & ~0xf;
            }
            else {
                if (m->value) heap_allocations[m->value] = std::pair{size, alignsize};
                else printf("malloc(%uB) failed!\n", size);
                _writeMalloc(ns, m->value, alignsize, size);
            }
            break;
        }
        case EMDBG_HEAP_FREE: // free
        {
            if (heap_allocations.contains(m->value))
            {
                const auto [size, alignsize] = heap_allocations[m->value];
                heap_allocations.erase(m->value);
                _writeFree(ns, m->value, alignsize, size);
            }
            else printf("Unknown size for free(0x%08x)!\n", m->value);
            break;
        }
        case EMDBG_DMA_CONFIG: // dma config
        {
            static uint8_t instance{0}, channel{0};
            static uint32_t did{0};
            static uint16_t mask{0x8000};
            if (m->len == 2 and m->value & 0x8000 and mask & 0x8000) {
                channel = m->value & 0x1f;
                instance = (m->value >> 5) & 0x7;
                did = PID_DMA + instance * 100 + channel;
                mask = m->value & 0x0f00;
                // printf("%llu: DMA%u CH%u Config: Mask=%#04x\n", ns, instance, channel, mask);
            }
            else if (mask & 0x0100) {
                dma_channel_config[did].size = m->value;
                mask &= ~0x0100;
                // printf("%llu: DMA%u CH%u Config: S=%u\n", ns, instance, channel, m->value);
            }
            else if (mask & 0x0200) {
                dma_channel_config[did].paddr = m->value;
                mask &= ~0x0200;
                // printf("%llu: DMA%u CH%u Config: P=%#08x\n", ns, instance, channel, m->value);
            }
            else if (mask & 0x0400) {
                dma_channel_config[did].maddr = m->value;
                mask &= ~0x0400;
                // printf("%llu: DMA%u CH%u Config: M=%#08x\n", ns, instance, channel, m->value);
            }
            else if (mask & 0x0800) {
                dma_channel_config[did].config = m->value;
                mask &= ~0x0800;
                // printf("%llu: DMA%u CH%u Config: C=%#08x\n", ns, instance, channel, m->value);
            }
            else {
                mask = 0x8000;
            }
            if (mask == 0) {
                const auto &config = dma_channel_config[did];
                uint32_t src = config.paddr, dst = config.maddr;
                if ((config.config & 0xC0) == 0x40) std::swap(src, dst);
                const auto src_name = device.register_name(src);
                const auto dst_name = device.register_name(dst);
                char buffer[1000];
                snprintf(buffer, sizeof(buffer), "%uB: %#08x%s -> %#08x%s (%#08x:%s%s%s%s%s%s%s%s)",
                         config.size,
                         src, src_name.empty() ? "" : ("="s + std::string(src_name)).c_str(),
                         dst, dst_name.empty() ? "" : ("="s + std::string(dst_name)).c_str(),
                         config.config,
                         config.config & 0x40000 ? " DBM" : "",
                         (const char*[]){" L", " M", " H", " VH"}[(config.config & 0x30000) >> 16],
                         (const char*[]){" P8", " P16", " P32", ""}[(config.config & 0x6000) >> 13],
                         (const char*[]){" M8", " M16", " M32", ""}[(config.config & 0x1800) >> 11],
                         config.config & 0x400 ? " MINC" : "",
                         config.config & 0x200 ? " PINC" : "",
                         config.config & 0x100 ? " CIRC" : "",
                         config.config & 0x20 ? " PFCTRL" : "");
                dma_channel_name[did] = buffer;
                mask = 0x8000;
            }
            break;
        }
        case EMDBG_DMA_START: // dma start
        {
            const uint32_t instance = m->value >> 5;
            const uint32_t channel = m->value & 0x1f;
            const uint32_t did = PID_DMA + instance * 100 + channel;
            // printf("%llu: DMA%u CH%u Start\n", ns, instance, channel);
            if (dma_channel_state[did])
            {
                auto *event = ftrace->add_event();
                event->set_timestamp(ns);
                event->set_pid(did);
                auto *print = event->mutable_print();
                print->set_buf("E|0");
            }
            {
                auto *event = ftrace->add_event();
                event->set_timestamp(ns);
                event->set_pid(did);
                auto *print = event->mutable_print();
                print->set_buf("B|0|"s + dma_channel_name[did]);
            }
            dma_channel_state[did] = true;
            break;
        }
        case EMDBG_DMA_STOP: // dma stop
        {
            const uint32_t instance = m->value >> 5;
            const uint32_t channel = m->value & 0x1f;
            const uint32_t did = PID_DMA + instance * 100 + channel;
            dma_channel_transfer[did] += dma_channel_config[did].size;
            // printf("%llu: DMA%u CH%u Stop\n", ns, instance, channel);
            {
                auto *event = ftrace->add_event();
                event->set_timestamp(ns);
                event->set_pid(did);
                auto *print = event->mutable_print();
                print->set_buf("E|0");
            }
            {
                auto *event = ftrace->add_event();
                event->set_timestamp(ns);
                event->set_pid(did);
                auto *print = event->mutable_print();
                char buffer[200];
                snprintf(buffer, 100, "C|%u|DMA%u CH%u Transfer|%llu", PID_DMA,
                         instance, channel, dma_channel_transfer[did]);
                print->set_buf(buffer);
            }
            dma_channel_state[did] = false;
            break;
        }
        case EMDBG_UART4_TX: // uart transmit
        {
            const uint32_t tid = PID_UART+2*4+0;
            {
                auto *event = ftrace->add_event();
                event->set_timestamp(ns);
                event->set_pid(tid);
                auto *print = event->mutable_print();
                print->set_buf("E|0");
            }
            {
                auto *event = ftrace->add_event();
                event->set_timestamp(ns);
                event->set_pid(tid);
                auto *print = event->mutable_print();
                char buffer[100];
                snprintf(buffer, sizeof(buffer), "B|0|%#02x", m->value);
                print->set_buf(buffer);
            }
            {
                auto *event = ftrace->add_event();
                // event->set_timestamp(ns+10000); // ~921600bps
                event->set_timestamp(ns+40000); // ~230400bps
                event->set_pid(tid);
                auto *print = event->mutable_print();
                print->set_buf("E|0");
            }
            {
                static uint64_t total{0};
                auto *event = ftrace->add_event();
                event->set_timestamp(ns);
                event->set_pid(tid);
                auto *print = event->mutable_print();
                char buffer[1000];
                snprintf(buffer, sizeof(buffer), "C|%u|UART4 Transmitted|%llu", PID_UART, ++total);
                print->set_buf(buffer);
            }
            break;
        }
        case EMDBG_UART4_RX: // uart receive
        {
            const uint32_t tid = PID_UART+2*4+1;
            const uint8_t data = m->value & 0xff;
            const uint8_t status = m->value >> 8;
            {
                auto *event = ftrace->add_event();
                event->set_timestamp(ns-40000);
                event->set_pid(tid);
                auto *print = event->mutable_print();
                print->set_buf("E|0");
            }
            {
                auto *event = ftrace->add_event();
                event->set_timestamp(ns-40000); // ~230400bps
                event->set_pid(tid);
                auto *print = event->mutable_print();
                char buffer[100];
                if (status & 0x08) {
                    snprintf(buffer, sizeof(buffer), "B|0|OVERFLOW %#02x", data);
                } else {
                    snprintf(buffer, sizeof(buffer), "B|0|%#02x", data);
                }
                print->set_buf(buffer);
            }
            {
                auto *event = ftrace->add_event();
                event->set_timestamp(ns);
                event->set_pid(tid);
                auto *print = event->mutable_print();
                print->set_buf("E|0");
            }
            if (status & 0x0f) printf("%llu: UART4 ERR=%#02x\n", ns, status);
            if (status & 0x08)
            {
                static uint64_t overflows{0};
                auto *event = ftrace->add_event();
                event->set_timestamp(ns);
                event->set_pid(tid);
                auto *print = event->mutable_print();
                char buffer[1000];
                snprintf(buffer, sizeof(buffer), "C|%u|UART4 Overflows|%llu", PID_UART, ++overflows);
                print->set_buf(buffer);
            }
            {
                static uint64_t total{0};
                auto *event = ftrace->add_event();
                event->set_timestamp(ns);
                event->set_pid(tid);
                auto *print = event->mutable_print();
                char buffer[1000];
                snprintf(buffer, sizeof(buffer), "C|%u|UART4 Received|%llu", PID_UART, ++total);
                print->set_buf(buffer);
            }
            break;
        }
        case EMDBG_PRINT: // debug print
        {
            const uint8_t data = m->value & 0xff;
            auto *event = ftrace->add_event();
            event->set_timestamp(ns);
            event->set_pid(100);
            auto *print = event->mutable_print();
            char buffer[100];
            snprintf(buffer, sizeof(buffer), "I|0|%u", data);
            print->set_buf(buffer);
            break;
        }
        case EMDBG_TS: // timestamp
        {
            auto *event = ftrace->add_event();
            event->set_timestamp(ns);
            event->set_pid(100);
            auto *print = event->mutable_print();
            char buffer[100];
            snprintf(buffer, sizeof(buffer), "I|0|Timestamp|%llu,%llu", m->value, (m->value * 1e9) / options.cps);
            print->set_buf(buffer);
            break;
        }
    }
}
// ====================================================================================================
static void _handleTS( struct TSMsg *m, struct ITMDecoder *i )
{
    _r.timeStamp += m->timeInc;
    _r.ns = (_r.timeStamp * 1e9) / options.cps;
    mortrall.update_itm_timestamp(_r.timeStamp,_r.ns);
}

// ====================================================================================================
static void _handleExc( struct excMsg *m, struct ITMDecoder *i )
{
    if (m->eventType == EXEVENT_UNKNOWN) return;
    const int16_t irq = m->exceptionNumber;
    if (irq > device.max_irq()) return;
    // [enter (1) -----> exit (2), resume (3)]
    const bool begin = m->eventType == EXEVENT_ENTER;
    const uint64_t ns = _r.ns;

    // filter out a RESUME, if EXIT was already received
    static std::unordered_map<int16_t, bool> irq_state;
    if (irq_state.contains(irq) and not irq_state[irq] and not begin)
        return;
    irq_state[irq] = begin;

    static int16_t last_irq{0};
    static bool last_begin{false};
    // we need to close the previous IRQ
    if (last_begin and begin)
    {
        auto *event = ftrace->add_event();
        event->set_timestamp(ns);
        event->set_pid(0);
        auto *exit = event->mutable_irq_handler_exit();
        exit->set_irq(last_irq);
    }
    last_irq = irq;
    last_begin = begin;

    auto *event = ftrace->add_event();
    event->set_timestamp(ns);
    event->set_pid(0);

    if (begin)
    {
        auto *entry = event->mutable_irq_handler_entry();
        entry->set_irq(irq);
        entry->set_name(std::string(device.irq(irq)));
    }
    else
    {
        auto *exit = event->mutable_irq_handler_exit();
        exit->set_irq(irq);
    }
}

// ====================================================================================================
static bool has_pc_samples{false};
static std::unordered_map<uint32_t, std::string> function_names;
static void _handlePc( struct pcSampleMsg *m, struct ITMDecoder *i )
{
    static uint32_t prev_function_addr{0};
    static uint16_t prev_prev_tid{0};
    // check if pc is in idle task, end the previous sample, then skip
    if(prev_tid == 0)
    {
        if(prev_function_addr)
        {
            auto *event = ftrace->add_event();
            event->set_timestamp(_r.ns);
            event->set_pid(PID_PC + prev_prev_tid);
            auto *exit = event->mutable_funcgraph_exit();
            exit->set_depth(0);
            exit->set_func(prev_function_addr);
            prev_function_addr = 0;
            printf("Last function in thread: %i\n", prev_prev_tid);
        }
        return;
    }
    // Find the function from the PC counter
    if (const auto *function = symbolFunctionAt(_r.symbols, m->pc); function)
    {
        uint32_t function_addr = function->lowaddr;
        // Keep two samples of the same function in one print
        if (function_addr == prev_function_addr and prev_tid == prev_prev_tid) return;
        if (not function_names.contains(function_addr)) {
            function_names[function_addr] = function->funcname;
            if (function->manglename) {
                if (char *realname = abi::__cxa_demangle(function->manglename, 0, 0, 0); realname) {
                    // std::cout << realname << std::endl;
                    function_names[function_addr] = realname;
                    free(realname);
                }
            }
        }

        // end the previous function sample
        if(prev_function_addr)
        {
            auto *event = ftrace->add_event();
            event->set_timestamp(_r.ns);
            event->set_pid(PID_PC + prev_prev_tid);
            auto *exit = event->mutable_funcgraph_exit();
            exit->set_depth(0);
            exit->set_func(prev_function_addr);
        }else
        {
            printf("First function in thread: %i\n", prev_tid);
        }
        // start the current function sample
        {
            auto *event = ftrace->add_event();
            event->set_timestamp(_r.ns);
            event->set_pid(PID_PC + prev_tid);
            auto *entry = event->mutable_funcgraph_entry();
            entry->set_depth(0);
            entry->set_func(function_addr);
            prev_function_addr = function_addr;
            prev_prev_tid = prev_tid;
        }
    }
}

// ====================================================================================================
static void _itmPumpProcessPre( char c )
{
    if ( ITM_EV_PACKET_RXED == ITMPump( &_r.i, c ) )
    {
        struct msg p;
        if ( ITMGetDecodedPacket( &_r.i, &p )  )
        {
            if ( p.genericMsg.msgtype == MSG_SOFTWARE )
            {
                struct swMsg *m = (struct swMsg *)&p;
                if (m->srcAddr == EMDBG_TASK_STOP) // stop
                {
                    stopped_threads.insert(m->value);
                    // printf("Thread %u stopped\n", m->value);
                }
            }
            else if (p.genericMsg.msgtype == MSG_PC_SAMPLE)
            {
                has_pc_samples = true;
            }
        }
    }
}

static void _itmPumpProcess( char c )
{
    struct msg *pp;

    typedef void ( *handlers )( void *decoded, struct ITMDecoder * i );

    /* Handlers for each complete message received */
    static const handlers h[MSG_NUM_MSGS] =
    {
        /* MSG_UNKNOWN */         NULL,
        /* MSG_RESERVED */        NULL,
        /* MSG_ERROR */           NULL,
        /* MSG_NONE */            NULL,
        /* MSG_SOFTWARE */        ( handlers )_handleSW,
        /* MSG_NISYNC */          NULL,
        /* MSG_OSW */             NULL,
        /* MSG_DATA_ACCESS_WP */  NULL,
        /* MSG_DATA_RWWP */       NULL,
        /* MSG_PC_SAMPLE */       ( handlers )_handlePc,
        /* MSG_DWT_EVENT */       NULL,
        /* MSG_EXCEPTION */       ( handlers )_handleExc,
        /* MSG_TS */              ( handlers )_handleTS
    };


    /* Pump messages into the store until we get a time message, then we can read them out */
    if ( !MSGSeqPump( &_r.d, c ) )
    {
        return;
    }

    /* We are synced timewise, so empty anything that has been waiting */
    while ( ( pp = MSGSeqGetPacket( &_r.d ) ) )
    {
        assert( pp->genericMsg.msgtype < MSG_NUM_MSGS );

        if ( h[pp->genericMsg.msgtype] )
        {

            ( h[pp->genericMsg.msgtype] )( pp, &_r.i );
        }
    }
}
// ====================================================================================================
// ====================================================================================================
// ====================================================================================================
// Protocol pump for decoding messages
// ====================================================================================================
// ====================================================================================================
// ====================================================================================================
int counter = 0;
static void _protocolPump( uint8_t c ,void ( *_pumpITMProcessGeneric )( char ),void ( *_pumpETMProcessGeneric )( char ))
{
    if ( options.useTPIU )
    {
        switch ( TPIUPump( &_r.t, c ) )
        {
            case TPIU_EV_NEWSYNC:
            case TPIU_EV_SYNCED:
                ITMDecoderForceSync( &_r.i, true );
                break;

            case TPIU_EV_RXING:
            case TPIU_EV_NONE:
                break;

            case TPIU_EV_UNSYNCED:
                ITMDecoderForceSync( &_r.i, false );
                break;

            case TPIU_EV_RXEDPACKET:
                if ( !TPIUGetPacket( &_r.t, &_r.p ) )
                {
                    genericsReport( V_WARN, "TPIUGetPacket fell over" EOL );
                }

                for ( uint32_t g = 0; g < _r.p.len; g++ )
                {
                    if  ( _r.p.packet[g].s == 2 )
                    {
                        // genericsReport( V_DEBUG, "Unknown TPIU channel %02x" EOL, _r.p.packet[g].s );
                        if ( _pumpETMProcessGeneric )
                        {
                            //printf("ETM\n");
                            _pumpETMProcessGeneric( _r.p.packet[g].d );
                        }
                        continue;
                    }
                    else if ( _r.p.packet[g].s == 1 )
                    {
                        // print counter
                        // printf("Packet count: %u\n", counter++);
                        counter ++;
                        //_itmPumpProcess( _r.p.packet[g].d );
                        _pumpITMProcessGeneric( (char)_r.p.packet[g].d );
                        //if ( _pumpETMProcessGeneric ) printf("ITM\n");
                    }
                    else
                    {
                        printf("Unknown TPIU channel %02x" EOL, _r.p.packet[g].s );
                    }
                }

                break;

            case TPIU_EV_ERROR:
                genericsReport( V_WARN, "****ERROR****" EOL );
                break;
            default:
                break;
        }
    }
    else
    {
        //_itmPumpProcess( c );
        _pumpITMProcessGeneric( c );
        //printf("C: %u\n", c);
    }
}
// ====================================================================================================
static struct option _longOptions[] =
{
    {"cpufreq", required_argument, NULL, 'C'},
    {"input-file", required_argument, NULL, 'f'},
    {"help", no_argument, NULL, 'h'},
    {"tpiu", required_argument, NULL, 't'},
    {"elf", required_argument, NULL, 'e'},
    {"debug", no_argument, NULL, 'd'},
    {"verbose", required_argument, NULL, 'v'},
    {"version", no_argument, NULL, 'V'},
    {NULL, no_argument, NULL, 0}
};
bool _processOptions( int argc, char *argv[] )
{
    int c, optionIndex = 0;
    while ( ( c = getopt_long ( argc, argv, "C:Ef:de:hVt:v:", _longOptions, &optionIndex ) ) != -1 )
        switch ( c )
        {
            // ------------------------------------
            case 'C':
                options.cps = atoi( optarg ) * 1000;
                break;

            // ------------------------------------
            case 'h':
                fprintf( stdout, "Usage: %s [options]" EOL, argv[0] );
                fprintf( stdout, "    -C, --cpufreq:      <Frequency in KHz> (Scaled) speed of the CPU" EOL );
                fprintf( stdout, "    -f, --input-file:   <filename> Take input from specified file" EOL );
                fprintf( stdout, "    -h, --help:         This help" EOL );
                fprintf( stdout, "    -e, --elf:          <file>: Use this ELF file for information" EOL );
                fprintf( stdout, "    -d, --debug:        Output a human-readable protobuf file" EOL );
                fprintf( stdout, "    -t, --tpiu:         <channel>: Use TPIU decoder on specified channel (normally 1)" EOL );
                fprintf( stdout, "    -v, --verbose:      <level> Verbose mode 0(errors)..3(debug)" EOL );
                fprintf( stdout, "    -V, --version:      Print version and exit" EOL );
                return false;

            // ------------------------------------
            case 'V':
                genericsPrintf( "orbcat version " GIT_DESCRIBE EOL );
                return false;

            // ------------------------------------
            case 'd':
                options.outputDebugFile = true;
                break;

            // ------------------------------------
            case 'f':
                options.file = optarg;
                break;

            // ------------------------------------
            case 'e':
                options.elfFile = optarg;
                break;

            // ------------------------------------
            case 't':
                options.useTPIU = true;
                options.tpiuChannel = atoi( optarg );
                break;

            // ------------------------------------
            case 'v':
                if ( !isdigit( *optarg ) )
                {
                    genericsReport( V_ERROR, "-v requires a numeric argument." EOL );
                    return false;
                }

                genericsSetReportLevel( (enum verbLevel)atoi( optarg ) );
                break;

            // ------------------------------------
            case '?':
                if ( optopt == 'b' )
                {
                    genericsReport( V_ERROR, "Option '%c' requires an argument." EOL, optopt );
                }
                else if ( !isprint ( optopt ) )
                {
                    genericsReport( V_ERROR, "Unknown option character `\\x%x'." EOL, optopt );
                }

                return false;

            // ------------------------------------
            default:
                return false;
                // ------------------------------------
        }

    if ( ( options.useTPIU ) && ( !options.tpiuChannel ) )
    {
        genericsReport( V_ERROR, "TPIU set for use but no channel set for ITM output" EOL );
        return false;
    }

    genericsReport( V_INFO, "orbcat version " GIT_DESCRIBE EOL );

    if ( options.cps ) genericsReport( V_INFO, "S-CPU Speed: %d KHz" EOL, options.cps );
    else genericsReport( V_INFO, "S-CPU Speed Autodetection" EOL);

    genericsReport( V_INFO, "Input File : %s", options.file.c_str() );
    genericsReport( V_INFO, " (Terminate on exhaustion)" EOL );

    if ( options.useTPIU )
    {
        genericsReport( V_INFO, "Using TPIU : true (ITM on channel %d)" EOL, options.tpiuChannel );
    }
    else
    {
        genericsReport( V_INFO, "Using TPIU : false" EOL );
    }

    return true;
}

// ====================================================================================================
int main(int argc, char *argv[])
{
    if ( !_processOptions( argc, argv ) )
    {
        exit( -1 );
    }

    /* Reset the TPIU handler before we start */
    TPIUDecoderInit( &_r.t );
    ITMDecoderInit( &_r.i, true );
    MSGSeqInit( &_r.d, &_r.i, MSG_REORDER_BUFLEN );

    device = Device(options.elfFile);
    assert(device.valid());
    if (options.cps == 0) options.cps = device.clock();

    perfetto_trace = new perfetto::protos::Trace();
    auto *ftrace_packet = perfetto_trace->add_packet();
    ftrace_packet->set_trusted_packet_sequence_id(42);
    ftrace_packet->set_sequence_flags(1);
    ftrace = ftrace_packet->mutable_ftrace_events();
    ftrace->set_cpu(0);

    struct Stream *stream = streamCreateFile( options.file.c_str() );
    genericsReport( V_INFO, "PreProcess Stream" EOL );
    while ( true )
    {
        size_t receivedSize;
        struct timeval t;
        unsigned char cbw[TRANSFER_SIZE];
        t.tv_sec = 0;
        t.tv_usec = 10000;
        enum ReceiveResult result = stream->receive( stream, cbw, TRANSFER_SIZE, &t, &receivedSize );

        if (result == RECEIVE_RESULT_EOF or result == RECEIVE_RESULT_ERROR) break;

        unsigned char *c = cbw;
        while (receivedSize--) _protocolPump(*c++,_itmPumpProcessPre,NULL); //_itmPumpProcessPre(*c++);
        fflush(stdout);
    }
    stream->close(stream);
    free(stream);


    printf("Loading ELF file %s with%s source lines\n", options.elfFile.c_str(), has_pc_samples ? "" : "out");
    _r.symbols = symbolAcquire((char*)options.elfFile.c_str(), true, has_pc_samples);
    assert( _r.symbols );
    mortrall.init(perfetto_trace,ftrace,options.cps,_r.symbols);
    
    printf("Loaded ELF with %u sections:\n", _r.symbols->nsect_mem);
    for (int ii = 0; ii < _r.symbols->nsect_mem; ii++)
    {
        auto mem = _r.symbols->mem[ii];
        printf("  Section '%s': [0x%08lx, 0x%08lx] (%lu)\n", mem.name, mem.start, mem.start + mem.len, mem.len);
    }

    stream = streamCreateFile( options.file.c_str() );
    genericsReport( V_INFO, "Process Stream" EOL );
    while ( true )
    {
        size_t receivedSize;
        struct timeval t;
        unsigned char cbw[TRANSFER_SIZE];
        t.tv_sec = 0;
        t.tv_usec = 10000;
        enum ReceiveResult result = stream->receive( stream, cbw, TRANSFER_SIZE, &t, &receivedSize );

        if (result == RECEIVE_RESULT_EOF or result == RECEIVE_RESULT_ERROR) break;

        unsigned char *c = cbw;
        while (receivedSize--) _protocolPump(*c++,_itmPumpProcess,mortrall.dumpElement);
        fflush(stdout);
    }
    stream->close(stream);
    free(stream);

    {
        auto *interned_data = ftrace_packet->mutable_interned_data();
        for (auto&& [addr, name] : workqueue_names)
        {
            auto *interned_string = interned_data->add_kernel_symbols();
            interned_string->set_iid(addr);
            interned_string->set_str(name.c_str());
        }
        if (has_pc_samples)
        {
            for (auto&& [addr, name] : function_names)
            {
                {
                    auto *interned_string = interned_data->add_kernel_symbols();
                    interned_string->set_iid(addr);
                    interned_string->set_str(name.c_str());
                }
            }
        }
    }

    {
        auto *packet = perfetto_trace->add_packet();
        packet->set_trusted_packet_sequence_id(42);
        auto *process_tree = packet->mutable_process_tree();
        {
            auto *process = process_tree->add_processes();
            process->set_pid(PID_TSK);
            process->add_cmdline("Threads");
            for (auto&& tid : active_threads)
            {
                if (tid == 0) continue;
                auto *thread = process_tree->add_threads();
                thread->set_tid(tid);
                thread->set_tgid(PID_TSK);
            }
            auto *thread = process_tree->add_threads();
            thread->set_tid(100);
            thread->set_tgid(PID_TSK);
        }
        {
            auto *process = process_tree->add_processes();
            process->set_pid(PID_STOP);
            process->add_cmdline("Threads (Stopped)");
            for (auto&& tid : stopped_threads)
            {
                if (tid == 0) continue;
                auto *thread = process_tree->add_threads();
                thread->set_tid(PID_STOP + tid);
                thread->set_tgid(PID_STOP);
            }
        }
        if (has_pc_samples)
        {
            auto *process = process_tree->add_processes();
            process->set_pid(PID_PC);
            process->add_cmdline("PC");
            for (auto&& tid : active_threads)
            {
                if (tid == 0) continue;
                auto *thread = process_tree->add_threads();
                thread->set_tid(PID_PC + tid);
                thread->set_tgid(PID_PC);
                thread->set_name(thread_names[tid]);
            }
        }
        if (has_pc_samples)
        {
            auto *process = process_tree->add_processes();
            process->set_pid(PID_PC + PID_STOP);
            process->add_cmdline("PC (stopped)");
            for (auto&& tid : stopped_threads)
            {
                if (tid == 0) continue;
                auto *thread = process_tree->add_threads();
                thread->set_tid(PID_PC + PID_STOP + tid);
                thread->set_tgid(PID_PC + PID_STOP);
                thread->set_name(thread_names[PID_STOP + tid]);
            }
        }
        {
            auto *process = process_tree->add_processes();
            process->set_pid(PID_DMA);
            process->add_cmdline("DMA Channels");
            for (int ctrl=0; ctrl <= 3; ctrl++)
            {
                for (int chan=0; chan < 8; chan++)
                {
                    char buffer[100];
                    snprintf(buffer, sizeof(buffer), "DMA%u CH%u", ctrl, chan);
                    auto *thread = process_tree->add_threads();
                    thread->set_tid(PID_DMA + ctrl * 100 + chan);
                    thread->set_tgid(PID_DMA);
                    thread->set_name(buffer);
                }
            }
        }
        {
            auto *process = process_tree->add_processes();
            process->set_pid(PID_UART);
            process->add_cmdline("UARTs");
            for (int chan=0; chan < 10; chan++)
            {
                auto *thread = process_tree->add_threads();
                thread->set_tid(PID_UART + chan);
                thread->set_tgid(PID_UART);
                char buffer[100];
                snprintf(buffer, sizeof(buffer), "UART%u %sX", chan/2, (chan & 0b1) ? "R" : "T");
                thread->set_name(buffer);
            }
        }
        {
            auto *process = process_tree->add_processes();
            process->set_pid(PID_SEMAPHORE);
            process->add_cmdline("Semaphores");
            // for (auto&& [addr, count] : semaphores)
            // {
            //     auto *thread = process_tree->add_threads();
            //     thread->set_tid(PID_SEMAPHORE + addr);
            //     thread->set_tgid(PID_SEMAPHORE);
            //     char buffer[100];
            //     snprintf(buffer, sizeof(buffer), "Semaphore %#08x", addr);
            //     thread->set_name(buffer);
            // }
        }
        mortrall.finalize(process_tree);
    }


    if ( options.outputDebugFile )
    {
        printf("Dumping debug output to 'orbetto.debug'\n");
        std::ofstream perfetto_debug("orbetto.debug", std::ios::out);
        perfetto_debug << perfetto_trace->DebugString();
        perfetto_debug.close();
    }

    printf("Serializing into 'orbetto.perf'\n");
    std::ofstream perfetto_file("orbetto.perf", std::ios::out | std::ios::binary);
    perfetto_trace->SerializeToOstream(&perfetto_file);
    perfetto_file.close();
    delete perfetto_trace;

    return 0;
}
// ====================================================================================================
