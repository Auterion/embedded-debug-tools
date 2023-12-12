// Copyright (c) 2019-2023, Orbcode Project
// Copyright (c) 2023, Auterion AG
// SPDX-License-Identifier: BSD-3-Clause
// This file is a modified version of orbuculum/orbcat.c

#include <stdlib.h>
#include <unistd.h>
#include <ctype.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include <inttypes.h>
#include <getopt.h>
#include <time.h>
#include <set>
#include <iostream>
#include <fstream>

#include "nw.h"
#include "git_version_info.h"
#include "generics.h"
#include "tpiuDecoder.h"
#include "itmDecoder.h"
#include "msgDecoder.h"
#include "msgSeq.h"
#include "stream.h"
#include "loadelf.h"

#include <protos/perfetto/trace/trace.pb.h>
#include <protos/perfetto/trace/trace_packet.pb.h>
#include <protos/perfetto/trace/trace_packet_defaults.pb.h>

#define NUM_CHANNELS  32
#define HW_CHANNEL    (NUM_CHANNELS)      /* Make the hardware fifo on the end of the software ones */

#define MAX_STRING_LENGTH (100)           /* Maximum length that will be output from a fifo for a single event */
#define DEFAULT_TS_TRIGGER '\n'           /* Default trigger character for timestamp output */

#define MSG_REORDER_BUFLEN  (10)          /* Maximum number of samples to re-order for timekeeping */
#define ONE_SEC_IN_USEC     (1000000)     /* Used for time conversions...usec in one sec */

/* Formats for timestamping */
#define REL_FORMAT            "%6" PRIu64 ".%01" PRIu64 "|"
#define REL_FORMAT_INIT       "   Initial|"
#define DEL_FORMAT            "%3" PRIu64 ".%03" PRIu64 "|"
#define DEL_FORMAT_CTD           "      +|"
#define DEL_FORMAT_INIT          "Initial|"
#define ABS_FORMAT_TM   "%d/%b/%y %H:%M:%S"
#define ABS_FORMAT              "%s.%03" PRIu64" |"
#define STAMP_FORMAT          "%12" PRIu64 "|"
#define STAMP_FORMAT_MS        "%8" PRIu64 ".%03" PRIu64 "_%03" PRIu64 "|"
#define STAMP_FORMAT_MS_DELTA  "%5" PRIu64 ".%03" PRIu64 "_%03" PRIu64 "|"

enum TSType { TSNone, TSAbsolute, TSRelative, TSDelta, TSStamp, TSStampDelta, TSNumTypes };
const char *tsTypeString[TSNumTypes] = { "None", "Absolute", "Relative", "Delta", "System Timestamp", "System Timestamp Delta" };

// Record for options, either defaults or from command line
struct Options
{
    /* Config information */
    bool useTPIU;
    uint32_t tpiuChannel;
    bool forceITMSync;
    uint64_t cps;                            /* Cycles per second for target CPU */

    enum TSType tsType;
    char *tsLineFormat;
    char tsTrigger;

    /* Sink information */
    char *presFormat[NUM_CHANNELS + 1];

    /* Source information */
    int port;
    char *server;

    /* SWO File name */
    char *file;                              /* File host connection */
    std::string std_file;

    bool endTerminate;                       /* Terminate when file/socket "ends" */

    /* Binary elf_file */
    std::vector<uint8_t>* elf_file;

    bool outputDebugFile;

    /* Parsed functions */
    std::vector<std::tuple<int32_t,std::string>> functions; /* Parsed function tuple from elf file (shape: #func * [addr,func_name])*/

    /* SPI Debug */
    std::vector<std::tuple<uint64_t,uint32_t>> mosi_digital;
    std::vector<std::tuple<uint64_t,uint32_t>> miso_digital;
    std::vector<std::tuple<uint64_t,uint32_t>> clk_digital;
    std::vector<std::tuple<uint64_t,uint32_t>> cs_digital;
    std::vector<std::tuple<uint64_t,uint64_t,std::vector<uint8_t>>> spi_decoded_mosi; /* Decoded spi data packets (shape: #data_packets * [timestamp_start,timestamp_end,data])*/
    std::vector<std::tuple<uint64_t,uint64_t,std::vector<uint8_t>>> spi_decoded_miso; /* Decoded spi data packets (shape: #data_packets * [timestamp_start,timestamp_end,data])*/
    std::vector<std::vector<std::tuple<uint64_t,uint64_t>>> workqueue_intervals_spi; 
    /* SPI Sync */
    std::vector<std::tuple<uint64_t,uint64_t>> workqueue_intervals_swo;
    uint64_t workqueue_last_switch_swo;
    std::vector<std::tuple<uint64_t,uint32_t>> sync_digital;

} options =
{
    .tpiuChannel = 1,
    .forceITMSync = true,
    .tsTrigger = DEFAULT_TS_TRIGGER,
    .port = NWCLIENT_SERVER_PORT,
    .server = (char *)"localhost",
    .workqueue_last_switch_swo = 0,
};

