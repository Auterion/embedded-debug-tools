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

    char *file;                              /* File host connection */
    std::string std_file;
    bool endTerminate;                       /* Terminate when file/socket "ends" */

    std::vector<uint8_t>* elf_file;
    bool outputDebugFile;

} options =
{
    .tpiuChannel = 1,
    .forceITMSync = true,
    .tsTrigger = DEFAULT_TS_TRIGGER,
    .port = NWCLIENT_SERVER_PORT,
    .server = (char *)"localhost"
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

static std::unordered_map<int32_t, const char*> *irq_names = nullptr;

static constexpr uint16_t PID_TSK{0};
static constexpr uint16_t PID_STOP{10000};
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
                        auto *event = ftrace->add_event();
                        event->set_timestamp(ns);
                        event->set_pid(tid);
                        auto *renametask = event->mutable_task_rename();
                        renametask->set_pid(tid);
                        renametask->set_newcomm(thread_name.c_str());
                    }
                }
                else if (tid != 0)
                {
                    static std::set<uint32_t> seen_tids;
                    if (not seen_tids.contains(tid))
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

static void _handlePc( struct pcSampleMsg *m, struct ITMDecoder *i )
{
    assert( m->msgtype == MSG_PC_SAMPLE );
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
static void _printHelp( const char *const progName )

{
    fprintf( stdout, "Usage: %s [options]" EOL, progName );
    fprintf( stdout, "    -c, --channel:      <Number>,<Format> of channel to add into output stream (repeat per channel)" EOL );
    fprintf( stdout, "    -C, --cpufreq:      <Frequency in KHz> (Scaled) speed of the CPU" EOL
             "                        generally /1, /4, /16 or /64 of the real CPU speed," EOL );
    fprintf( stdout, "    -E, --eof:          Terminate when the file/socket ends/is closed, or wait for more/reconnect" EOL );
    fprintf( stdout, "    -f, --input-file:   <filename> Take input from specified file" EOL );
    fprintf( stdout, "    -g, --trigger:      <char> to use to trigger timestamp (default is newline)" EOL );
    fprintf( stdout, "    -h, --help:         This help" EOL );
    fprintf( stdout, "    -n, --itm-sync:     Enforce sync requirement for ITM (i.e. ITM needs to issue syncs)" EOL );
    fprintf( stdout, "    -s, --server:       <Server>:<Port> to use" EOL );
    fprintf( stdout, "    -e, --elf:          <file>: Use this ELF file for information" EOL );
    fprintf( stdout, "    -d, --debug:        Output a human-readable protobuf file" EOL );
    fprintf( stdout, "    -t, --tpiu:         <channel>: Use TPIU decoder on specified channel (normally 1)" EOL );
    fprintf( stdout, "    -T, --timestamp:    <a|r|d|s|t>: Add absolute, relative (to session start)," EOL
             "                        delta, system timestamp or system timestamp delta to output. Note" EOL
             "                        a,r & d are host dependent and you may need to run orbuculum with -H." EOL );
    fprintf( stdout, "    -v, --verbose:      <level> Verbose mode 0(errors)..3(debug)" EOL );
    fprintf( stdout, "    -V, --version:      Print version and exit" EOL );
}
// ====================================================================================================
static void _printVersion( void )

{
    genericsPrintf( "orbcat version " GIT_DESCRIBE EOL );
}
// ====================================================================================================
static struct option _longOptions[] =
{
    {"channel", required_argument, NULL, 'c'},
    {"cpufreq", required_argument, NULL, 'C'},
    {"eof", no_argument, NULL, 'E'},
    {"input-file", required_argument, NULL, 'f'},
    {"help", no_argument, NULL, 'h'},
    {"trigger", required_argument, NULL, 'g' },
    {"itm-sync", no_argument, NULL, 'n'},
    {"server", required_argument, NULL, 's'},
    {"tpiu", required_argument, NULL, 't'},
    {"timestamp", required_argument, NULL, 'T'},
    {"elf", required_argument, NULL, 'e'},
    {"debug", no_argument, NULL, 'd'},
    {"verbose", required_argument, NULL, 'v'},
    {"version", no_argument, NULL, 'V'},
    {NULL, no_argument, NULL, 0}
};
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
static void _feedStream( struct Stream *stream )
{
    struct timeval t;
    unsigned char cbw[TRANSFER_SIZE];

    perfetto_trace = new perfetto::protos::Trace();
    auto *ftrace_packet = perfetto_trace->add_packet();
    ftrace_packet->set_trusted_packet_sequence_id(42);
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

void main_pywrapper(Options py_op, std::vector<uint8_t>* elfbin, std::unordered_map<int32_t, const char*>* irq_names_input){
    // set option struct from python
    options.cps = py_op.cps;
    options.tsType = py_op.tsType;
    options.endTerminate = py_op.endTerminate;
    options.file = py_op.std_file.data();
    options.elf_file = elfbin;
    irq_names = irq_names_input;
    // call main
    printf("Wrapping worked.\n");
    main();
}
// ====================================================================================================
