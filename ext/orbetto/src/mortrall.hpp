#pragma once

#include <vector>
#include <protos/perfetto/trace/trace.pb.h>

#include <stdlib.h>
#include <unistd.h>
#include <stdarg.h>
#include <fcntl.h>
#include <ctype.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <stdio.h>
#include <assert.h>
#include <strings.h>
#include <string.h>
#include <signal.h>
#include <getopt.h>
#include <iostream>
#include <fstream>
#include <deque>
#include <functional>
#include <time.h>

#include "git_version_info.h"
#include "generics.h"
#include "nw.h"
#include "traceDecoder.h"
#include "tpiuDecoder.h"
#include "loadelf.h"
#include "sio.h"
#include "stream.h"



//--------------------------------------------------------------------------------------//
//--------------------------------- BEGIN REGION Defines -------------------------------//
//--------------------------------------------------------------------------------------//

#define INTERVAL_TIME_MS    (1000)      /* Intervaltime between acculumator resets */
#define HANG_TIME_MS        (200)       /* Time without a packet after which we dump the buffer */
#define TICK_TIME_MS        (100)       /* Time intervals for screen updates and keypress check */
#define STACK_BUFFER_SIZE   (4096)      /* Size of the stack buffer */
#define SCRATCH_STRING_LEN  (65535)     /* Max length for a string under construction */

#define MAX_CALL_STACK (30)
#define DEFAULT_PM_BUFLEN_K (32)
#define MAX_BUFFER_SIZE (100)

/* Materials required to be maintained across callbacks for output construction */
struct opConstruct
{
    uint32_t currentFileindex;           /* The filename we're currently in */
    struct symbolFunctionStore *currentFunctionptr;       /* The function we're currently in */
    uint32_t currentLine;                /* The line we're currently in */
    uint32_t workingAddr;                /* The address we're currently in */
};

struct CallStack
{
    symbolMemaddr stack[MAX_CALL_STACK];    /* Stack of calls */
    int stackDepth{-1};                     /* Current stack depth */
    int lastStackDepth{-1};                 /* Last stack depth */
};

struct RunTime
{
    enum TRACEprotocol protocol;        /* Encoding protocol to use */
    struct TRACEDecoder i;

    struct symbol *s;                   /* Currently used elf */
    struct symbol *_s;                  /* Symbols read from elf */
    struct symbol *sb;                  /* Symbols read from bootloader elf*/

    bool bootloader;              /* Set if we are still using bootloader elf */

    struct opConstruct op;              /* Materials required to be maintained across callbacks for output construction */

    bool traceRunning;                  /* Set if we are currently receiving trace */
    uint32_t context;                   /* Context we are currently working under */

    bool committed{true};               /* Set if we have committed to the current jump */
    bool resentStackDel;                /* Possibility to remove an entry from the stack, if address not given */

    bool resentStackSwitch{false};      /* Call stack has been switched in last iteration */
    bool exceptionEntry{false};         /* Set if we are currently in an exception entry */
    int exceptionId{0};                 /* Exception ID */
    bool exceptionActive{false};        /* Set if we are currently in an exception */
    uint32_t returnAddress{0};          /* Return address for exception */

    uint16_t instruction_count{0};      /* Instruction count for precise timing between cycle count packets (Assume all instructions take equally long) */      

    CallStack *callStack;               /* Pointer to current active call stack */
    CallStack exceptionCallStack;       /* Separate call stack for exceptions (all exceptions need to convert to depth 0; nested exceptions not implemented)*/
    CallStack bootloaderCallStack;      /* Call stack for bootloader */
};

struct CallStackBuffer
{
    unsigned int lastCycleCount{0};         /* Last cycle count */
    perfetto::protos::FtraceEvent *proto_buffer[MAX_BUFFER_SIZE]; /* Buffer for protobuf */
    uint16_t instruction_counts[MAX_BUFFER_SIZE];          /* Instruction count */
    uint64_t global_interpolations[MAX_BUFFER_SIZE];          /* Global timestamps */
    int proto_buffer_index{0};                    /* Index for the buffer */
}csb;

//--------------------------------------------------------------------------------------//
//---------------------------------- END REGION Defines --------------------------------//
//--------------------------------------------------------------------------------------//

class Mortrall
{
    public:
        // Perfetto trace to insert the decoded trace elements
        static inline perfetto::protos::Trace *perfetto_trace;
        static inline perfetto::protos::FtraceEventBundle *ftrace;
        static inline uint64_t perf_prev_ns = 0;
        // Data Struct to store information about the current decoding process
        static inline RunTime *r;
        // Parameter to store the PID at which the callstack is added to the perfetto trace
        static constexpr uint32_t PID_CALLSTACK = 400000;
        static constexpr uint32_t PID_BOOTLOADER = 401000;
        static constexpr uint32_t PID_EXCEPTION = 500000;
        static inline uint32_t activeCallStackThread;
        // Store interrupt names to give each a unique perfetto thread
        static inline std::unordered_map<int, const char *> exception_names;
        // initialized
        static inline bool initialized = false;
        // Clocks per second
        static inline uint64_t cps;
        // cycle count and itm timestamp
        static inline uint64_t itm_cycle_count;
        static inline uint64_t itm_timestamp_ns;
        // current running thread id
        static inline uint16_t tid;
        static inline uint16_t pending_tid;
        // Callstack map to store the callstacks of the different threads
        static inline std::map<uint16_t, CallStack> callstacks;
        // pending thread switch
        static inline bool pending_thread_switch;
        // array which lists thread switches from software Pre-Pump
        // The value always indicates the the thread id to switch to (next tid)
        static inline std::deque<uint16_t> thread_switches;
        static inline struct symbolFunctionStore *top_thread_func;
        // Callback function to update timestamp in ITM trace
        static inline std::function<void(uint64_t)> update_itm_timestamp;
        static inline std::function<void()> switch_itm_symbols;
        // Verbosity level
        static inline enum verbLevel verbose;

        static inline bool debug;
        static inline uint64_t cycleCountThreshold;