struct PyOptions
{
    uint64_t cps;
    enum TSType tsType;
    std::string std_file;
    bool endTerminate; 
    std::vector<uint8_t> elf_file;
    bool outputDebugFile;
    std::vector<std::tuple<int32_t,std::string>> functions; /* Parsed function tuple from elf file (shape: #func * [addr,func_name])*/
    std::vector<std::tuple<uint64_t,uint32_t>> mosi_digital;
    std::vector<std::tuple<uint64_t,uint32_t>> miso_digital;
    std::vector<std::tuple<uint64_t,uint32_t>> clk_digital;
    std::vector<std::tuple<uint64_t,uint32_t>> cs_digital;
    std::vector<std::tuple<uint64_t,uint64_t,std::vector<uint8_t>>> spi_decoded_mosi; /* Decoded spi data packets (shape: #data_packets * [timestamp_start,timestamp_end,data])*/
    std::vector<std::tuple<uint64_t,uint64_t,std::vector<uint8_t>>> spi_decoded_miso; /* Decoded spi data packets (shape: #data_packets * [timestamp_start,timestamp_end,data])*/
    std::vector<std::vector<std::tuple<uint64_t,uint64_t>>> workqueue_intervals_spi;
    std::vector<std::tuple<uint64_t,uint32_t>> sync_digital;
};


struct
{
    /* The decoders and the packets from them */
    struct ITMDecoder i;
    struct MSGSeq    d;
    struct ITMPacket h;
    struct TPIUDecoder t;
    struct TPIUPacket p;
    enum timeDelay timeStatus;           /* Indicator of if this time is exact */
    uint64_t timeStamp;                  /* Latest received time */
    uint64_t lastTimeStamp;              /* Last received time */
    uint64_t te;                         /* Time on host side for line stamping */
    bool gotte;                          /* Flag that we have the initial time */
    bool inLine;                         /* We are in progress with a line that has been timestamped already */
    uint64_t oldte;                      /* Old time for interval calculation */
    struct symbol *symbols;              /* symbols from the elf file */
} _r;

// ====================================================================================================
int64_t _timestamp( void )
{
    struct timeval te;
    gettimeofday( &te, NULL ); // get current time
    return te.tv_sec * ONE_SEC_IN_USEC + te.tv_usec;
}
// ====================================================================================================
// ====================================================================================================
// ====================================================================================================
// Handler for individual message types from SWO
// ====================================================================================================
// ====================================================================================================
// ====================================================================================================

static perfetto::protos::Trace *perfetto_trace;

static perfetto::protos::FtraceEventBundle *ftrace;
static perfetto::protos::TracePacket *ftrace_packet;

static std::unordered_map<int32_t, const char*> *irq_names = nullptr;

static constexpr uint16_t PID_TSK{0};
static constexpr uint16_t PID_STOP{10000};
static constexpr uint32_t PID_PC{200000};
static constexpr uint32_t PID_SPI{300000};
static uint16_t prev_tid{0};
static std::unordered_map<uint16_t, std::string> active_threads;

static void _switchTo(uint16_t tid, bool begin, int priority = -1, int prev_state = -1)
{
    if (begin)
    {
        auto *event = ftrace->add_event();
        event->set_timestamp((_r.timeStamp * 1e9) / options.cps);
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
    }
}

