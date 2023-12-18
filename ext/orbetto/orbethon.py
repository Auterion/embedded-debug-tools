import os
import time
import pandas as pd

from build.orbethon import *
import argparse
from elf import process_address,print_sections,process_string_table,process_symbol_table,process_debug_string,get_text_bin
from irq_names import irq_names_stm32h753,irq_names_stm32f765
from spi_decode import spi_decode_csv,digital_spi_csv
from protocol_synchronize import getWorkQueuePattern

arg2tsType = {
    "a" : TSType.TSAbsolute,
    "r" : TSType.TSRelative,
    "d" : TSType.TSDelta,
    "s" : TSType.TSStamp,
    "t" : TSType.TSStampDelta
}


def processOptions(args,work_queue_pattern,sync_edges,elf_file,functions,miso_edges, mosi_edges, clk_edges, cs_edges,spi_decoded_mosi,spi_decoded_miso):
    """
    Takes the input arguments and creates a options struct which is needed as input for orbetto tool
    Input:
        - args : arguments received from argparse
    Return:
        - options struct
    """
    print("Process Options ...")
    # init Options class
    options = Options_Struct()
    # default options
    options.cps = args.cpufreq * 1000
    options.tsType = arg2tsType[args.timestamp]
    # input file name
    options.std_file = args.input_file
    # parse options
    options.endTerminate = args.eof
    # bin elf file
    options.elf_file = elf_file
    # enable debug
    options.outputDebugFile = args.debug
    #parsed functions
    options.functions = functions
    # spi debug 
    options.miso_digital = miso_edges
    options.mosi_digital = mosi_edges
    options.clk_digital = clk_edges
    options.cs_digital = cs_edges
    options.spi_decoded_mosi = spi_decoded_mosi
    options.spi_decoded_miso = spi_decoded_miso
    # Sync
    options.workqueue_intervals_spi = work_queue_pattern
    options.sync_digital = sync_edges
    return options



def init_argparse():
    """ 
    Initializes the argparse library with the needed arguments and the according defaults.
    Return:
        - all parsed arguments
    """
    parser = argparse.ArgumentParser(
        prog='Orbethon', description='Run Orbetto Tool from Python.')
    parser.add_argument('-T', '--timestamp',
                        help="Add absolute, relative (to session start),delta, system timestamp or system timestamp delta to output."
                        + "Note a,r & d are host dependent and you may need to run orbuculum with -H.",
                        type=str,
                        choices=['a', 'r', 'd', 's', 't'],
                        default='s'
                        )
    parser.add_argument('-C', '--cpufreq',
                        help="<Frequency in KHz> (Scaled) speed of the CPU."
                        + "generally /1, /4, /16 or /64 of the real CPU speed",
                        type=int,
                        default=216000
                        )
    parser.add_argument('-E', '--eof',
                        help="Terminate when the file/socket ends/is closed, or wait for more/reconnect",
                        action='store_true',
                        default=True
                        )
    parser.add_argument('-f', '--input_file',
                        help="<filename> Take input from specified file",
                        type=str,
                        default='../../../PX4-Autopilot/trace.swo'
                        )
    parser.add_argument('-e', '--elf',
                        help="<filename> Use this ELF file for information",
                        type=str,
                        default='../../../PX4-Autopilot/build/px4_fmu-v5x_default/px4_fmu-v5x_default.elf'
                        )
    parser.add_argument('-d','--device',
                        help="select stm32h753 or stm32f765",
                        type=str,
                        choices=['stm32h753','stm32f765'],
                        default='stm32f765')
    parser.add_argument('-sa','--spi_analog',
                        help="select spi analog csv file to decode",
                        type=str,
                        default='../../../Logic2/analog.csv')
    parser.add_argument('-dd','--dynamic_decoding',
                        help="enable dynamic decoding, which improves computation time if the same analog spi data is used multiple times",
                        action='store_true',
                        default=False)
    parser.add_argument('-db','--debug',
                        help="enable debug output",
                        action='store_true',
                        default=False)

    return parser.parse_args()


if __name__ == "__main__":
    start_time = time.time()
    args = init_argparse()
    if not args.dynamic_decoding:
        # check if buffer dir exists if yes delete it
        if os.path.exists("buffer"):
            os.system('rm -rf buffer')
    df = pd.read_csv(args.spi_analog)
    work_queue_pattern,sync_edges = getWorkQueuePattern(df)
    miso_edges, mosi_edges, clk_edges, cs_edges = digital_spi_csv(df)
    spi_decoded_mosi, spi_decoded_miso = spi_decode_csv(miso_edges, mosi_edges, clk_edges, cs_edges)
    elf_file = list(get_text_bin(args.elf))
    functions = process_symbol_table(args.elf)
    options = processOptions(args,work_queue_pattern,sync_edges,elf_file,functions,miso_edges, mosi_edges, clk_edges, cs_edges,spi_decoded_mosi,spi_decoded_miso)
    print("Orbethon Tool took %s minutes %s seconds to run in python" % (int((time.time() - start_time)/60),int((time.time() - start_time)%60)))
    print("Run Orbetto Tool ...")
    if args.device == 'stm32h753':
        orbethon(options,irq_names_stm32h753)
    elif args.device == 'stm32f765':
        orbethon(options,irq_names_stm32f765)