        // Default Constructor
        constexpr Mortrall()
        {
            ;
        }
        // initialization
        void inline init(perfetto::protos::Trace *perfetto_trace,perfetto::protos::FtraceEventBundle *ftrace,uint64_t cps,enum verbLevel v, struct symbol *s,struct symbol *sb, std::function<void(uint64_t)> update_itm_timestamp_input,std::function<void()> switch_itm_symbols, uint64_t ccth)
        {
            //Mortrall::_startSong();
            Mortrall::perfetto_trace = perfetto_trace;
            Mortrall::ftrace = ftrace;
            Mortrall::cps = cps;
            Mortrall::r = new RunTime();
            Mortrall::r->_s = s;
            Mortrall::r->sb = sb;
            Mortrall::_init();
            Mortrall::initialized = true;
            Mortrall::itm_timestamp_ns = 0;
            Mortrall::itm_cycle_count = 0;
            Mortrall::// Initialize the callstacks
            Mortrall::callstacks[0] = CallStack();
            Mortrall::r->exceptionCallStack = CallStack();
            Mortrall::r->bootloaderCallStack = CallStack();
            if(sb)
            {
                r->bootloader = true;
                r->s = sb;
                Mortrall::r->callStack = &r->bootloaderCallStack;
                Mortrall::activeCallStackThread = PID_BOOTLOADER;
            }else
            {
                r->bootloader = false;
                r->s = s;
                Mortrall::r->callStack = &Mortrall::callstacks[0];
                Mortrall::activeCallStackThread = PID_CALLSTACK;
            }
            Mortrall::pending_thread_switch = false;
            Mortrall::top_thread_func = NULL;
            Mortrall::debug = false;
            Mortrall::update_itm_timestamp = update_itm_timestamp_input;
            Mortrall::switch_itm_symbols = switch_itm_symbols;
            if (v)
            {
                Mortrall::verbose = v;
            }else
            {
                Mortrall::verbose = V_ERROR;
            }
            // Report successful initialization
            _traceReport( V_DEBUG, "Mortrall initialized" EOL);
            // cycle count threshold
            Mortrall::cycleCountThreshold = ccth;
        }
        // Process Trace element
        static void inline dumpElement(char element)
        {
            if(Mortrall::initialized)
            {
                uint8_t byte = (uint8_t)element;
                TRACEDecoderPump( &r->i, &byte, 1, _traceCB, r );
            }
        }
        // Close all remaining threads
        void inline finalize(auto *process_tree)
        {
            if(Mortrall::initialized)
            {
                Mortrall::r->committed = true;
                // flush remaining buffer entries
                Mortrall::_flush_proto_buffer();
            }
            Mortrall::_init_protobuf(process_tree);

            // Print Debug Information
            struct TRACECPUState *cpu = TRACECPUState( &Mortrall::r->i );
            printf("Overflows: %lu - %lu\n",cpu->overflows,cpu->ASyncs);

            delete Mortrall::r;
            // printf times
            printf("Time1: %lu\n",time1);
            printf("Time2: %lu\n",time2);
            printf("Time3: %lu\n",time3);
            printf("Time4: %lu\n",time4);
            printf("Time5: %lu\n",time5);
            printf("Time61: %lu\n",time61);
            printf("Time611: %lu\n",time611);
            printf("Time612: %lu\n",time612);
            printf("Time613: %lu\n",time613);
            printf("Time62: %lu\n",time62);
            printf("Time63: %lu\n",time63);
            printf("Time64: %lu\n",time64);

            //Mortrall::_endSong();
        }

        void inline add_thread_switch(uint16_t tid)
        {
            Mortrall::thread_switches.push_back(tid);
        }

    private:

//--------------------------------------------------------------------------------------//
//-------------------------------- BEGIN REGION Callback -------------------------------//
//--------------------------------------------------------------------------------------//
        static inline bool revertStack = false;
        static inline bool inconsistent = false;
        // Callback function if an "interesting" element has been received

        // timing
        static inline uint64_t time1 = 0;
        static inline uint64_t time2 = 0;
        static inline uint64_t time3 = 0;
        static inline uint64_t time4 = 0;
        static inline uint64_t time5 = 0;
        static inline uint64_t time6 = 0;
        static inline uint64_t time61 = 0;
        static inline uint64_t time611 = 0;
        static inline uint64_t time612 = 0;
        static inline uint64_t time613 = 0;
        static inline uint64_t time62 = 0;
        static inline uint64_t time63 = 0;
        static inline uint64_t time64 = 0;

        static inline struct timespec start;
        static inline struct timespec end;