static std::unordered_map<uint32_t, uint32_t> heap_regions;
static std::unordered_map<uint32_t, std::pair<uint32_t, uint32_t>> heap_allocations;
static uint32_t heap_size_total{0};
static uint32_t heap_size_remaining{0};
static uint32_t heap_packet_index{0};
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
    event->set_timestamp((_r.timeStamp * 1e9) / options.cps);
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
    event->set_timestamp((_r.timeStamp * 1e9) / options.cps);
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
static void _handleSW( struct swMsg *m, struct ITMDecoder *i )
{
    assert( m->msgtype == MSG_SOFTWARE );
    const uint64_t ns = (_r.timeStamp * 1e9) / options.cps;

    static std::string thread_name;
    uint16_t tid = (m->value & 0xfffful);
    const bool tid_tl = tid > 3000;
    if (stopped_threads.contains(tid)) tid += PID_STOP;
    else if (tid != 0) tid += PID_TSK;

    
    if (m->srcAddr == 0) // start
    {
        if (m->len == 4) {
            char name[5]{0,0,0,0,0};
            memcpy(name, &m->value, 4);
            thread_name += name;
        }
        if (m->len == 2) {
            if (tid_tl) {
                thread_name.clear();
                return;
            }
            if (not thread_name.empty())
            {
                if (active_threads.contains(tid))
                {
                    if (active_threads[tid] != thread_name and tid != 0)
                    {
                        {
                            auto *event = ftrace->add_event();
                            event->set_timestamp(ns);
                            event->set_pid(tid);
                            auto *renametask = event->mutable_task_rename();
                            renametask->set_pid(tid);
                            renametask->set_newcomm(thread_name.c_str());
                        }
                        // Do the same for PC Thread
                        {
                            auto *event = ftrace->add_event();
                            event->set_timestamp(ns);
                            event->set_pid(PID_PC + tid);
                            auto *renametask = event->mutable_task_rename();
                            renametask->set_pid(PID_PC + tid);
                            renametask->set_newcomm(thread_name.c_str());
                        }
                    }
                }
                else if (tid != 0)
                {
                    static std::set<uint32_t> seen_tids;
                    if (not seen_tids.contains(tid))
                    {
                        {
                            seen_tids.insert(tid);
                            auto *event = ftrace->add_event();
                            event->set_timestamp(ns);
                            event->set_pid(prev_tid);
                            auto *newtask = event->mutable_task_newtask();
                            newtask->set_pid(tid);
                            newtask->set_comm(thread_name.c_str());
                            newtask->set_clone_flags(0x10000); // new thread, not new process!
                        }
                        {
                            // Do the same for PC Thread
                            auto *event = ftrace->add_event();
                            event->set_timestamp(ns);
                            event->set_pid(prev_tid);
                            auto *renametask = event->mutable_task_rename();
                            renametask->set_pid(PID_PC + tid);
                            renametask->set_newcomm(thread_name.c_str());
                        }
                    }
                }
                active_threads.insert({tid, thread_name});
            }
            thread_name.clear();
        }
    }
    else if (m->srcAddr == 1) // stop
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
    }
    else if (m->srcAddr == 2) // suspend
    {
        if (tid_tl) return;
        if (not active_threads.contains(tid)) return;
        _switchTo(0, true);
    }
    else if (m->srcAddr == 3) // resume
    {
        if (tid_tl) return;
        if (not active_threads.contains(tid)) return;
        const uint8_t priority = m->value >> 16;
        const uint8_t prev_state = m->value >> 24;
        _switchTo(tid, true, priority, prev_state);
    }
    else if (m->srcAddr == 4) // ready
    {
        if (tid_tl) return;
        auto *event = ftrace->add_event();
        event->set_timestamp(ns);
        event->set_pid(prev_tid);
        auto *sched_waking = event->mutable_sched_waking();
        sched_waking->set_pid(tid);
        sched_waking->set_success(1);
    }
    else if (m->srcAddr == 15) // workqueue start
    {
        if (prev_tid == 0) return;
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
        workqueue_map.insert({prev_tid, m->value});
        if (not workqueue_names.contains(m->value))
        {
            if(options.elf_file == nullptr) {
                printf("No elf file found.\n");
            }else if (const char *name = (const char *) &(*options.elf_file)[m->value - 0x08008000]; name)
            {
                printf("Found Name %s for 0x%08x\n", name, m->value);
                workqueue_names.insert({m->value, name});
            }
            else {
                printf("No match found for 0x%08x\n", m->value);
            }
        }
    }
    else if (m->srcAddr == 16) // workqueue stop
    {
        if (prev_tid == 0) return;
        if (workqueue_map.contains(prev_tid))
        {
            auto *event = ftrace->add_event();
            event->set_timestamp(ns);
            event->set_pid(prev_tid);
            event->mutable_workqueue_execute_end();
            workqueue_map.erase(prev_tid);
            // const uint8_t count = m->value;
        }
    }
    else if (m->srcAddr == 17) // heap region
    {
        static uint32_t start = 0;
        if (m->value & 0x80000000) {
            start = m->value & ~0x80000000;
        }
        else if (start)
        {
            const uint32_t end = start + m->value;
            heap_regions.insert({start, end});
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
    }
    else if (m->srcAddr == 18 || m->srcAddr == 19) // malloc attempt and result
    {
        static uint32_t size = 0;
        static uint32_t alignsize = 0;
        if (m->srcAddr == 18) {
            size = m->value;
            alignsize = ((size + 16) + 0xf) & ~0xf;
        }
        else {
            if (m->value) heap_allocations.insert({m->value, {size, alignsize}});
            else printf("malloc(%uB) failed!\n", size);
            _writeMalloc(ns, m->value, alignsize, size);
        }
    }
    else if (m->srcAddr == 20) // free
    {
        if (heap_allocations.contains(m->value))
        {
            const auto [size, alignsize] = heap_allocations[m->value];
            heap_allocations.erase(m->value);
            _writeFree(ns, m->value, alignsize, size);
        }
        else printf("Unknown size for free(0x%08x)!\n", m->value);
    }
}
// ====================================================================================================
static void _handleTS( struct TSMsg *m, struct ITMDecoder *i )
{
    assert( m->msgtype == MSG_TS );
    _r.timeStamp += m->timeInc;
}

