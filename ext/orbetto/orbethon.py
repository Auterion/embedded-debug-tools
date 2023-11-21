import os

os.system('rm -rf build')
os.system('meson setup build')
os.system('ninja -C build')

from build.orbethon import *
import argparse
from elf import process_address,print_sections,process_string_table,process_symbol_table,process_debug_string,get_text_bin
from irq_names import irq_names_stm32h753,irq_names_stm32f765

arg2tsType = {
    "a" : TSType.TSAbsolute,
    "r" : TSType.TSRelative,
    "d" : TSType.TSDelta,
    "s" : TSType.TSStamp,
    "t" : TSType.TSStampDelta
}


def processOptions(args,functions):
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
    # set options based on args
    options.cps = args.cpufreq * 1000
    options.tsType = arg2tsType[args.timestamp]
    options.endTerminate = args.eof
    options.file = args.input_file
    options.functions = functions
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

    return parser.parse_args()


if __name__ == "__main__":
    args = init_argparse()
    #print_sections(args.elf)
    elf_bin = list(get_text_bin(args.elf))
    #process_string_table(args.elf)
    functions = process_symbol_table(args.elf)
    #process_debug_string(args.elf)
    options = processOptions(args,functions)
    print("Run Orbetto Tool ...")
    if (args.device == 'stm32h753'):
        orbethon(options,elf_bin,irq_names_stm32h753)
    elif (args.device == 'stm32f765'):
        orbethon(options,elf_bin,irq_names_stm32f765)