        static void inline _traceCB( void *d )
        /* Callback function for when valid TRACE decode is detected */
        {
            Mortrall::r = ( RunTime * )d;
            struct TRACECPUState *cpu = TRACECPUState( &Mortrall::r->i );
            uint32_t incAddr = 0;
            uint32_t disposition;
            uint32_t targetAddr = 0; /* Just to avoid unitialised variable warning */
            bool linearRun = false;
            enum instructionClass ic;
            symbolMemaddr newaddr;

            clock_gettime(CLOCK_MONOTONIC, &start);

            /* Check for Cycle Count update to reset instruction count*/
            if (TRACEStateChanged( &Mortrall::r->i, EV_CH_CYCLECOUNT) )
            {
                Mortrall::_generate_protobuf_cycle_counts();
                Mortrall::_flush_proto_buffer();
                Mortrall::r->instruction_count = 0;
                Mortrall::update_itm_timestamp(cpu->cycleCount);
                _traceReport( V_DEBUG, "Cc: %lu\n",cpu->cycleCount );
                if(cpu->cycleCount >= 155610)
                {
                    Mortrall::debug = false;
                }
            }
            //printf("%lu\n",cpu->ASyncs);
            
            clock_gettime(CLOCK_MONOTONIC, &end);
            time1 += (end.tv_sec - start.tv_sec) * 1e9 + (end.tv_nsec - start.tv_nsec);
            clock_gettime(CLOCK_MONOTONIC, &start);

            /* 2: Deal with exception entry */
            /* ============================ */
            if ( TRACEStateChanged( &Mortrall::r->i, EV_CH_EX_ENTRY ) )
            {
                switch ( Mortrall::r->protocol )
                {
                    case TRACE_PROT_ETM4:

                        /* For the ETM4 case we get a new address with the exception indication. This address is the preferred _return_ address, */
                        /* there will be a further address packet, which is the jump destination, along shortly. Note that _this_ address        */
                        /* change indication will be consumed here, and won't hit the test below (which is correct behaviour.                    */
                        if ( !TRACEStateChanged( &Mortrall::r->i, EV_CH_ADDRESS ) )
                        {
                            _traceReport( V_DEBUG, "Exception occured without return address specification" );
                        }
                        else
                        {
                            /* Sometimes an invalid exception address is transmitted. When this happens do not use it as preferred return address. */
                            /* It seems like this can happen when there just has been a branch instruction before the exception and it is not clear if the jump will be executed*/
                            /* An invalid address starts has hex: 0xf...*/
                            if (cpu->addr < 0xf0000000)
                            {
                                _appendToOPBuffer( Mortrall::r, NULL, Mortrall::r->op.currentLine, LT_EVENT, "========== Exception Entry (%d (%s) at 0x%08x return to 0x%08x ) ==========",
                                                cpu->exception, TRACEExceptionName( cpu->exception ), Mortrall::r->op.workingAddr, cpu->addr );
                                Mortrall::r->returnAddress = cpu->addr;
                                revertStack = (cpu->addr != Mortrall::r->callStack->stack[Mortrall::r->callStack->stackDepth]);
                            }
                            else
                            {
                                _appendToOPBuffer( Mortrall::r, NULL, Mortrall::r->op.currentLine, LT_EVENT, "========== Exception Entry (%d (%s) at 0x%08x with invalid return address (0x%08x) ) ==========",
                                                cpu->exception, TRACEExceptionName( cpu->exception ), Mortrall::r->op.workingAddr, cpu->addr );
                                Mortrall::r->returnAddress = Mortrall::r->op.workingAddr;
                            }
                            Mortrall::r->exceptionEntry = true;
                            Mortrall::r->exceptionId = cpu->exception;
                        }

                        break;

                    default:
                        _traceReport( V_DEBUG, "Unrecognised trace protocol in exception handler" );
                        break;
                }
            }

            clock_gettime(CLOCK_MONOTONIC, &end);
            time2 += (end.tv_sec - start.tv_sec) * 1e9 + (end.tv_nsec - start.tv_nsec);
            clock_gettime(CLOCK_MONOTONIC, &start);

            /* 3: Collect flow affecting changes introduced by this event */
            /* ========================================================== */
            if ( TRACEStateChanged( &Mortrall::r->i, EV_CH_ADDRESS ) )
            {
                /* Make debug report if calculated and reported addresses differ. This is most useful for testing when exhaustive  */
                /* address reporting is switched on. It will give 'false positives' for uncalculable instructions (e.g. bx lr) but */
                /* it's a decent safety net to be sure the jump decoder is working correctly.                                      */
                if ( Mortrall::r->protocol != TRACE_PROT_MTB )
                {
                    inconsistent = ( Mortrall::r->op.workingAddr != cpu->addr ) && !r->resentStackSwitch;
                    _traceReport( V_DEBUG, "%sCommanded CPU Address change (Was:0x%08x Commanded:0x%08x)" EOL,
                                ( !inconsistent ||  Mortrall::r->exceptionEntry) ? "" : "***INCONSISTENT*** ", Mortrall::r->op.workingAddr, cpu->addr );
                    _revertStackDel(revertStack,inconsistent);
                    _catchInconsistencies(inconsistent,cpu->addr);
                    Mortrall::r->committed = true;              // This is needed to generate only protobuff entries when the jump was commited
                    Mortrall::r->resentStackDel = false;        // Stack delete has been processed
                    r->resentStackSwitch = false;     // Stack switch has been processed
                    revertStack = false;                        // Reset revertStack
                }
                _handleExceptionEntry();
                /*  After it is clear to what postion the jump happened add the current function to the top of the stack and update in protobuf */
                _addTopToStack(Mortrall::r,cpu->addr);
                _generate_protobuf_entries_single(cpu->addr);
                _stackReport(Mortrall::r);
                /* Check whether a thread switch happened */
                _detect_thread_switch_pattern(cpu);
                /* Whatever the state was, this is an explicit setting of an address, so we need to respect it */
                Mortrall::r->op.workingAddr = cpu->addr;        // Update working address from addr packet
                Mortrall::r->exceptionEntry = false;        // Reset exception entry flag
            }
            
            clock_gettime(CLOCK_MONOTONIC, &end);
            time3 += (end.tv_sec - start.tv_sec) * 1e9 + (end.tv_nsec - start.tv_nsec);
            clock_gettime(CLOCK_MONOTONIC, &start);

            if ( TRACEStateChanged( &Mortrall::r->i, EV_CH_LINEAR ) )
            {
                /* MTB-Specific mechanism: Execute instructions from the marked starting location to the indicated finishing one */
                /* Disposition is all 1's because every instruction is executed.                                                 */
                Mortrall::r->op.workingAddr = cpu->addr;
                targetAddr        = cpu->toAddr;
                linearRun         = true;
                disposition       = 0xffffffff;
                _traceReport( V_DEBUG, "Linear run 0x%08x to 0x%08x" EOL, cpu->addr, cpu->toAddr );
            }

            if ( TRACEStateChanged( &Mortrall::r->i, EV_CH_ENATOMS ) )
            {
                /* Atoms represent instruction steps...some of which will have been executed, some stepped over. The number of steps is the   */
                /* total of the eatoms (executed) and natoms (not executed) and the disposition bitfield shows if each individual instruction */
                /* was executed or not. For ETM3 each 'run' of instructions is a single instruction with the disposition bit telling you if   */
                /* it was executed or not. For ETM4 each 'run' of instructions is from the current address to the next possible change of     */
                /* program flow (and which point the disposition bit tells you if that jump was taken or not).                                */
                incAddr = cpu->eatoms + cpu->natoms;
                disposition = cpu->disposition;
            }
            clock_gettime(CLOCK_MONOTONIC, &end);
            time4 += (end.tv_sec - start.tv_sec) * 1e9 + (end.tv_nsec - start.tv_nsec);

            /* 4: Execute the flow instructions */
            /* ================================ */
            while ( ( incAddr && !linearRun ) || ( ( Mortrall::r->op.workingAddr <= targetAddr ) && linearRun ) )
            {
                clock_gettime(CLOCK_MONOTONIC, &start);
                /* Firstly, lets get the source code line...*/
                struct symbolLineStore *l = symbolLineAt( Mortrall::r->s, Mortrall::r->op.workingAddr );
                struct symbolFunctionStore *func = symbolFunctionAt( Mortrall::r->s, Mortrall::r->op.workingAddr );

                if ( func )
                {
                    /* There is a valid function tag recognised here. If it's a change highlight it in the output. */
                    if ( ( func->filename != Mortrall::r->op.currentFileindex ) || ( func != Mortrall::r->op.currentFunctionptr ) )
                    {
                        _appendToOPBuffer( Mortrall::r, l, Mortrall::r->op.currentLine, LT_FILE, "%s::%s", symbolGetFilename( Mortrall::r->s, func->filename ), func->funcname );
                        Mortrall::r->op.currentFileindex     = func->filename;
                        Mortrall::r->op.currentFunctionptr = func;
                        Mortrall::r->op.currentLine = NO_LINE;
                    }
                }
                else
                {
                    /* We didn't find a valid function, but we might have some information to work with.... */
                    if ( ( NO_FILE != Mortrall::r->op.currentFileindex ) || ( NULL != Mortrall::r->op.currentFunctionptr ) )
                    {
                        _appendToOPBuffer( Mortrall::r, l, Mortrall::r->op.currentLine, LT_FILE, "Unknown function" );
                        Mortrall::r->op.currentFileindex     = NO_FILE;
                        Mortrall::r->op.currentFunctionptr = NULL;
                        Mortrall::r->op.currentLine = NO_LINE;
                    }
                }

                /* If we have changed line then output the new one */
                if ( l && ( ( l->startline != Mortrall::r->op.currentLine ) ) )
                {
                    const char *v = symbolSource( Mortrall::r->s, l->filename, l->startline - 1 );
                    Mortrall::r->op.currentLine = l->startline;
                    //if ( v )
                    //    _appendToOPBuffer( Mortrall::r, l, Mortrall::r->op.currentLine, LT_SOURCE, v );
                }
                clock_gettime(CLOCK_MONOTONIC, &end);
                time5 += (end.tv_sec - start.tv_sec) * 1e9 + (end.tv_nsec - start.tv_nsec);
                clock_gettime(CLOCK_MONOTONIC, &start);

                /* Now output the matching assembly, and location updates */
                char *a = symbolDisassembleLine( Mortrall::r->s, &ic, Mortrall::r->op.workingAddr, &newaddr , &time611, &time612, &time613);
                
                clock_gettime(CLOCK_MONOTONIC, &end);
                time61 += (end.tv_sec - start.tv_sec) * 1e9 + (end.tv_nsec - start.tv_nsec);
                clock_gettime(CLOCK_MONOTONIC, &start);
                if ( a )
                {
                    /* Calculate if this instruction was executed. This is slightly hairy depending on which protocol we're using;         */
                    /*   * ETM3.5: Instructions are executed based on disposition bit (LSB in disposition word)                            */
                    /*   * ETM4  : ETM4 everything up to a branch is executed...decision about that branch is based on disposition bit     */
                    /*   * MTB   : Everything except jumps are executed, jumps are executed only if they are the last instruction in a run */
                    bool insExecuted = (
                                                /* ETM3.5 case - dependent on disposition */
                                                ( ( !linearRun )  && ( Mortrall::r->i.protocol == TRACE_PROT_ETM35 ) && ( disposition & 1 ) ) ||

                                                /* ETM4 case - either not a branch or disposition is 1 */
                                                ( ( !linearRun ) && ( Mortrall::r->i.protocol == TRACE_PROT_ETM4 ) && ( ( !( ic & LE_IC_JUMP ) ) || ( disposition & 1 ) ) ) ||

                                                /* MTB case - a linear run to last address */
                                                ( ( linearRun ) && ( Mortrall::r->i.protocol == TRACE_PROT_MTB ) &&
                                                    ( ( ( Mortrall::r->op.workingAddr != targetAddr ) && ( ! ( ic & LE_IC_JUMP ) ) )  ||
                                                    ( Mortrall::r->op.workingAddr == targetAddr )
                                                    ) ) );
                    _appendToOPBuffer( Mortrall::r, l, Mortrall::r->op.currentLine, insExecuted ? LT_ASSEMBLY : LT_NASSEMBLY, a );
                    /* Count instructions fot later interpolating between cycle count packets*/
                    if(insExecuted)
                    {
                        Mortrall::r->instruction_count++;
                    }
                    /* Move addressing along */
                    if ( ( Mortrall::r->i.protocol != TRACE_PROT_ETM4 ) || ( ic & LE_IC_JUMP ) || (ic & LE_IC_SYNC_BARRIER) )
                    {
                        if ( Mortrall::r->i.protocol == TRACE_PROT_ETM4 )
                        {
                            _traceReport( V_DEBUG, "Consumed, %sexecuted (%d left)", insExecuted ? "" : "not ", incAddr - 1 );
                        }

                        disposition >>= 1;
                        incAddr--;
                    }
                    clock_gettime(CLOCK_MONOTONIC, &end);
                    time62 += (end.tv_sec - start.tv_sec) * 1e9 + (end.tv_nsec - start.tv_nsec);
                    clock_gettime(CLOCK_MONOTONIC, &start);

                    if ( ic & LE_IC_CALL )
                    {
                        if ( insExecuted )
                        {
                            /* Push the instruction after this if it's a subroutine or ISR */
                            _traceReport( V_DEBUG, "Call to %08x", newaddr );
                            _addRetToStack( Mortrall::r, Mortrall::r->op.workingAddr + ( ( ic & LE_IC_4BYTE ) ? 4 : 2 ));
                        }

                        Mortrall::r->op.workingAddr = insExecuted ? newaddr : Mortrall::r->op.workingAddr + ( ( ic & LE_IC_4BYTE ) ? 4 : 2 );
                    }
                    else if ( ic & LE_IC_JUMP )
                    {
                        _traceReport( V_DEBUG, "%sTAKEN JUMP", insExecuted ? "" : "NOT " );

                        if ( insExecuted )
                        {
                            /* Update working address according to if jump was taken */
                            if ( ic & LE_IC_IMMEDIATE )
                            {
                                /* This is a jump, so we need to use the target address */
                                _traceReport( V_DEBUG, "Immediate address %8x", newaddr );
                                Mortrall::r->op.workingAddr = newaddr;
                            }
                            else
                            {
                                if(!_handleExceptionExit(func))
                                {
                                    /* We didn't get the address, so need to park the call stack address if we've got one. Either we won't      */
                                    /* get an address (in which case this one was correct), or we wont (in which case, don't unstack this one). */
                                    if ( Mortrall::r->callStack->stackDepth )
                                    {
                                        Mortrall::r->op.workingAddr= Mortrall::r->callStack->stack[Mortrall::r->callStack->stackDepth - 1];
                                        _traceReport( V_DEBUG, "Return with stacked candidate to %08x", Mortrall::r->op.workingAddr );
                                    }
                                    else
                                    {
                                        _traceReport( V_DEBUG, "Return with no stacked candidate" );
                                    }
                                    Mortrall::r->committed = false;
                                    Mortrall::r->resentStackDel = true;
                                    _removeRetFromStack(Mortrall::r);
                                }
                            }
                        }
                        else
                        {
                            /* The branch wasn't taken, so just move along */
                            Mortrall::r->op.workingAddr += ( ic & LE_IC_4BYTE ) ? 4 : 2;
                        }
                    }
                    else if (ic & LE_IC_SYNC_BARRIER)
                    {
                        /* This is a sync barrier, it has its own Atom packet like a jump instruction */
                        _traceReport( V_DEBUG, "Sync Barrier. \n");
                        Mortrall::r->op.workingAddr += ( ic & LE_IC_4BYTE ) ? 4 : 2;
                    }
                    else
                    {
                        /* Just a regular instruction, so just move along */
                        Mortrall::r->op.workingAddr += ( ic & LE_IC_4BYTE ) ? 4 : 2;
                    }
                    clock_gettime(CLOCK_MONOTONIC, &end);
                    time63 += (end.tv_sec - start.tv_sec) * 1e9 + (end.tv_nsec - start.tv_nsec);

                }
                else
                {
                    clock_gettime(CLOCK_MONOTONIC, &start);
                    /* If it is the first time assembly is not found switch elf file because we exceeded the address range of bootloader elf*/
                    if (r->bootloader)
                    {
                        r->s = r->_s;
                        Mortrall::tid = 0;
                        r->callStack = &callstacks[Mortrall::tid];
                        Mortrall::activeCallStackThread = PID_CALLSTACK + Mortrall::tid;
                        _addTopToStack(Mortrall::r,cpu->addr);
                        _generate_protobuf_entries_single(cpu->addr);
                        r->bootloader = false;
                        Mortrall::switch_itm_symbols();
                        _traceReport( V_DEBUG, "*** BOOTLOADER FINISHED *** \n");
                    }else
                    {
                        _appendToOPBuffer( Mortrall::r, l, Mortrall::r->op.currentLine, LT_ASSEMBLY, "%8x:\tASSEMBLY NOT FOUND" EOL, Mortrall::r->op.workingAddr );
                        Mortrall::r->op.workingAddr += 2;
                        disposition >>= 1;
                        incAddr--;
                    }
                    clock_gettime(CLOCK_MONOTONIC, &end);
                    time64 += (end.tv_sec - start.tv_sec) * 1e9 + (end.tv_nsec - start.tv_nsec);
                }
            }
        }

//--------------------------------------------------------------------------------------//
//--------------------------------- END REGION Callback --------------------------------//
//--------------------------------------------------------------------------------------//

//--------------------------------------------------------------------------------------//
//---------------------------------- BEGIN REGION Init ---------------------------------//
//--------------------------------------------------------------------------------------//