static void _handleExc( struct excMsg *m, struct ITMDecoder *i )
{
    assert( m->msgtype == MSG_EXCEPTION );
    if (m->eventType == EXEVENT_UNKNOWN) return;
    const uint32_t irq = m->exceptionNumber;
    if (irq > 16+149) return;
    // [enter (1) -----> exit (2), resume (3)]
    const bool begin = m->eventType == EXEVENT_ENTER;
    const uint64_t ns = (_r.timeStamp * 1e9) / options.cps;

    // filter out a RESUME, if EXIT was already received
    static std::unordered_map<uint16_t, bool> irq_state;
    if (irq_state.contains(irq) and
        not irq_state[irq] and not begin)
        return;
    irq_state.insert({irq, begin});

    static uint32_t last_irq{0};
    static bool last_begin{false};
    // we need to close the previous IRQ
    if (last_begin and begin)
    {
        auto *event = ftrace->add_event();
        event->set_timestamp(ns);
        event->set_pid(0);
        auto *exit = event->mutable_irq_handler_exit();
        exit->set_irq(last_irq);
        exit->set_ret(1);
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
        entry->set_name("unknown");
        if (irq_names->contains(irq))
            entry->set_name((*irq_names)[irq]);
    }
    else
    {
        auto *exit = event->mutable_irq_handler_exit();
        exit->set_irq(irq);
    }
}

uint64_t last_function_index = -1;
auto last_prev_tid = prev_tid;

static void _handlePc( struct pcSampleMsg *m, struct ITMDecoder *i )
{
    assert( m->msgtype == MSG_PC_SAMPLE );
    // check if pc is in idle task then skip
    if(prev_tid == 0) return;
    // find the new function name
    auto pc_function = std::lower_bound(options.functions.begin(), options.functions.end(), m->pc,
        [](const std::tuple<int32_t,std::string> addr_func_tuple, uint32_t value)
        {
            return get<0>(addr_func_tuple) < value;
        });
    // begin the new function in ftrace
    if (pc_function == options.functions.end()) 
    {
        printf("For PC at 0x%08x no Function name could be found.\n", m->pc);
    }else
    {
        uint64_t index = get<0>(*pc_function);
        std::string function_name = get<1>(*pc_function);
        // printf("Function: %s\n", function_name.c_str());
        if(index==last_function_index and prev_tid==last_prev_tid) return;
        // end the last function in ftrace
        if(last_function_index != (uint64_t)-1){
            auto *event = ftrace->add_event();
            event->set_timestamp((_r.timeStamp * 1e9) / options.cps);
            event->set_pid(PID_PC + last_prev_tid);
            auto *exit = event->mutable_funcgraph_exit();
            exit->set_depth(0);
            exit->set_func(last_function_index);
        }
        // start ftrace event
        {
            auto *event = ftrace->add_event();
            event->set_timestamp((_r.timeStamp * 1e9) / options.cps);
            event->set_pid(PID_PC + prev_tid);
            auto *entry = event->mutable_funcgraph_entry();
            entry->set_depth(0);
            entry->set_func(index);
            // save last event
            last_prev_tid = prev_tid;
            last_function_index = index;
        }
    }

}

