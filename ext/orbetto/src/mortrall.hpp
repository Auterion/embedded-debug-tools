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
#define STACK_BUFFER_SIZE   (1024)      /* Size of the stack buffer */
#define SCRATCH_STRING_LEN  (65535)     /* Max length for a string under construction */

#define MAX_CALL_STACK (15)
#define DEFAULT_PM_BUFLEN_K (32)
#define MAX_BUFFER_SIZE (100)

/* Enum for Callstack Properties*/
enum CallStackProperties
{
    FUNCTION,
    EXCEPTION_ENTRY,
    EXCEPTION_EXIT
};

/* Materials required to be maintained across callbacks for output construction */
struct opConstruct
{
    uint32_t currentFileindex;           /* The filename we're currently in */
    struct symbolFunctionStore *currentFunctionptr;       /* The function we're currently in */
    uint32_t currentLine;                /* The line we're currently in */
    uint32_t workingAddr;                /* The address we're currently in */
};

struct RunTime
{
    enum TRACEprotocol protocol;        /* Encoding protocol to use */
    struct TRACEDecoder i;

    struct symbol *s;                   /* Symbols read from elf */

    uint8_t *pmBuffer;                  /* The post-mortem buffer */
    int pmBufferLen{DEFAULT_PM_BUFLEN_K * 1024};               /* The post-mortem buffer length */
    int wp;
    int rp;

    struct opConstruct op;          /* Materials required to be maintained across callbacks for output construction */

    bool traceRunning;                  /* Set if we are currently receiving trace */
    uint32_t context;                   /* Context we are currently working under */
    symbolMemaddr callStack[MAX_CALL_STACK]; /* Stack of calls */
    CallStackProperties callStackProperties[MAX_CALL_STACK]; /* Stack of call properties */
    int stackDepth;            
    int exceptionDepth{-1};        
    bool resentStackDel;               /* Possibility to remove an entry from the stack, if address not given */
    bool exceptionEntry{false};
    uint16_t instruction_count{0};
    uint32_t returnAddress{0};
    bool committed{true};
    void (*protobuffCallback)();
    void (*protobuffCycleCount)();
    void (*flushprotobuff)();
};

struct CallStackBuffer
{
    int lastStackDepth{-1};         /* Last stack depth */
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
        // Data Struct to store information about the current decoding process
        static inline RunTime *r;
        // Parameter to store the PID at which the callstack is added to the perfetto trace
        static constexpr uint32_t PID_CALLSTACK = 400000;
        static constexpr uint32_t PID_INTERRUPTS = 500000;
        static inline uint32_t activeCallStackThread = 5000;
        // Store interrupt names to give each a unique perfetto thread
        static inline std::unordered_map<uint32_t, char *> interrupt_names;
        // initialized
        static inline bool initialized = false;
        // Clocks per second
        static inline uint64_t cps;
        // itm timestamp
        static inline uint64_t itm_timestamp_ns;
        // current running thread id
        static inline uint16_t tid;
        // Default Constructor
        constexpr Mortrall()
        {
            ;
        }
        // initialization
        void inline init(perfetto::protos::Trace *perfetto_trace,perfetto::protos::FtraceEventBundle *ftrace,uint64_t cps,struct symbol *s)
        {
            Mortrall::perfetto_trace = perfetto_trace;
            Mortrall::ftrace = ftrace;
            Mortrall::cps = cps;
            Mortrall::r = new RunTime();
            Mortrall::r->protobuffCallback = Mortrall::_generate_protobuf_entries_single;
            Mortrall::r->protobuffCycleCount = Mortrall::_generate_protobuf_cycle_counts;
            Mortrall::r->flushprotobuff = Mortrall::_flush_proto_buffer;
            Mortrall::r->s = s;
            Mortrall::_init();
            Mortrall::initialized = true;
            Mortrall::itm_timestamp_ns = 0;
            _traceReport( V_DEBUG, "Mortrall initialized" EOL);
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
                while(Mortrall::r->stackDepth > 0)
                {
                    Mortrall::r->stackDepth--;
                    Mortrall::_generate_protobuf_entries_single();
                }
            }
            Mortrall::_init_protobuf(process_tree);
            delete Mortrall::r;
        }

        void inline update_itm_timestamp(uint64_t timestamp)
        {
            Mortrall::itm_timestamp_ns = timestamp;
        }

        void inline update_tid(uint16_t tid)
        {
            Mortrall::tid = tid;
        }
    private:

//--------------------------------------------------------------------------------------//
//-------------------------------- BEGIN REGION Callback -------------------------------//
//--------------------------------------------------------------------------------------//
        static inline int last_stack_depth = -1;
        static inline bool revertStack = false;
        // Callback function if an "interesting" element has been received
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

            /* Check for Cycle Count update to reset instruction count*/
            if (TRACEStateChanged( &Mortrall::r->i, EV_CH_CYCLECOUNT) )
            {
                Mortrall::r->protobuffCycleCount();
                Mortrall::r->flushprotobuff();
                Mortrall::r->instruction_count = 0;
                //printf("Cc: %lu\n",cpu->cycleCount);
            }
            

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
                            _appendToOPBuffer( Mortrall::r, NULL, Mortrall::r->op.currentLine, LT_EVENT, "========== Exception Entry (%d (%s) at 0x%08x return to 0x%08x ) ==========",
                                            cpu->exception, TRACEExceptionName( cpu->exception ), Mortrall::r->op.workingAddr, cpu->addr );
                            Mortrall::r->returnAddress = cpu->addr;
                            revertStack = (cpu->addr != Mortrall::r->callStack[Mortrall::r->stackDepth]);
                            Mortrall::r->exceptionEntry = true;
                        }

                        break;

                    default:
                        _traceReport( V_DEBUG, "Unrecognised trace protocol in exception handler" );
                        break;
                }
            }


            /* 3: Collect flow affecting changes introduced by this event */
            /* ========================================================== */
            if ( TRACEStateChanged( &Mortrall::r->i, EV_CH_ADDRESS ) )
            {
                /* Make debug report if calculated and reported addresses differ. This is most useful for testing when exhaustive  */
                /* address reporting is switched on. It will give 'false positives' for uncalculable instructions (e.g. bx lr) but */
                /* it's a decent safety net to be sure the jump decoder is working correctly.                                      */

                if ( Mortrall::r->protocol != TRACE_PROT_MTB )
                {
                    _traceReport( V_DEBUG, "%sCommanded CPU Address change (Was:0x%08x Commanded:0x%08x)" EOL,
                                ( (Mortrall::r->op.workingAddr == cpu->addr) ||  Mortrall::r->exceptionEntry) ? "" : "***INCONSISTENT*** ", Mortrall::r->op.workingAddr, cpu->addr );
                    // Check if because of an exception we need to revert the stack delete because the previous instruction was not executed
                    Mortrall::r->committed = true;
                    if ( Mortrall::r->resentStackDel && revertStack)
                    {
                        _traceReport( V_DEBUG, "Stack delete reverted" );
                        Mortrall::r->stackDepth++;
                    }else
                    {
                        Mortrall::r->protobuffCallback();
                    }
                    Mortrall::r->resentStackDel = false;
                    // after reverting add the return address of before the exception to the stack
                    if( Mortrall::r->exceptionEntry)
                    {
                        _addRetToStack( Mortrall::r, Mortrall::r->returnAddress ,EXCEPTION_ENTRY);
                    }
                    Mortrall::r->exceptionEntry = false;
                    revertStack = false;
                }
                /* Whatever the state was, this is an explicit setting of an address, so we need to respect it */
                Mortrall::r->op.workingAddr = cpu->addr;
            }
            else
            {
                // Return Stack: If we had a stack deletion pending because of a candidate match, the match was good, so commit
                /*
                if ( ( Mortrall::r->stackDelPending == true ) && ( Mortrall::r->stackDepth ) )
                {
                    //Mortrall::r->stackDepth--;
                    _traceReport( V_DEBUG, "Stack delete committed" );
                    //_stackReport(Mortrall::r);
                }
                Mortrall::r->stackDelPending = false;
                */
                //Mortrall::r->resentStackDel = false;
            }

            // update callstack if stack depth changed when a address has been commanded
            if ( Mortrall::last_stack_depth != Mortrall::r->stackDepth)
            {
                Mortrall::last_stack_depth = Mortrall::r->stackDepth;
                _addTopToStack(Mortrall::r,Mortrall::r->op.workingAddr);
                _stackReport(Mortrall::r);
            }
            

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

            /* 4: Execute the flow instructions */
            /* ================================ */
            while ( ( incAddr && !linearRun ) || ( ( Mortrall::r->op.workingAddr <= targetAddr ) && linearRun ) )
            {
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

                /* Now output the matching assembly, and location updates */
                char *a = symbolDisassembleLine( Mortrall::r->s, &ic, Mortrall::r->op.workingAddr, &newaddr );

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
                    if ( ( Mortrall::r->i.protocol != TRACE_PROT_ETM4 ) || ( ic & LE_IC_JUMP ) )
                    {
                        if ( Mortrall::r->i.protocol == TRACE_PROT_ETM4 )
                        {
                            _traceReport( V_DEBUG, "Consumed, %sexecuted (%d left)", insExecuted ? "" : "not ", incAddr - 1 );
                        }

                        disposition >>= 1;
                        incAddr--;
                    }

                    if ( ic & LE_IC_CALL )
                    {
                        if ( insExecuted )
                        {
                            /* Push the instruction after this if it's a subroutine or ISR */
                            _traceReport( V_DEBUG, "Call to %08x", newaddr );
                            _addRetToStack( Mortrall::r, Mortrall::r->op.workingAddr + ( ( ic & LE_IC_4BYTE ) ? 4 : 2 ) ,FUNCTION);
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
                                _traceReport( V_DEBUG, "Immediate address %8x", newaddr );
                                /* We have a good address, so update with it */
                                Mortrall::r->op.workingAddr = newaddr;
                            }
                            else
                            {
                                /* We didn't get the address, so need to park the call stack address if we've got one. Either we won't      */
                                /* get an address (in which case this one was correct), or we wont (in which case, don't unstack this one). */
                                if ( Mortrall::r->stackDepth )
                                {
                                    Mortrall::r->op.workingAddr= Mortrall::r->callStack[Mortrall::r->stackDepth - 1];
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
                        else
                        {
                            /* The branch wasn't taken, so just move along */
                            Mortrall::r->op.workingAddr += ( ic & LE_IC_4BYTE ) ? 4 : 2;
                        }
                    }
                    else
                    {
                        /* Just a regular instruction, so just move along */
                        Mortrall::r->op.workingAddr += ( ic & LE_IC_4BYTE ) ? 4 : 2;
                    }
                    // maybe ad perfetto here on bool function switch
                    
                }
                else
                {
                    _appendToOPBuffer( Mortrall::r, l, Mortrall::r->op.currentLine, LT_ASSEMBLY, "%8x:\tASSEMBLY NOT FOUND" EOL, Mortrall::r->op.workingAddr );
                    Mortrall::r->op.workingAddr += 2;
                    disposition >>= 1;
                    incAddr--;
                }
                // add current function pointer to the stack if stack depth changed
                if ( last_stack_depth != Mortrall::r->stackDepth)
                {
                    last_stack_depth = Mortrall::r->stackDepth;
                    _addTopToStack(Mortrall::r,Mortrall::r->op.workingAddr);
                    _stackReport(Mortrall::r);
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
            Mortrall::Mortrall::r->pmBuffer = ( uint8_t * )calloc( 1, Mortrall::Mortrall::r->pmBufferLen );
            TRACEDecoderInit( &Mortrall::Mortrall::r->i, trp, true, _traceReport );
        }
        static void inline _init_protobuf(auto *process_tree)
        {
            {
                auto *process = process_tree->add_processes();
                process->set_pid(PID_CALLSTACK);
                process->add_cmdline("CallStack");
                // TODO: add more Callstacks 
                auto *thread = process_tree->add_threads();
                thread->set_tid(PID_CALLSTACK);
                thread->set_tgid(PID_CALLSTACK);
            }
            {
                auto *process = process_tree->add_processes();
                process->set_pid(PID_INTERRUPTS);
                process->add_cmdline("INTERRUPTS");
                char buffer[100];
                auto p = Mortrall::interrupt_names.begin();
                for(int i=0; i < Mortrall::interrupt_names.size(); i++)
                {
                    snprintf(buffer, sizeof(buffer), "%s", p->second);
                    auto *thread = process_tree->add_threads();
                    thread->set_tid(PID_INTERRUPTS + Mortrall::interrupt_names.size() - i -1);
                    thread->set_tgid(PID_INTERRUPTS);
                    thread->set_name(buffer);
                    p++;
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
        static void inline _switchThread(struct symbolFunctionStore *running_func)
        {
            if(Mortrall::r->callStackProperties[Mortrall::r->stackDepth] == EXCEPTION_ENTRY)
            {
                // add Interrupt name to the map if not already present
                if(!Mortrall::interrupt_names.contains(Mortrall::r->callStack[Mortrall::r->stackDepth]))
                {
                    if(running_func)
                    {
                        Mortrall::interrupt_names[Mortrall::r->callStack[Mortrall::r->stackDepth]] = running_func->funcname;
                    }else
                    {
                        Mortrall::interrupt_names[Mortrall::r->callStack[Mortrall::r->stackDepth]] = (char *)"unknown";
                    }
                }
                // get index of the interrupt
                int pos = distance(Mortrall::interrupt_names.begin(),Mortrall::interrupt_names.find(Mortrall::r->callStack[Mortrall::r->stackDepth]));
                // invert position to get the thread number
                pos = Mortrall::interrupt_names.size() - pos - 1; 
                // change thread relative to position in the map
                activeCallStackThread = PID_INTERRUPTS + pos;
            }
        }

        static void inline _returnThread()
        {
            if (Mortrall::r->stackDepth > 0 && Mortrall::r->callStackProperties[Mortrall::r->stackDepth] == EXCEPTION_EXIT)
            {
                activeCallStackThread = PID_CALLSTACK;
            }
        }

        static void inline _generate_protobuf_entries_single()
        {
            ;
            // if(((int)Mortrall::r->stackDepth != csb.lastStackDepth) && Mortrall::r->committed)
            // {
            //     // create Ftrace event
            //     auto *event = ftrace->add_event();
            //     auto *print = event->mutable_print();
            //     char buffer[80];
            //     if(((int)Mortrall::r->stackDepth > csb.lastStackDepth))
            //     {
            //         // get the function at the current address
            //         struct symbolFunctionStore *running_func = symbolFunctionAt( Mortrall::r->s, Mortrall::r->callStack[Mortrall::r->stackDepth] );
            //         // check on which thread the event has been received
            //         _switchThread(running_func);
            //         // set the pid of the event
            //         event->set_pid(activeCallStackThread);
            //         if (running_func)
            //         {
            //             snprintf(buffer, sizeof(buffer), "B|0|%s", running_func->funcname);
            //         }else
            //         {
            //             snprintf(buffer, sizeof(buffer), "B|0|0x%08x", Mortrall::r->op.workingAddr);
            //         }
            //     }
            //     else if(((int)Mortrall::r->stackDepth < csb.lastStackDepth))
            //     {
            //         // set the pid of the event
            //         event->set_pid(activeCallStackThread);
            //         // check return to previous thread
            //         _returnThread();
            //         snprintf(buffer, sizeof(buffer), "E|0");
            //     }
            //     print->set_buf(buffer);
            //     // as the instruction count interpolation cannot be applied before the next cycle count is received
            //     // store the event in the buffer
            //     csb.proto_buffer[csb.proto_buffer_index] = event;
            //     csb.instruction_counts[csb.proto_buffer_index] = Mortrall::r->instruction_count;
            //     csb.global_interpolations[csb.proto_buffer_index] = Mortrall::r->i.cpu.cycleCount;
            //     csb.proto_buffer_index++;
            //     csb.lastStackDepth = Mortrall::r->stackDepth;
            //     if (csb.proto_buffer_index == MAX_BUFFER_SIZE)
            //     {
            //         Mortrall::r->flushprotobuff();
            //     }
            // }
        }

        static void inline _generate_protobuf_cycle_counts()
        {
            // create Ftrace event
            auto *event = ftrace->add_event();
            uint64_t ns = (uint64_t)(((Mortrall::r->i.cpu.cycleCount * 1'000'000'000)/ Mortrall::cps)-1);
            // event->set_timestamp(ns);
            event->set_timestamp(Mortrall::itm_timestamp_ns);
            event->set_pid(PID_CALLSTACK);
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
            }
            return ret;
        }

        static void inline _flush_proto_buffer()
        {
            ;
            // // create Ftrace event
            // for (int i = 0; i < csb.proto_buffer_index; i++)
            // {
            //     auto *event = csb.proto_buffer[i];
            //     uint64_t interpolation = csb.global_interpolations[i] + (uint64_t)_get_ic_percentage(i);
            //     uint64_t ns = (uint64_t)((interpolation * 1'000'000'000) / Mortrall::cps);
            //     event->set_timestamp(ns);  
            // }
            // // clear buffer after flushing
            // csb.proto_buffer_index = 0;
            // csb.lastCycleCount = Mortrall::r->i.cpu.cycleCount;
        }

//--------------------------------------------------------------------------------------//
//--------------------------------- END REGION Perfetto --------------------------------//
//--------------------------------------------------------------------------------------//

//--------------------------------------------------------------------------------------//
//-------------------------------- BEGIN REGION CallStack ------------------------------//
//--------------------------------------------------------------------------------------//

        static void inline _addRetToStack( RunTime *r, symbolMemaddr p ,CallStackProperties csp)
        {
            if ( Mortrall::r->stackDepth == MAX_CALL_STACK - 1 )
            {
                /* Stack is full, so make room for a new entry */
                memmove( &Mortrall::r->callStack[0], &Mortrall::r->callStack[1], sizeof( symbolMemaddr ) * ( MAX_CALL_STACK - 1 ) );
                memmove( &Mortrall::r->callStackProperties[0], &Mortrall::r->callStackProperties[1], sizeof( CallStackProperties ) * ( MAX_CALL_STACK - 1 ) );
            }
            // check if where are exiting an exception
            if (csp == EXCEPTION_ENTRY)
            {
                Mortrall::r->exceptionDepth = Mortrall::r->stackDepth;
            }

            Mortrall::r->callStack[Mortrall::r->stackDepth] = p;
            _traceReport( V_DEBUG, "Pushed %08x to return stack", Mortrall::r->callStack[Mortrall::r->stackDepth]);

            if ( Mortrall::r->stackDepth < MAX_CALL_STACK - 1 )
            {
                /* We aren't at max depth, so go ahead and remove this entry */
                Mortrall::r->stackDepth++;
            }
            Mortrall::r->callStackProperties[Mortrall::r->stackDepth] = csp;
        }
        static void inline _removeRetFromStack(RunTime *r)
        {
            if ( Mortrall::r->stackDepth > 0 )
            {
                Mortrall::r->stackDepth--;
                if(Mortrall::r->exceptionDepth >= Mortrall::r->stackDepth)
                {
                    Mortrall::r->exceptionDepth = 0;
                    Mortrall::r->callStackProperties[Mortrall::r->stackDepth] = EXCEPTION_EXIT;
                }
                _traceReport( V_DEBUG, "Popped %08x from return stack", Mortrall::r->callStack[Mortrall::r->stackDepth]);
            }
        }
        static void inline _addTopToStack(RunTime *r,symbolMemaddr p)
        {
            if ( Mortrall::r->stackDepth < MAX_CALL_STACK - 1 )
            {
                Mortrall::r->callStack[Mortrall::r->stackDepth] = p;
            }
            Mortrall::r->protobuffCallback();
        }

//--------------------------------------------------------------------------------------//
//--------------------------------- END REGION CallStack -------------------------------//
//--------------------------------------------------------------------------------------//


//--------------------------------------------------------------------------------------//
//-------------------------------- BEGIN REGION Report ---------------------------------//
//--------------------------------------------------------------------------------------//

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

            genericsReport( V_DEBUG, "%s" EOL, construct );

        }
        static void inline _traceReport( enum verbLevel l, const char *fmt, ... )
        /* Debug reporting stream */
        {
            static char op[SCRATCH_STRING_LEN];
            va_list va;
            va_start( va, fmt );
            vsnprintf( op, SCRATCH_STRING_LEN, fmt, va );
            va_end( va );

            genericsReport( V_DEBUG, "%s" EOL, op );
        }
        static void inline _stackReport(RunTime *r)
        {
            char CallStack[STACK_BUFFER_SIZE];
            if ( Mortrall::r->stackDepth == 0 )
            {
                strcat(CallStack, "Stack is empty" EOL);
                if(Mortrall::r->callStack[Mortrall::r->stackDepth])
                {
                    Mortrall::strfcat(CallStack, "Stack %d: %08x" EOL, Mortrall::r->stackDepth, Mortrall::r->callStack[Mortrall::r->stackDepth]);
                }
                strcat(CallStack, EOL);
            }
            else
            {
                Mortrall::strfcat(CallStack,  "Stack depth is %d" EOL, Mortrall::r->stackDepth);
                for ( int i = 0; i < Mortrall::r->stackDepth+1; i++ )
                {
                    struct symbolFunctionStore *running_func = symbolFunctionAt( Mortrall::r->s, Mortrall::r->callStack[i] );
                    if(running_func)
                    {
                        Mortrall::strfcat(CallStack,  "Stack %d: %08x %s" EOL, i, Mortrall::r->callStack[i], running_func->funcname);
                    }
                    else
                    {
                        Mortrall::strfcat(CallStack,  "Stack %d: %08x" EOL, i, Mortrall::r->callStack[i]);
                    }
                }
                strcat(CallStack, EOL);
            }
            _traceReport( V_DEBUG, CallStack);
        }
        static void inline strfcat(char *str, const char *format, ...)
        {
            char buffer[60];
            va_list args;
            va_start(args, format);
            vsprintf(buffer, format, args);
            va_end(args);
            strcat(str, buffer);
        }

//--------------------------------------------------------------------------------------//
//---------------------------------- END REGION Report ---------------------------------//
//--------------------------------------------------------------------------------------//

};