        static void inline _init()
        {
            // Init ETM4 Decoder
            TRACEprotocol trp = TRACE_PROT_ETM4;
            Mortrall::Mortrall::r->protocol = trp;
            TRACEDecoderInit( &Mortrall::Mortrall::r->i, trp, true, _traceReport );
            // init Debug counters
            r->i.cpu.ASyncs = 0;
            r->i.cpu.overflows = 0;
        }
        static void inline _init_protobuf(auto *process_tree)
        {
            {
                auto *process = process_tree->add_processes();
                process->set_pid(PID_CALLSTACK);
                process->add_cmdline("CallStack");
                // loop over callstacks
                for (auto const& [key, val] : Mortrall::callstacks)
                {
                    auto *thread = process_tree->add_threads();
                    thread->set_tid(PID_CALLSTACK + key);
                    thread->set_tgid(PID_CALLSTACK);
                    thread->set_name("Thread");
                }
                // Add additional thread for bootloader
                auto *thread = process_tree->add_threads();
                thread->set_tid(PID_BOOTLOADER);
                thread->set_tgid(PID_CALLSTACK);
                thread->set_name("Bootloader");
            }
            {
                auto *process = process_tree->add_processes();
                process->set_pid(PID_EXCEPTION);
                process->add_cmdline("EXCEPTIONS");
                for (auto&& [tid, name] : exception_names)
                {
                    auto *thread = process_tree->add_threads();
                    thread->set_tid(PID_EXCEPTION + tid);
                    thread->set_tgid(PID_EXCEPTION);
                    thread->set_name(name);
                }
            }
        }

//--------------------------------------------------------------------------------------//
//----------------------------------- END REGION Init ----------------------------------//
//--------------------------------------------------------------------------------------//

//--------------------------------------------------------------------------------------//
//-------------------------------- BEGIN REGION Perfetto -------------------------------//
//--------------------------------------------------------------------------------------//

// ====================================================================================================