// ====================================================================================================
static void _itmPumpProcessPre( char c )
{
    struct msg p;
    if ( ITM_EV_PACKET_RXED == ITMPump( &_r.i, c ) )
    {
        if ( ITMGetDecodedPacket( &_r.i, &p )  )
        {
            assert( p.genericMsg.msgtype < MSG_NUM_MSGS );

            if ( p.genericMsg.msgtype == MSG_SOFTWARE )
            {
                struct swMsg *m = (struct swMsg *)&p;
                if (m->srcAddr == 1) // stop
                {
                    stopped_threads.insert(m->value);
                    // printf("Thread %u stopped\n", m->value);
                }
                else if (m->srcAddr == 15) // workqueue start
                {
                    const uint64_t ns = (_r.timeStamp * 1e9) / options.cps;
                    if(options.workqueue_last_switch_swo == 0)
                    {
                        options.workqueue_last_switch_swo = ns;
                        printf("First workqueue start at %llu\n", ns);
                    }else
                    {
                        options.workqueue_intervals_swo.push_back(std::make_tuple(options.workqueue_last_switch_swo, ns-options.workqueue_last_switch_swo));
                        options.workqueue_last_switch_swo = ns;
                    }
                }
            }
            else if(p.genericMsg.msgtype == MSG_TS)
            {
                struct TSMsg *m = (struct TSMsg *)&p;
                _r.timeStamp += m->timeInc;
            }
        }
    }
}

static void _itmPumpProcess( char c )

{
    struct msg p;
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

    /* For any mode except the ones where we collect timestamps from the target we need to send */
    /* the samples out directly to give the host a chance of having accurate timing info. For   */
    /* target-based timestamps we need to re-sequence the messages so that the timestamps are   */
    /* issued _before_ the data they apply to.  These are the two cases.                        */

    if ( ( options.tsType != TSStamp ) && ( options.tsType != TSStampDelta ) )
    {
        if ( ITM_EV_PACKET_RXED == ITMPump( &_r.i, c ) )
        {
            if ( ITMGetDecodedPacket( &_r.i, &p )  )
            {
                assert( p.genericMsg.msgtype < MSG_NUM_MSGS );

                if ( h[p.genericMsg.msgtype] )
                {
                    ( h[p.genericMsg.msgtype] )( &p, &_r.i );
                }
            }
        }
    }
    else
    {

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
}
// ====================================================================================================
// ====================================================================================================
// ====================================================================================================
// Protocol pump for decoding messages
// ====================================================================================================
// ====================================================================================================
// ====================================================================================================
static void _protocolPump( uint8_t c )

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
                    if ( _r.p.packet[g].s == options.tpiuChannel )
                    {
                        _itmPumpProcess( _r.p.packet[g].d );
                        continue;
                    }

                    if  ( _r.p.packet[g].s != 0 )
                    {
                        genericsReport( V_DEBUG, "Unknown TPIU channel %02x" EOL, _r.p.packet[g].s );
                    }
                }

                break;

            case TPIU_EV_ERROR:
                genericsReport( V_WARN, "****ERROR****" EOL );
                break;
        }
    }
    else
    {
        _itmPumpProcess( c );
    }
}

// ====================================================================================================
static void _printVersion( void )

{
    genericsPrintf( "orbcat version " GIT_DESCRIBE EOL );
}

// ====================================================================================================
static struct Stream *_tryOpenStream()
{
    if ( options.file != NULL )
    {
        return streamCreateFile( options.file );
    }
    else
    {
        return streamCreateSocket( options.server, options.port );
    }
}

// ====================================================================================================
int64_t offset;
double drift;
uint64_t sync_point;
static uint64_t _apply_offset_and_drift(uint64_t timestamp)
{
    uint64_t timestamp_offset = timestamp + offset;
    int64_t drift_offset = (int64_t)((((double)timestamp_offset - (double)sync_point)) * drift);
    timestamp_offset -= drift_offset;
    return timestamp_offset;
}
static void counter_to_print(bool data,uint32_t pid,uint64_t timestamp)
{
    if(data)
    {
        // create Ftrace event
        auto *event = ftrace->add_event();
        event->set_timestamp(_apply_offset_and_drift(timestamp));
        event->set_pid(pid);
        auto *print = event->mutable_print();
        char buffer[20];
        snprintf(buffer, sizeof(buffer), "B|0| ");
        print->set_buf(buffer);
    }else
    {
        // create Ftrace event
        auto *event = ftrace->add_event();
        event->set_timestamp(_apply_offset_and_drift(timestamp));
        event->set_pid(pid);
        auto *print = event->mutable_print();
        char buffer[20];
        snprintf(buffer, sizeof(buffer), "E|0");
        print->set_buf(buffer);
    }
}

static void _sync_digital_prints()
{
    for(const auto& [timestamp, sync] : options.sync_digital)
    {
        counter_to_print((bool)sync, PID_SPI + 2, timestamp);
    }
}

