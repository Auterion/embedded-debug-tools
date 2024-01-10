import time
import pandas as pd
import os

from build.orbethon import *
import argparse
from elf import process_symbol_table, get_text_bin
from irq_names import irq_names_stm32h753, irq_names_stm32f765
from spi_decode import spi_decode, edge_detection_on_spi
from protocol_synchronize import getWorkQueuePattern

arg2tsType = {
    "a": TSType.TSAbsolute,
    "r": TSType.TSRelative,
    "d": TSType.TSDelta,
    "s": TSType.TSStamp,
    "t": TSType.TSStampDelta
}


def processOptions(args, options):
    """
    Takes the input arguments and add them to the options struct.
    Input:
        - args : arguments received from argparse
        - options : options struct
    """
    # cpu frequency
    options.cps = args.cpufreq * 1000
    # timestamp type
    options.tsType = arg2tsType[args.timestamp]
    # input file name
    options.std_file = args.input_file
    # terminate when file ends
    options.endTerminate = args.eof
    # enable debug
    options.outputDebugFile = args.debug
    # enable spi debug
    options.spi_debug = args.enable_spi_debug


def init_argparse(options):
    """ 
    Initializes the argparse library with the needed arguments and the according defaults.
    Input:
        - options : options struct
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
    parser.add_argument('-d', '--device',
                        help="select stm32h753 or stm32f765",
                        type=str,
                        choices=['stm32h753', 'stm32f765'],
                        default='stm32f765')
    parser.add_argument('--enable_spi_debug',
                        help="enable spi debug output",
                        action='store_true',
                        default=False)
    parser.add_argument('-sa', '--spi_analog',
                        help="select spi analog csv file to decode",
                        type=str,
                        default='../../../Logic2/analog.csv')
    parser.add_argument('-dd', '--dynamic_decoding',
                        help="enable dynamic decoding, which improves computation time if the same analog spi data is used multiple times",
                        action='store_true',
                        default=False)
    parser.add_argument('-db', '--debug',
                        help="enable debug output",
                        action='store_true',
                        default=False)
    # get arguments
    args = parser.parse_args()
    # add arguments that are directly handed to orbetto to options struct
    processOptions(args, options)
    return args


def decode_analog_protocols(args, options):
    """
    Decode analog spi and sync data with ripyl and save it to options struct
    Input:
        - args : arguments received from argparse
        - options : options struct
    """
    # read csv file that stores analog spi and sync data with pandas
    df = pd.read_csv(args.spi_analog)
    # perform edge detection on analog sync signal and extract work queue pattern
    options.workqueue_intervals_spi, options.sync_digital = getWorkQueuePattern(
        df)
    # perform edge detection on analog spi signals
    signal = edge_detection_on_spi(df)
    # save decoded spi signals to options struct
    options.mosi_digital = signal[1]
    options.miso_digital = signal[0]
    options.clk_digital = signal[2]
    options.cs_digital = signal[3]
    # decode spi data with ripyl
    options.spi_decoded_mosi, options.spi_decoded_miso = spi_decode(signal)


def read_elf_file(args, options):
    """
    Extract relevant information from elf file and save it to options struct
    Input:
        - args : arguments received from argparse
        - options : options struct
    """
    # extract .text section from elf file
    options.elf_file = list(get_text_bin(args.elf))
    # read symbol table from elf file and extract function names and pointers to start of function
    options.functions = process_symbol_table(args.elf)


def main():
    # ---------- Init Arguments ----------#
    # init Options class which stores all data needed for orbetto tool
    options = Options_Struct()
    # get arguments and write them to options struct
    args = init_argparse(options)
    if args.enable_spi_debug:
        # check if dynamic decoding is disabled to delete buffer folder which then will be created again with new data
        if not args.dynamic_decoding:
            # check if buffer dir exists if yes delete it
            if os.path.exists("buffer"):
                os.system('rm -rf buffer')

        # ---------- Decode SPI ----------#
        decode_analog_protocols(args, options)

    # ---------- Decode ELF ----------#
    read_elf_file(args, options)

    # ---------- Run Orbetto Tool ----------#
    print("Run Orbetto Tool ...")
    if args.device == 'stm32h753':
        orbethon(options, irq_names_stm32h753)
    elif args.device == 'stm32f765':
        orbethon(options, irq_names_stm32f765)
    else:
        raise Exception(f"  {args.device} Device not supported")


if __name__ == "__main__":
    start_time = time.time()
    main()
    print("Orbethon Tool took %s minutes %s seconds to run." % (
        int((time.time() - start_time)/60), int((time.time() - start_time) % 60)))