        static void inline _appendTOProtoBuffer(auto *event, int offset = 0)
        {
            // as the instruction count interpolation cannot be applied before the next cycle count is received
            // store the event in the buffer
            csb.proto_buffer[csb.proto_buffer_index] = event;
            csb.instruction_counts[csb.proto_buffer_index] = Mortrall::r->instruction_count + offset;
            // The first packet sometimes still has an unknown cycle count however it is actually 0
            if (Mortrall::r->i.cpu.cycleCount == COUNT_UNKNOWN && Mortrall::r->callStack->lastStackDepth == -1){
                csb.global_interpolations[csb.proto_buffer_index] = 0;
            }else
            {
                csb.global_interpolations[csb.proto_buffer_index] = Mortrall::r->i.cpu.cycleCount;
            }
            csb.proto_buffer_index++;
            if (Mortrall::r->callStack->stackDepth < Mortrall::r->callStack->lastStackDepth){
                Mortrall::r->callStack->lastStackDepth--;
            }else if (Mortrall::r->callStack->stackDepth > Mortrall::r->callStack->lastStackDepth){
                Mortrall::r->callStack->lastStackDepth++;
            }
            if (csb.proto_buffer_index == MAX_BUFFER_SIZE)
            {
                Mortrall::_flush_proto_buffer();
            }
        }