static void _spi_digital_prints()
{
    // Proccess SPI Digital intro perfetto trace
    // iterate over all samples of digital data array and generate a perfetto trace count event for each
    for(const auto& [timestamp, data] : options.mosi_digital)
    {
        counter_to_print((bool)data, PID_SPI + 6,timestamp);
    }
    for (const auto& [timestamp, data] : options.miso_digital)
    {
        counter_to_print((bool)data, PID_SPI + 5,timestamp);
    }
    for (const auto& [timestamp, data] : options.clk_digital)
    {
        counter_to_print((bool)data, PID_SPI + 4,timestamp);
    }
    for (const auto& [timestamp, data] : options.cs_digital)
    {
        counter_to_print((bool)data, PID_SPI + 3,timestamp);
    }
}

static void _spi_decoded()
{
    // Proccess SPI Decoded intro perfetto trace
    if (options.spi_decoded_mosi.size() > 0)
    {
        // iterate over all samples of analog data array and generate a perfetto trace count event for each
        for(const auto& [timestamp_start, timestamp_end, data] : options.spi_decoded_mosi)
        {
            std::string data_string = " ";
            for (const auto i : data)
            {
                data_string += "0x" + std::to_string(i) + ", ";
            }
            {
                // only print cs if smaller than 30.0f
                auto *event = ftrace->add_event();
                event->set_timestamp(_apply_offset_and_drift(timestamp_start));
                event->set_pid(PID_SPI + 1);
                auto *print = event->mutable_print();
                char buffer[300];
                snprintf(buffer, 300, "B|0|Decoded MOSI|%s", data_string.c_str());
                print->set_buf(buffer);
            }
            {
                // only print cs if smaller than 30.0f
                auto *event = ftrace->add_event();
                event->set_timestamp(_apply_offset_and_drift(timestamp_end));
                event->set_pid(PID_SPI + 1);
                auto *print = event->mutable_print();
                char buffer[300];
                snprintf(buffer, 300, "E|0|Decoded MOSI|%s", data_string.c_str());
                print->set_buf(buffer);
            }
        }
    }
    if (options.spi_decoded_miso.size() > 0) 
    {
        // iterate over all samples of analog data array and generate a perfetto trace count event for each
        for(const auto& [timestamp_start, timestamp_end, data] : options.spi_decoded_miso)
        {
            std::string data_string = " ";
            for (const auto i : data)
            {
                data_string += "0x" + std::to_string(i) + ", ";
            }
            {
                // only print cs if smaller than 30.0f
                auto *event = ftrace->add_event();
                event->set_timestamp(_apply_offset_and_drift(timestamp_start));
                event->set_pid(PID_SPI + 1);
                auto *print = event->mutable_print();
                char buffer[100];
                snprintf(buffer, 100, "B|0|Decoded MISO|%s", data_string.c_str());
                print->set_buf(buffer);
            }
            {
                // only print cs if smaller than 30.0f
                auto *event = ftrace->add_event();
                event->set_timestamp(_apply_offset_and_drift(timestamp_end));
                event->set_pid(PID_SPI + 1);
                auto *print = event->mutable_print();
                char buffer[100];
                snprintf(buffer, 100, "E|0|Decoded MISO|%s", data_string.c_str());
                print->set_buf(buffer);
            }
        }
    }
}

static std::vector<std::tuple<uint64_t,uint64_t>> find_matching_pattern(){
    printf("Synchronise SWO and SPI ...\n");
    std::vector<std::tuple<uint64_t,uint64_t>> pattern_stats;
    // loop over each pattern
    for (auto spi_pattern : options.workqueue_intervals_spi)
    {
        int window_length = spi_pattern.size();
        printf("\t Window length: %d\n", window_length);
        uint64_t min_sum = (uint64_t)-1;
        int min_sum_index = -1;
        uint64_t second_min_sum = (uint64_t)-1;
        uint64_t min_total_sum = 0;
        // loop over options.workqueue_intervals_swo and compute abs sum of intervals
        for(int i = 0;i<options.workqueue_intervals_swo.size()-window_length;i++)
        {
            uint64_t sum = 0;
            uint64_t total_sum = 0;
            for(int j = 0;j<window_length;j++)
            {
                int diff = std::get<1>(options.workqueue_intervals_swo[i+j])-std::get<1>(spi_pattern[j]);
                sum += abs(diff);
                total_sum += std::get<1>(options.workqueue_intervals_swo[i+j]);
            }
            if(sum < min_sum)
            {
                second_min_sum = min_sum;
                min_sum = sum;
                min_sum_index = i;
                min_total_sum = total_sum;
            }
        }
        printf("\t Min Offset: %llu\n", min_sum);
        printf("\t Second Min Offset: %llu\n", second_min_sum);
        printf("\t Min Offset Index: %d\n", min_sum_index);
        if(min_total_sum !=0)
        {
            printf("\t Min Offset Ratio: %f'%%'\n", (float)min_sum/min_total_sum*100);
        }
        // print overlapping intervals
        for(int i = 0;i<window_length;i++)
        {
            int diff = std::get<1>(options.workqueue_intervals_swo[min_sum_index+i])-std::get<1>(spi_pattern[i]);
            double rel_diff = (double)diff/((std::get<1>(spi_pattern[i])+std::get<1>(options.workqueue_intervals_swo[min_sum_index+i]))/2);
            printf("\t\t SWO: %llu, SPI: %llu, DIFF: %i, REL DIFF: %f\n", std::get<1>(options.workqueue_intervals_swo[min_sum_index+i]),std::get<1>(spi_pattern[i]), diff,rel_diff);
        }
        uint64_t swo_start = std::get<0>(options.workqueue_intervals_swo[min_sum_index]);
        uint64_t spi_start = std::get<0>(spi_pattern[0]);
        pattern_stats.push_back(std::make_tuple(swo_start, spi_start));
    }
    return pattern_stats;
}

