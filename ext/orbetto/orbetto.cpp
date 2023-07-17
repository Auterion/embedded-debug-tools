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
struct
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
    bool endTerminate;                       /* Terminate when file/socket "ends" */

} options =
{
    .forceITMSync = true,
    .tpiuChannel = 1,
    .port = NWCLIENT_SERVER_PORT,
    .server = (char *)"localhost",
    .tsTrigger = DEFAULT_TS_TRIGGER
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

static perfetto::protos::FtraceEventBundle *ftrace;

static std::unordered_map<int32_t, const char*> irq_names =
{
  {16+-14, "NonMaskableInt"},     // 2 Non Maskable Interrupt
  {16+-12, "MemoryManagement"},   // 4 Cortex-M7 Memory Management Interrupt
  {16+-11, "BusFault"},           // 5 Cortex-M7 Bus Fault Interrupt
  {16+-10, "UsageFault"},         // 6 Cortex-M7 Usage Fault Interrupt
  {16+ -5, "SVCall"},             // 11 Cortex-M7 SV Call Interrupt
  {16+ -4, "DebugMonitor"},       // 12 Cortex-M7 Debug Monitor Interrupt
  {16+ -2, "PendSV"},             // 14 Cortex-M7 Pend SV Interrupt
  {16+ -1, "SysTick"},            // 15 Cortex-M7 System Tick Interrupt

  {16+  0, "WWDG"},               // Window WatchDog Interrupt
  {16+  1, "PVD"},                // PVD through EXTI Line detection Interrupt
  {16+  2, "TAMP_STAMP"},         // Tamper and TimeStamp interrupts through the EXTI line
  {16+  3, "RTC_WKUP"},           // RTC Wakeup interrupt through the EXTI line
  {16+  4, "FLASH"},              // FLASH global Interrupt
  {16+  5, "RCC"},                // RCC global Interrupt
  {16+  6, "EXTI0"},              // EXTI Line0 Interrupt
  {16+  7, "EXTI1"},              // EXTI Line1 Interrupt
  {16+  8, "EXTI2"},              // EXTI Line2 Interrupt
  {16+  9, "EXTI3"},              // EXTI Line3 Interrupt
  {16+ 10, "EXTI4"},              // EXTI Line4 Interrupt
  {16+ 11, "DMA1_Stream0"},       // DMA1 Stream 0 global Interrupt
  {16+ 12, "DMA1_Stream1"},       // DMA1 Stream 1 global Interrupt
  {16+ 13, "DMA1_Stream2"},       // DMA1 Stream 2 global Interrupt
  {16+ 14, "DMA1_Stream3"},       // DMA1 Stream 3 global Interrupt
  {16+ 15, "DMA1_Stream4"},       // DMA1 Stream 4 global Interrupt
  {16+ 16, "DMA1_Stream5"},       // DMA1 Stream 5 global Interrupt
  {16+ 17, "DMA1_Stream6"},       // DMA1 Stream 6 global Interrupt
  {16+ 18, "ADC"},                // ADC1, ADC2 and ADC3 global Interrupts
  {16+ 19, "CAN1_TX"},            // CAN1 TX Interrupt
  {16+ 20, "CAN1_RX0"},           // CAN1 RX0 Interrupt
  {16+ 21, "CAN1_RX1"},           // CAN1 RX1 Interrupt
  {16+ 22, "CAN1_SCE"},           // CAN1 SCE Interrupt
  {16+ 23, "EXTI9_5"},            // External Line[9:5] Interrupts
  {16+ 24, "TIM1_BRK_TIM9"},      // TIM1 Break interrupt and TIM9 global interrupt
  {16+ 25, "TIM1_UP_TIM10"},      // TIM1 Update Interrupt and TIM10 global interrupt
  {16+ 26, "TIM1_TRG_COM_TIM11"}, // TIM1 Trigger and Commutation Interrupt and TIM11 global interrupt
  {16+ 27, "TIM1_CC"},            // TIM1 Capture Compare Interrupt
  {16+ 28, "TIM2"},               // TIM2 global Interrupt
  {16+ 29, "TIM3"},               // TIM3 global Interrupt
  {16+ 30, "TIM4"},               // TIM4 global Interrupt
  {16+ 31, "I2C1_EV"},            // I2C1 Event Interrupt
  {16+ 32, "I2C1_ER"},            // I2C1 Error Interrupt
  {16+ 33, "I2C2_EV"},            // I2C2 Event Interrupt
  {16+ 34, "I2C2_ER"},            // I2C2 Error Interrupt
  {16+ 35, "SPI1"},               // SPI1 global Interrupt
  {16+ 36, "SPI2"},               // SPI2 global Interrupt
  {16+ 37, "USART1"},             // USART1 global Interrupt
  {16+ 38, "USART2"},             // USART2 global Interrupt
  {16+ 39, "USART3"},             // USART3 global Interrupt
  {16+ 40, "EXTI15_10"},          // External Line[15:10] Interrupts
  {16+ 41, "RTC_Alarm"},          // RTC Alarm (A and B) through EXTI Line Interrupt
  {16+ 42, "OTG_FS_WKUP"},        // USB OTG FS Wakeup through EXTI line interrupt
  {16+ 43, "TIM8_BRK_TIM12"},     // TIM8 Break Interrupt and TIM12 global interrupt
  {16+ 44, "TIM8_UP_TIM13"},      // TIM8 Update Interrupt and TIM13 global interrupt
  {16+ 45, "TIM8_TRG_COM_TIM14"}, // TIM8 Trigger and Commutation Interrupt and TIM14 global interrupt
  {16+ 46, "TIM8_CC"},            // TIM8 Capture Compare Interrupt
  {16+ 47, "DMA1_Stream7"},       // DMA1 Stream7 Interrupt
  {16+ 48, "FMC"},                // FMC global Interrupt
  {16+ 49, "SDMMC1"},             // SDMMC1 global Interrupt
  {16+ 50, "TIM5"},               // TIM5 global Interrupt
  {16+ 51, "SPI3"},               // SPI3 global Interrupt
  {16+ 52, "UART4"},              // UART4 global Interrupt
  {16+ 53, "UART5"},              // UART5 global Interrupt
  {16+ 54, "TIM6_DAC"},           // TIM6 global and DAC1&2 underrun error  interrupts
  {16+ 55, "TIM7"},               // TIM7 global interrupt
  {16+ 56, "DMA2_Stream0"},       // DMA2 Stream 0 global Interrupt
  {16+ 57, "DMA2_Stream1"},       // DMA2 Stream 1 global Interrupt
  {16+ 58, "DMA2_Stream2"},       // DMA2 Stream 2 global Interrupt
  {16+ 59, "DMA2_Stream3"},       // DMA2 Stream 3 global Interrupt
  {16+ 60, "DMA2_Stream4"},       // DMA2 Stream 4 global Interrupt
  {16+ 61, "ETH"},                // Ethernet global Interrupt
  {16+ 62, "ETH_WKUP"},           // Ethernet Wakeup through EXTI line Interrupt
  {16+ 63, "CAN2_TX"},            // CAN2 TX Interrupt
  {16+ 64, "CAN2_RX0"},           // CAN2 RX0 Interrupt
  {16+ 65, "CAN2_RX1"},           // CAN2 RX1 Interrupt
  {16+ 66, "CAN2_SCE"},           // CAN2 SCE Interrupt
  {16+ 67, "OTG_FS"},             // USB OTG FS global Interrupt
  {16+ 68, "DMA2_Stream5"},       // DMA2 Stream 5 global interrupt
  {16+ 69, "DMA2_Stream6"},       // DMA2 Stream 6 global interrupt
  {16+ 70, "DMA2_Stream7"},       // DMA2 Stream 7 global interrupt
  {16+ 71, "USART6"},             // USART6 global interrupt
  {16+ 72, "I2C3_EV"},            // I2C3 event interrupt
  {16+ 73, "I2C3_ER"},            // I2C3 error interrupt
  {16+ 74, "OTG_HS_EP1_OUT"},     // USB OTG HS End Point 1 Out global interrupt
  {16+ 75, "OTG_HS_EP1_IN"},      // USB OTG HS End Point 1 In global interrupt
  {16+ 76, "OTG_HS_WKUP"},        // USB OTG HS Wakeup through EXTI interrupt
  {16+ 77, "OTG_HS"},             // USB OTG HS global interrupt
  {16+ 78, "DCMI"},               // DCMI global interrupt
  {16+ 80, "RNG"},                // RNG global interrupt
  {16+ 81, "FPU"},                // FPU global interrupt
  {16+ 82, "UART7"},              // UART7 global interrupt
  {16+ 83, "UART8"},              // UART8 global interrupt
  {16+ 84, "SPI4"},               // SPI4 global Interrupt
  {16+ 85, "SPI5"},               // SPI5 global Interrupt
  {16+ 86, "SPI6"},               // SPI6 global Interrupt
  {16+ 87, "SAI1"},               // SAI1 global Interrupt
  {16+ 90, "DMA2D"},              // DMA2D global Interrupt
  {16+ 91, "SAI2"},               // SAI2 global Interrupt
  {16+ 92, "QUADSPI"},            // Quad SPI global interrupt
  {16+ 93, "LPTIM1"},             // LP TIM1 interrupt
  {16+ 94, "CEC"},                // HDMI-CEC global Interrupt
  {16+ 95, "I2C4_EV"},            // I2C4 Event Interrupt
  {16+ 96, "I2C4_ER"},            // I2C4 Error Interrupt
  {16+ 97, "SPDIF_RX"},           // SPDIF-RX global Interrupt
  {16+ 99, "DFSDM1_FLT0"},        // DFSDM1 Filter 0 global Interrupt
  {16+100, "DFSDM1_FLT1"},        // DFSDM1 Filter 1 global Interrupt
  {16+101, "DFSDM1_FLT2"},        // DFSDM1 Filter 2 global Interrupt
  {16+102, "DFSDM1_FLT3"},        // DFSDM1 Filter 3 global Interrupt
  {16+103, "SDMMC2"},             // SDMMC2 global Interrupt
  {16+104, "CAN3_TX"},            // CAN3 TX Interrupt
  {16+105, "CAN3_RX0"},           // CAN3 RX0 Interrupt
  {16+106, "CAN3_RX1"},           // CAN3 RX1 Interrupt
  {16+107, "CAN3_SCE"},           // CAN3 SCE Interrupt
  {16+109, "MDIOS"},              // MDIO Slave global Interrupt
};

static constexpr uint32_t PID_TSK{10'000};
static constexpr uint32_t PID_IRQ{100'000};
static std::unordered_map<uint16_t, std::string> active_threads;
static std::unordered_map<uint32_t, std::pair<uint32_t, std::string>> process_map;
static void _switchTo(uint32_t tid, bool begin, int priority = -1, int prev_state = -1)
{
    static uint32_t prev_tid{0}, pre_irq_tid{0};
    bool is_irq_return{false};
    uint32_t pid = tid >= PID_IRQ ? PID_IRQ : PID_TSK;

    if (pid == PID_IRQ)
    {
        // We must return interrupts to previous thread manually
        if (not begin) {
            tid = pre_irq_tid;
            pid = PID_TSK;
            is_irq_return = true;
        }
        pre_irq_tid = prev_tid;
    }

    if (not process_map.contains(tid))
    {
        std::string name = "unknown";
        if (pid == PID_IRQ and irq_names.contains(tid - PID_IRQ))
            name = irq_names[tid - PID_IRQ];
        else if (active_threads.contains(tid))
            name = active_threads[tid];
        else if (tid == 0)
            name = "idle";
        process_map.insert({tid, {pid, name}});
    }

    if (begin or is_irq_return)
    {
        auto *event = ftrace->add_event();
        event->set_timestamp((_r.timeStamp * 1e9) / options.cps);
        event->set_pid(pid);

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
        if (priority > 0) sched_switch->set_next_prio(priority);

        prev_tid = tid;
    }

}

// ====================================================================================================
static uint32_t last_tid{0};
static void _handleSW( struct swMsg *m, struct ITMDecoder *i )
{
    assert( m->msgtype == MSG_SOFTWARE );

    static std::string thread_name;
    const uint32_t tid = ((m->value & 0xfffful) == 0) ? 0 : (PID_TSK + m->value & 0xfffful);
    const uint32_t PID_TL = PID_TSK + 3000;
    if (m->srcAddr == 0) // start
    {
        if (m->len == 4) {
            char name[5]{0,0,0,0,0};
            memcpy(name, &m->value, 4);
            thread_name += name;
        }
        if (m->len == 2) {
            if (tid > PID_TL) {
                thread_name.clear();
                return;
            }
            if (not thread_name.empty() and thread_name.find("param") == -1)
            {
                if (active_threads.contains(tid))
                {
                    if (active_threads[tid] != thread_name and tid != 0)
                    {
                        auto *event = ftrace->add_event();
                        event->set_timestamp((_r.timeStamp * 1e9) / options.cps);
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
                        event->set_timestamp((_r.timeStamp * 1e9) / options.cps);
                        event->set_pid(last_tid);
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
        if (tid > PID_TL) return;
        active_threads.erase(tid);
    }
    else if (m->srcAddr == 2) // suspend
    {
        if (tid > PID_TL) return;
        if (not active_threads.contains(tid)) return;
        _switchTo(0, true);
    }
    else if (m->srcAddr == 3) // resume
    {
        if (tid > PID_TL) return;
        if (not active_threads.contains(tid)) return;
        const uint8_t priority = m->value >> 16;
        const uint8_t prev_state = m->value >> 24;
        _switchTo(tid, true, priority, prev_state);
        last_tid = tid;
    }
    else if (m->srcAddr == 4) // ready
    {
        if (tid > PID_TL) return;
        auto *event = ftrace->add_event();
        event->set_timestamp((_r.timeStamp * 1e9) / options.cps);
        event->set_pid(last_tid);
        auto *sched_waking = event->mutable_sched_waking();
        sched_waking->set_pid(tid);
        sched_waking->set_success(1);
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
    if (irq > 125) return;
    // [enter (1) -----> exit (2), resume (3)]
    const bool begin = m->eventType == EXEVENT_ENTER;

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
        event->set_timestamp((_r.timeStamp * 1e9) / options.cps);
        event->set_pid(0);
        auto *exit = event->mutable_irq_handler_exit();
        exit->set_irq(last_irq);
        exit->set_ret(1);
    }
    last_irq = irq;
    last_begin = begin;

    auto *event = ftrace->add_event();
    event->set_timestamp((_r.timeStamp * 1e9) / options.cps);
    event->set_pid(0);

    if (begin)
    {
        auto *entry = event->mutable_irq_handler_entry();
        entry->set_irq(irq);
        entry->set_name("unknown");
        if (irq_names.contains(irq))
            entry->set_name(irq_names[irq]);
    }
    else
    {
        auto *exit = event->mutable_irq_handler_exit();
        exit->set_irq(irq);
        exit->set_ret(1);
    }
}

static void _handlePc( struct pcSampleMsg *m, struct ITMDecoder *i )
{
    assert( m->msgtype == MSG_PC_SAMPLE );
}

// ====================================================================================================
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
    {"verbose", required_argument, NULL, 'v'},
    {"version", no_argument, NULL, 'V'},
    {NULL, no_argument, NULL, 0}
};
// ====================================================================================================
bool _processOptions( int argc, char *argv[] )

{
    int c, optionIndex = 0;
    unsigned int chan;
    char *chanIndex;
#define DELIMITER ','

    while ( ( c = getopt_long ( argc, argv, "c:C:Ef:g:hVns:t:T:v:", _longOptions, &optionIndex ) ) != -1 )
        switch ( c )
        {
            // ------------------------------------
            case 'C':
                options.cps = atoi( optarg ) * 1000;
                break;

            // ------------------------------------
            case 'h':
                _printHelp( argv[0] );
                return false;

            // ------------------------------------
            case 'V':
                _printVersion();
                return false;

            // ------------------------------------
            case 'E':
                options.endTerminate = true;
                break;

            // ------------------------------------
            case 'f':
                options.file = optarg;
                break;

            // ------------------------------------
            case 'g':
                printf( "%s" EOL, optarg );
                options.tsTrigger = genericsUnescape( optarg )[0];
                break;

            // ------------------------------------
            case 'n':
                options.forceITMSync = false;
                break;

            // ------------------------------------
            case 's':
            {
                options.server = optarg;
                // See if we have an optional port number too
                char *a = optarg;

                while ( ( *a ) && ( *a != ':' ) )
                {
                    a++;
                }

                if ( *a == ':' )
                {
                    *a = 0;
                    options.port = atoi( ++a );
                }

                if ( !options.port )
                {
                    options.port = NWCLIENT_SERVER_PORT;
                }

                break;
            }

            // ------------------------------------
            case 't':
                options.useTPIU = true;
                options.tpiuChannel = atoi( optarg );
                break;

            // ------------------------------------
            case 'T':
                switch ( *optarg )
                {
                    case 'a':
                        options.tsType = TSAbsolute;
                        break;

                    case 'r':
                        options.tsType = TSRelative;
                        break;

                    case 'd':
                        options.tsType = TSDelta;
                        break;

                    case 's':
                        options.tsType = TSStamp;
                        break;

                    case 't':
                        options.tsType = TSStampDelta;
                        break;

                    default:
                        genericsReport( V_ERROR, "Unrecognised Timestamp type" EOL );
                        return false;
                }

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
            /* Individual channel setup */
            case 'c':
                chanIndex = optarg;

                chan = atoi( optarg );

                if ( chan >= NUM_CHANNELS )
                {
                    genericsReport( V_ERROR, "Channel index out of range" EOL );
                    return false;
                }

                /* Scan for format */
                while ( ( *chanIndex ) && ( *chanIndex != DELIMITER ) )
                {
                    chanIndex++;
                }

                /* Step over delimiter */
                chanIndex++;

                /* Scan past any whitespace */
                while ( ( *chanIndex ) && ( isspace( *chanIndex ) ) )
                {
                    chanIndex++;
                }

                if ( !*chanIndex )
                {
                    genericsReport( V_ERROR, "No output format for channel %d (avoid spaces before the output spec)" EOL, chan );
                    return false;
                }

                //*chanIndex++ = 0;
                options.presFormat[chan] = strdup( genericsUnescape( chanIndex ) );
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
    genericsReport( V_INFO, "Server     : %s:%d" EOL, options.server, options.port );
    genericsReport( V_INFO, "ForceSync  : %s" EOL, options.forceITMSync ? "true" : "false" );
    genericsReport( V_INFO, "Timestamp  : %s" EOL, tsTypeString[options.tsType] );

    if ( options.cps )
    {
        genericsReport( V_INFO, "S-CPU Speed: %d KHz" EOL, options.cps );
    }

    if ( options.tsType != TSNone )
    {
        char unesc[2] = {options.tsTrigger, 0};
        genericsReport( V_INFO, "TriggerChr : '%s'" EOL, genericsEscape( unesc ) );
    }

    if ( options.file )
    {

        genericsReport( V_INFO, "Input File : %s", options.file );

        if ( options.endTerminate )
        {
            genericsReport( V_INFO, " (Terminate on exhaustion)" EOL );
        }
        else
        {
            genericsReport( V_INFO, " (Ongoing read)" EOL );
        }
    }

    if ( options.useTPIU )
    {
        genericsReport( V_INFO, "Using TPIU : true (ITM on channel %d)" EOL, options.tpiuChannel );
    }
    else
    {
        genericsReport( V_INFO, "Using TPIU : false" EOL );
    }

    genericsReport( V_INFO, "Channels   :" EOL );

    for ( int g = 0; g < NUM_CHANNELS; g++ )
    {
        if ( options.presFormat[g] )
        {
            genericsReport( V_INFO, "             %02d [%s]" EOL, g, genericsEscape( options.presFormat[g] ) );
        }
    }

    return true;
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
static void _feedStream( struct Stream *stream )
{
    struct timeval t;
    unsigned char cbw[TRANSFER_SIZE];

    auto *perfetto_trace = new perfetto::protos::Trace();
    {
        auto *packet = perfetto_trace->add_packet();
        packet->set_trusted_packet_sequence_id(42);
        ftrace = packet->mutable_ftrace_events();
        ftrace->set_cpu(0);
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
        auto *packet = perfetto_trace->add_packet();
        packet->set_trusted_packet_sequence_id(42);
        auto *process_tree = packet->mutable_process_tree();
        {
            auto *process = process_tree->add_processes();
            process->set_pid(0);
            process->add_cmdline("NuttX");
        }
        // {
        //     auto *process = process_tree->add_processes();
        //     process->set_pid(PID_IRQ);
        //     process->add_cmdline("Interrupts");
        // }
        for (const auto& [tid, value] : process_map)
        {
            if (tid == 0) continue;
            const auto& [pid, name] = value;
            auto *thread = process_tree->add_threads();
            thread->set_tid(tid);
            thread->set_tgid(pid);
            if (pid == PID_IRQ) thread->set_name(name);
        }
    }

    // std::ofstream perfetto_debug("orbetto.debug", std::ios::out);
    // perfetto_debug << perfetto_trace->DebugString();
    // perfetto_debug.close();

    std::ofstream perfetto_file("orbetto.perf", std::ios::out | std::ios::binary);
    perfetto_trace->SerializeToOstream(&perfetto_file);
    perfetto_file.close();
    delete perfetto_trace;
}

// ====================================================================================================
int main( int argc, char *argv[] )

{
    bool alreadyReported = false;

    if ( !_processOptions( argc, argv ) )
    {
        exit( -1 );
    }

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
// ====================================================================================================