        static bool inline _handleInconsistentFunctionSwitch(struct symbolFunctionStore *next_func, uint32_t addr)
        {
            /*
                This function inserts a stop and start element into the protobuf trace to compensate for function switches
                within the same level of the call stack. This should not happen with a perfect instruction trace but seems 
                unavoidable with the current trace data.
            */
           if(Mortrall::r->callStack->stackDepth >= 0)
           {
                // First end current function and append to proto buffer
                //printf("End prev function\n");
                auto *event = ftrace->add_event();      // create Ftrace event
                auto *print = event->mutable_print();
                char buffer[80];
                event->set_pid(Mortrall::activeCallStackThread);        // set the pid of the event
                snprintf(buffer, sizeof(buffer), "E|0");
                print->set_buf(buffer);
                _appendTOProtoBuffer(event);

                // Second begin current function and append to proto buffer
                //printf("Begin next function: %s \n", next_func->funcname);
                event = ftrace->add_event();        // create Ftrace event
                print = event->mutable_print();         // add print
                event->set_pid(Mortrall::activeCallStackThread);        // set the pid of the event
                snprintf(buffer, sizeof(buffer), "B|0|%s", next_func->funcname);
                print->set_buf(buffer);
                _appendTOProtoBuffer(event,1);      // Use an offset of 1 to compensate for the missing instruction count
           }
        }

        static bool inline _inconsistentFunctionSwitch(uint32_t addr)
        {
            if((int)Mortrall::r->callStack->stackDepth == Mortrall::r->callStack->lastStackDepth){
                struct symbolFunctionStore *next_func = symbolFunctionAt( Mortrall::r->s, addr );
                if(top_thread_func && next_func)
                {
                    if(strcmp(next_func->funcname, top_thread_func->funcname))
                    {
                        _traceReport( V_DEBUG, "Inconsistent function switch detected between functions: %s and %s\n", next_func->funcname, top_thread_func->funcname);
                        _handleInconsistentFunctionSwitch(next_func,addr);
                        // Update top thread function after handling the inconsistency
                        Mortrall::top_thread_func = symbolFunctionAt( Mortrall::r->s, Mortrall::r->callStack->stack[Mortrall::r->callStack->stackDepth] );
                    }
                }
                return true;
            }
            return false;
        }

        static void inline _generate_protobuf_entries_single(uint32_t addr)
        {
            // print stack depths
            //printf("Stack Depth: %d\n",Mortrall::r->callStack->stackDepth);
            //printf("Last Stack Depth: %d\n",Mortrall::r->callStack->lastStackDepth);
            if(!_inconsistentFunctionSwitch(addr) && Mortrall::r->committed)
            {
                // Create Ftrace event
                auto *event = ftrace->add_event();
                auto *print = event->mutable_print();
                char buffer[80];
                // Get the function at the current address
                Mortrall::top_thread_func = symbolFunctionAt( Mortrall::r->s, Mortrall::r->callStack->stack[Mortrall::r->callStack->stackDepth] );
                // Check if the call stack reduced or increased
                if(((int)Mortrall::r->callStack->stackDepth > Mortrall::r->callStack->lastStackDepth))
                {
                    // set the pid of the event
                    event->set_pid(Mortrall::activeCallStackThread);
                    if (top_thread_func)
                    {
                        snprintf(buffer, sizeof(buffer), "B|0|%s", Mortrall::top_thread_func->funcname);
                        if(debug)
                        {
                            printf("B|0|%s\n", Mortrall::top_thread_func->funcname);
                        }
                    }else
                    {
                        snprintf(buffer, sizeof(buffer), "B|0|0x%08x", Mortrall::r->op.workingAddr);
                        if(debug)
                        {
                            printf("B|0|0x%08x\n", Mortrall::r->op.workingAddr);
                        }
                    }
                }
                else if(((int)Mortrall::r->callStack->stackDepth < Mortrall::r->callStack->lastStackDepth))
                {
                    // set the pid of the event
                    event->set_pid(Mortrall::activeCallStackThread);
                    snprintf(buffer, sizeof(buffer), "E|0");
                    if(debug)
                    {
                        printf("E|0\n");
                    }
                    //printf("E|0\n");
                }
                print->set_buf(buffer);
                _appendTOProtoBuffer(event);
            }
        }