// ====================================================================================================
static void _feedStream( struct Stream *stream )
{
    struct timeval t;
    unsigned char cbw[TRANSFER_SIZE];

    perfetto_trace = new perfetto::protos::Trace();
    ftrace_packet = perfetto_trace->add_packet();
    ftrace_packet->set_trusted_packet_sequence_id(6);
    ftrace_packet->set_sequence_flags(1);
    ftrace = ftrace_packet->mutable_ftrace_events();
    ftrace->set_cpu(0);



    if ( options.file != NULL )
    {
        while ( true )
        {
            size_t receivedSize;

            t.tv_sec = 0;
            t.tv_usec = 10000;
            enum ReceiveResult result = stream->receive( stream, cbw, TRANSFER_SIZE, &t, &receivedSize );

            if ( result != RECEIVE_RESULT_OK )
            {
                if ( result == RECEIVE_RESULT_EOF )
                {
                    break;
                }
                else if ( result == RECEIVE_RESULT_ERROR )
                {
                    break;
                }
            }

            unsigned char *c = cbw;

            while ( receivedSize-- )
            {
                _itmPumpProcessPre( *c++ );
            }

            fflush( stdout );
        }
        stream->close(stream);
        stream = streamCreateFile( options.file );
    }

    // reset timestamp for second swo parsing
    _r.timeStamp = 0;
    auto pattern_stats = find_matching_pattern();
    offset = std::get<1>(pattern_stats[0]) - std::get<0>(pattern_stats[0]);
    double nominator = ((double)(std::get<1>(pattern_stats[1])-(std::get<0>(pattern_stats[1])+offset)));
    double denominator = ((double)(std::get<0>(pattern_stats[1])-std::get<0>(pattern_stats[0])));
    drift = nominator /denominator;
    printf("SPI and SWO Clock drift %f per nano second.\n", drift);
    sync_point = std::get<1>(pattern_stats[0]);
    if(offset > 0)
    {
        printf("SPI is ahead of SWO by %llu nano seconds.\n", offset);
        _r.timeStamp = (uint64_t)(((double)offset) / 1e9 * options.cps);
        offset=0;
        //_spi_digital();
        _sync_digital_prints();
        _spi_digital_prints();
        _spi_decoded();
        //_sync_digital();
    }else
    {
        printf("SWO is ahead of SPI by %llu nano seconds.\n", -offset);
        offset=-offset;
        //_spi_digital();
        _sync_digital_prints();
        _spi_digital_prints();
        _spi_decoded();
        //_sync_digital();
    }

    while ( true )
    {
        size_t receivedSize;

        t.tv_sec = 0;
        t.tv_usec = 10000;
        enum ReceiveResult result = stream->receive( stream, cbw, TRANSFER_SIZE, &t, &receivedSize );

        if ( result != RECEIVE_RESULT_OK )
        {
            if ( result == RECEIVE_RESULT_EOF && options.endTerminate )
            {
                break;
            }
            else if ( result == RECEIVE_RESULT_ERROR )
            {
                break;
            }
        }

        unsigned char *c = cbw;

        while ( receivedSize-- )
        {
            _protocolPump( *c++ );
        }

        fflush( stdout );
    }
    {
        auto *interned_data = ftrace_packet->mutable_interned_data();
        for (auto&& [func, name] : workqueue_names)
        {
            {
                auto *interned_string = interned_data->add_kernel_symbols();
                interned_string->set_iid(func);
                interned_string->set_str(name.c_str());
            }
        }
    }
    {
        auto *interned_data = ftrace_packet->mutable_interned_data();
        for (auto&& [func, name] : options.functions)
        {
            {
                auto *interned_string = interned_data->add_kernel_symbols();
                interned_string->set_iid(func);
                interned_string->set_str(name.c_str());
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
            for (auto&& [tid, name] : active_threads)
            {
                if (tid == 0) continue;
                auto *thread = process_tree->add_threads();
                thread->set_tid(tid);
                thread->set_tgid(PID_TSK);
            }
        }
        {
            auto *process = process_tree->add_processes();
            process->set_pid(PID_STOP);
            process->add_cmdline("Threads (stopped)");
            for (auto&& tid : stopped_threads)
            {
                if (tid == 0) continue;
                auto *thread = process_tree->add_threads();
                thread->set_tid(tid);
                thread->set_tgid(PID_STOP);
            }
        }
        // Init Programm Counter Process with threads
        {
            auto *process = process_tree->add_processes();
            process->set_pid(PID_PC);
            process->add_cmdline("PC");
            for (auto&& [tid, name] : active_threads)
            {
                auto *thread = process_tree->add_threads();
                thread->set_tid(PID_PC + tid);
                thread->set_tgid(PID_PC);
            }
            for (auto&& tid : stopped_threads)
            {
                auto *thread = process_tree->add_threads();
                thread->set_tid(PID_PC + PID_STOP + tid);
                thread->set_tgid(PID_PC);
            }
        }
        // Init SPI Protocol Process with Channels as Threads
        {
            auto *process = process_tree->add_processes();
            process->set_pid(PID_SPI);
            process->add_cmdline("SPI");
            for(int channels = 6;channels>0;channels--)
            {
                auto *thread = process_tree->add_threads();
                thread->set_tid(PID_SPI + channels);
                thread->set_tgid(PID_SPI);
                char buffer[100];
                switch(channels)
                {
                    case 6:
                        snprintf(buffer, sizeof(buffer), "SPI MOSI");
                        break;
                    case 5:
                        snprintf(buffer, sizeof(buffer), "SPI MISO");
                        break;
                    case 4:
                        snprintf(buffer, sizeof(buffer), "SPI CLK");
                        break;
                    case 3:
                        snprintf(buffer, sizeof(buffer), "SPI CS");
                        break;
                    case 2:
                        snprintf(buffer, sizeof(buffer), "SPI Sync");
                        break;
                    case 1:
                        snprintf(buffer, sizeof(buffer), "SPI Decoded");
                        break;
                }
                thread->set_name(buffer);
            }
        }
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
}

// ====================================================================================================

int main()
{
    bool alreadyReported = false;

    /* Reset the TPIU handler before we start */
    TPIUDecoderInit( &_r.t );
    ITMDecoderInit( &_r.i, options.forceITMSync );
    MSGSeqInit( &_r.d, &_r.i, MSG_REORDER_BUFLEN );

    while ( true )
    {
        struct Stream *stream = NULL;

        while ( true )
        {
            stream = _tryOpenStream();

            if ( stream != NULL )
            {
                if ( alreadyReported )
                {
                    genericsReport( V_INFO, "Connected" EOL );
                    alreadyReported = false;
                }

                break;
            }

            if ( !alreadyReported )
            {
                genericsReport( V_INFO, EOL "No connection" EOL );
                alreadyReported = true;
            }

            if ( options.endTerminate )
            {
                break;
            }

            /* Checking every 100ms for a connection is quite often enough */
            usleep( 10000 );
        }

        if ( stream != NULL )
        {
            _feedStream( stream );
        }

        stream->close( stream );
        free( stream );

        if ( options.endTerminate )
        {
            break;
        }
    }

    return 0;
}

void main_pywrapper(PyOptions py_op, std::unordered_map<int32_t, const char*>* irq_names_input){
    // set option struct from python
    options.cps = py_op.cps;
    options.tsType = py_op.tsType;
    options.endTerminate = py_op.endTerminate;
    options.file = py_op.std_file.data();
    options.elf_file = &py_op.elf_file;
    options.outputDebugFile = py_op.outputDebugFile;
    options.functions = py_op.functions;
    options.mosi_digital = py_op.mosi_digital;
    options.miso_digital = py_op.miso_digital;
    options.clk_digital = py_op.clk_digital;
    options.cs_digital = py_op.cs_digital;
    options.spi_decoded_mosi = py_op.spi_decoded_mosi;
    options.spi_decoded_miso = py_op.spi_decoded_miso;
    options.workqueue_intervals_spi = py_op.workqueue_intervals_spi;
    options.sync_digital = py_op.sync_digital;

    irq_names = irq_names_input;
    // call main
    printf("Wrapping worked.\n");
    main();
}
// ====================================================================================================