        static void inline _generate_protobuf_cycle_counts()
        {
            // create Ftrace event
            auto *event = ftrace->add_event();
            uint64_t ns = (uint64_t)(((Mortrall::r->i.cpu.cycleCount * 1'000'000'000)/ Mortrall::cps)-1);
            event->set_timestamp(ns);
            event->set_pid(activeCallStackThread);
            auto *print = event->mutable_print();
            char buffer[40];
            snprintf(buffer, sizeof(buffer), "I|0|CC: %llu",Mortrall::r->i.cpu.cycleCount);
            print->set_buf(buffer);
        }

        static double inline _get_ic_percentage(int i)
        {
            uint16_t ic = csb.instruction_counts[i];
            double ret = 0;
            if (ic != 0)
            {
                    ret = ((double)ic/(double)Mortrall::r->instruction_count) * (Mortrall::r->i.cpu.cycleCount - csb.lastCycleCount);
                    //ret = ((double)ic/(double)Mortrall::r->instruction_count) * (Mortrall::itm_cycle_count - csb.lastCycleCount);
            }
            return ret;
        }

        static void inline _flush_proto_buffer()
        {
            // create Ftrace event
            for (int i = 0; i < csb.proto_buffer_index; i++)
            {
                auto *event = csb.proto_buffer[i];
                uint64_t interpolation = csb.global_interpolations[i] + (uint64_t)_get_ic_percentage(i);
                uint64_t ns = (uint64_t)((interpolation * 1'000'000'000) / Mortrall::cps);
                // check if ns is smaller than previous ns
                // Note: this should not be necessary with a perfect instruction trace however
                if(perf_prev_ns >= ns){
                    ns = perf_prev_ns + 1;
                }
                perf_prev_ns = ns;
                event->set_timestamp(ns);
                // print all stats for debugging
                //printf("Timestamp: %lu\n",ns);
            }
            // clear buffer after flushing
            csb.proto_buffer_index = 0;
            csb.lastCycleCount = Mortrall::r->i.cpu.cycleCount;
        }

//--------------------------------------------------------------------------------------//
//--------------------------------- END REGION Perfetto --------------------------------//
//--------------------------------------------------------------------------------------//

//--------------------------------------------------------------------------------------//
//-------------------------------- BEGIN REGION CallStack ------------------------------//
//--------------------------------------------------------------------------------------//

        static void inline _handleExceptionEntry()
        {
            if (Mortrall::r->exceptionEntry)
            {
                // check if exception Id is in the map
                if(!Mortrall::exception_names.contains(Mortrall::r->exceptionId))
                {
                    Mortrall::exception_names[Mortrall::r->exceptionId] = TRACEExceptionName(Mortrall::r->exceptionId);
                }
                // switch current call stack to exception call stack
                _generate_protobuf_entries_single(Mortrall::r->op.workingAddr);
                _flush_proto_buffer();
                _traceReport( V_DEBUG, "*** THREAD SWITCH *** (to exception: %u)" , Mortrall::r->exceptionId);
                // set the active call stack in runtime
                Mortrall::r->callStack = &r->exceptionCallStack;
                Mortrall::activeCallStackThread = Mortrall::PID_EXCEPTION + Mortrall::r->exceptionId;
                csb.proto_buffer_index = 0;
                r->exceptionActive = true;
            }
        }

        static bool inline _handleExceptionExit(struct symbolFunctionStore *func)
        {
            // if highaddr is reached its the end of exception (highaddr might be offset by a 1/2 byte)
            if(r->exceptionActive && func && strstr(func->funcname,"arm_exception") && (Mortrall::r->op.workingAddr >= (func->highaddr - 0xf))&& (Mortrall::r->op.workingAddr <= (func->highaddr)))
            {
                // Clear the exception call stack
                _removeRetFromStack(Mortrall::r);
                _generate_protobuf_entries_single(Mortrall::r->op.workingAddr);
                _flush_proto_buffer();
                _stackReport(Mortrall::r);
                // Switch to new call stack
                if (Mortrall::pending_thread_switch){       // Check if we switched threads or are just returning from the exception
                    Mortrall::tid = Mortrall::pending_tid;
                }
                _traceReport( V_DEBUG, "*** THREAD SWITCH *** (to tid: %u)" , Mortrall::tid);
                // set the current call stack in runtime
                Mortrall::r->callStack = &Mortrall::callstacks[Mortrall::tid];
                Mortrall::activeCallStackThread = Mortrall::PID_CALLSTACK + Mortrall::tid;
                csb.proto_buffer_index = 0;
                Mortrall::pending_thread_switch = false;
                r->resentStackSwitch = true;
                r->exceptionActive = false;
                _stackReport(Mortrall::r);
                return true;
            }
            return false;
        }


        static void inline _revertStackDel(bool revertStack, bool inconsistent)
        {
            /*
                There are multiple reasons why we would want to revert a stack deletion:
                1. There has been a jump instruction without immediate address this means we have taken a jump but are not sure where we jumped until the next addr packet
                2. There has been a exception right after a jump instruction this means it is not clear if the jump will be executed or the exception interrupted
            */
            if ( Mortrall::r->resentStackDel && (revertStack || (inconsistent && !Mortrall::r->exceptionEntry)))
            {
                _traceReport( V_DEBUG, "Stack delete reverted" );
                Mortrall::r->callStack->stackDepth++;
            }
        }

        static void inline _catchInconsistencies(bool inconsistent, uint32_t addr)
        {
            //if (inconsistent){
                    // check if function in stack
                    if(Mortrall::r->callStack->stackDepth > 0)
                    {
                        // loop over r->callstack
                        struct symbolFunctionStore *new_func = symbolFunctionAt( Mortrall::r->s, addr);
                        for (int i = (Mortrall::r->callStack->stackDepth - 1); i >= 0; i--)
                        {
                            // check if function name address is the same as the new address
                            struct symbolFunctionStore *current_func = symbolFunctionAt( Mortrall::r->s, Mortrall::r->callStack->stack[i]);
                            if(current_func != NULL && new_func != NULL && strcmp(current_func->funcname,new_func->funcname) == 0)
                            {
                                _traceReport( V_DEBUG, "Inconsistency has been caught and reverted" );
                                for (int j = (Mortrall::r->callStack->stackDepth - 1); j >= i; j--)
                                {
                                    _removeRetFromStack(Mortrall::r);
                                    // commit
                                    Mortrall::r->committed = true;
                                    _generate_protobuf_entries_single(addr);
                                }
                                _stackReport(Mortrall::r);
                            }
                        }
                    }
                //}
        }

        static void inline _detect_thread_switch_pattern(struct TRACECPUState *cpu)
        {
            struct symbolFunctionStore *func = symbolFunctionAt( Mortrall::r->s, cpu->addr);
            if(!Mortrall::pending_thread_switch && func && (strcmp(func->funcname,"sched_note_resume") == 0))
            {
                printf("Debug Thread");
                for(const uint16_t& elem : thread_switches)
                {
                    printf(" %u", elem);
                }
                printf("\n");
                Mortrall::pending_tid = Mortrall::thread_switches.front();
                Mortrall::thread_switches.pop_front();
                Mortrall::pending_thread_switch = true;
                _traceReport( V_DEBUG, "Thread switch pattern detected with pending tid: %u" , Mortrall::pending_tid);
            }
        }

        static void inline _addRetToStack( RunTime *r, symbolMemaddr p , int num = 0)
        {
            // for debugging
            if ( Mortrall::r->callStack->stackDepth == MAX_CALL_STACK - 1 )
            {
                /* Stack is full, so make room for a new entry */
                memmove( &Mortrall::r->callStack->stack[0], &Mortrall::r->callStack->stack[1], sizeof( symbolMemaddr ) * ( MAX_CALL_STACK - 1 ) );
            }

            Mortrall::r->callStack->stack[Mortrall::r->callStack->stackDepth] = p;
            _traceReport( V_DEBUG, "Pushed %08x to return stack", Mortrall::r->callStack->stack[Mortrall::r->callStack->stackDepth]);

            if ( Mortrall::r->callStack->stackDepth < MAX_CALL_STACK - 1 )
            {
                Mortrall::r->callStack->stackDepth++;
            }
        }
        static void inline _removeRetFromStack(RunTime *r)
        {
            if ( Mortrall::r->callStack->stackDepth >= 0 )
            {
                Mortrall::r->callStack->stackDepth--;
                _traceReport( V_DEBUG, "Popped %08x from return stack", Mortrall::r->callStack->stack[Mortrall::r->callStack->stackDepth]);
            }
        }
        static inline int count = 0;
        static void inline _addTopToStack(RunTime *r,symbolMemaddr p)
        {
            // If the stack is uninitialized set the stack depth to 0
            if ( Mortrall::r->callStack->stackDepth == -1)
            {
                Mortrall::r->callStack->stackDepth = 0;
            }
            if ( Mortrall::r->callStack->stackDepth < MAX_CALL_STACK - 1 )
            {
                Mortrall::r->callStack->stack[Mortrall::r->callStack->stackDepth] = p;
            }
            if(p==0x080166ca){
                count++;
                //printf("Debug %d\n", count);
                if (count == 45)
                {
                    printf("Debug found.\n");
                }
            }
        }

//--------------------------------------------------------------------------------------//
//--------------------------------- END REGION CallStack -------------------------------//
//--------------------------------------------------------------------------------------//


//--------------------------------------------------------------------------------------//
//-------------------------------- BEGIN REGION Report ---------------------------------//
//--------------------------------------------------------------------------------------//
        static inline bool debug_flag = false;
        static void inline _appendToOPBuffer( struct RunTime *r, void *dat, int32_t lineno, enum LineType lt, const char *fmt, ... )
        /* Add line to output buffer, in a printf stylee */
        {
            char construct[SCRATCH_STRING_LEN];
            va_list va;
            char *p;

            va_start( va , fmt );
            vsnprintf( construct, SCRATCH_STRING_LEN, fmt, va );
            va_end( va );

            /* Make sure we didn't accidentially admit a CR or LF */
            for ( p = construct; ( ( *p ) && ( *p != '\n' ) && ( *p != '\r' ) ); p++ );

            *p = 0;

            if(Mortrall::r->i.cpu.cycleCount >= cycleCountThreshold)
            {
                genericsReport( V_DEBUG, "%s" EOL, construct );
            }
            if(Mortrall::r->i.cpu.cycleCount == cycleCountThreshold && !debug_flag)
            {
                debug_flag = true;
                genericsReport( V_INFO, "Debug Flag set." EOL );
            }
        }
        static void inline _traceReport( enum verbLevel l, const char *fmt, ... )
        /* Debug reporting stream */
        {
            static char op[SCRATCH_STRING_LEN];
            va_list va;
            va_start( va, fmt );
            vsnprintf( op, SCRATCH_STRING_LEN, fmt, va );
            va_end( va );

            if(Mortrall::r->i.cpu.cycleCount >= cycleCountThreshold)
            {
                genericsReport( V_DEBUG, "%s" EOL, op );
            }
        }
        static void inline _stackReport(RunTime *r)
        {
            if ( Mortrall::verbose != V_DEBUG )
            {
                return;
            }
            char CallStack[STACK_BUFFER_SIZE] = "";
            if ( Mortrall::r->callStack->stackDepth == 0 )
            {
                Mortrall::strfcat(CallStack, "Stack %d is empty" EOL, Mortrall::tid);
                if(Mortrall::r->callStack->stack[Mortrall::r->callStack->stackDepth])
                {
                    Mortrall::strfcat(CallStack, "Stack %d: %08x" EOL, Mortrall::r->callStack->stackDepth, Mortrall::r->callStack->stack[Mortrall::r->callStack->stackDepth]);
                }
                strcat(CallStack, EOL);
            }
            else
            {
                Mortrall::strfcat(CallStack,  "Stack depth is %d with tid: %d" EOL, Mortrall::r->callStack->stackDepth, Mortrall::tid);
                // TODO: +1 to stack depth because the stack depth is zero based
                for ( int i = 0; i < Mortrall::r->callStack->stackDepth+1; i++ )
                {
                    struct symbolFunctionStore *running_func = symbolFunctionAt( Mortrall::r->s, Mortrall::r->callStack->stack[i] );
                    if(running_func)
                    {
                        Mortrall::strfcat(CallStack,  "Stack %d: %08x %s" EOL, i, Mortrall::r->callStack->stack[i], running_func->funcname);
                    }
                    else
                    {
                        Mortrall::strfcat(CallStack,  "Stack %d: %08x" EOL, i, Mortrall::r->callStack->stack[i]);
                    }
                }
                strcat(CallStack, EOL);
            }
            if(Mortrall::r->i.cpu.cycleCount >= cycleCountThreshold)
            {
                _traceReport( V_DEBUG, CallStack);
            }
        }
        static void inline strfcat(char *str, const char *format, ...)
        {
            char buffer[STACK_BUFFER_SIZE];
            va_list args;
            va_start(args, format);
            vsprintf(buffer, format, args);
            va_end(args);
            strcat(str, buffer);
        }

//--------------------------------------------------------------------------------------//
//---------------------------------- END REGION Report ---------------------------------//
//--------------------------------------------------------------------------------------//

//--------------------------------------------------------------------------------------//
//------------------------------------- BEGIN song -------------------------------------//
//--------------------------------------------------------------------------------------//

        /*  This part is just for fun because I was stuck on with instruction tracing and Niklas was on vacation */
        /*  and sadly no one else at Auterion can help me with that (GPT: why should they no one has ever done that )*/

        static void inline _startSong()
        {
            // Path to your audio file
            const char *songPath = "/Users/lukasvonbriel/Music/Music/Media.localized/Music/Unknown Artist/Unknown Album/glass-of-wine-143532.mp3";

            // Command to play the song using afplay
            char command[512];
            //snprintf(command, sizeof(command), "afplay \"%s\"", songPath);
            snprintf(command, sizeof(command), "osascript -e 'tell application \"Terminal\" to do script \"afplay \\\"%s\\\"\"'", songPath);

            // Play the song
            system(command);
        }

        static void inline _endSong()
        {
            system("pkill afplay");
        }

//--------------------------------------------------------------------------------------//
//------------------------------------- END song -------------------------------------//
//--------------------------------------------------------------------------------------//

};