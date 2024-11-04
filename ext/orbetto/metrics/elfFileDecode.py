from elftools.common.utils import bytes2str
from elftools.dwarf.descriptions import describe_form_class
from elftools.elf.elffile import ELFFile
import pandas as pd
from pyroaring import BitMap
import numpy as np
from dash import html

GREEN = "\033[92m"  # Green color code
RESET = "\033[0m"   # Reset color code

elf_path = None
roar_path = None
bitmap = None

# Documentation for dwarf classes in pyelftools can be found here:
# https://github.com/eliben/pyelftools/tree/main/elftools/dwarf

def set_elffile_and_bitmap(elf_path_input, roar_path_input):
    global elf_path
    global roar_path
    elf_path = elf_path_input
    roar_path = roar_path_input

def get_all_function_names():
    if elf_path is None:
        print("Please set the elf file")
        return
    
    print('Processing file:', elf_path)
    with open(elf_path, 'rb') as f:
        elffile = ELFFile(f)

        if not elffile.has_dwarf_info():
            print('  file has no DWARF info')
            return

        # get_dwarf_info returns a DWARFInfo context object, which is the
        # starting point for all DWARF-based processing in pyelftools.
        dwarfinfo = elffile.get_dwarf_info()

        # Return Pandas DataFrame with all function information
        df = pd.DataFrame(columns=['File','Function Name'])

        #count = 0
        for CU in dwarfinfo.iter_CUs():
            #if count > 100:
            #    break
            #count += 1
            TOP_DIE = CU.get_top_DIE()
            if ".cpp" in bytes2str(TOP_DIE.attributes['DW_AT_name'].value):
                path = TOP_DIE.attributes['DW_AT_name'].value
            else:
                path = TOP_DIE.attributes['DW_AT_comp_dir'].value + bytes('/', 'utf-8') + TOP_DIE.attributes['DW_AT_name'].value
            for DIE in CU.iter_DIEs():
                # check for function tag
                if DIE.tag == 'DW_TAG_subprogram':
                    try:
                        if DIE.attributes['DW_AT_inline'].value == 3:
                            continue
                    except KeyError:
                        pass
                    try:
                        DIE.attributes['DW_AT_low_pc'].value
                        DIE.attributes['DW_AT_high_pc'].value
                    except KeyError:
                        continue
                    # check for function name
                    try :
                        if DIE.attributes['DW_AT_name'] is not None:
                            df = pd.concat([df, pd.DataFrame({'File': [bytes2str(path)], 'Function Name': [bytes2str(DIE.attributes['DW_AT_name'].value)]})])
                    except KeyError:
                        continue
        return df


def get_function_info(function_path, function_name):

    if elf_path is None:
        print("Please set the elf file")
        return
    
    with open(elf_path, 'rb') as f:
        elffile = ELFFile(f)

        if not elffile.has_dwarf_info():
            print('  file has no DWARF info')
            return

        # get_dwarf_info returns a DWARFInfo context object, which is the
        # starting point for all DWARF-based processing in pyelftools.
        dwarfinfo = elffile.get_dwarf_info()

        # Return Pandas DataFrame with all function information
        source_code = decode_funcname( dwarfinfo, function_path, function_name)

    return source_code


def decode_funcname(dwarfinfo, function_path, function_name):
    source_code = []
    for CU in dwarfinfo.iter_CUs():
        try:
            TOP_DIE = CU.get_top_DIE()
            if ".cpp" in bytes2str(TOP_DIE.attributes['DW_AT_name'].value):
                path = TOP_DIE.attributes['DW_AT_name'].value
            else:
                path = TOP_DIE.attributes['DW_AT_comp_dir'].value + bytes('/', 'utf-8') + TOP_DIE.attributes['DW_AT_name'].value
            if(path == function_path):
                for DIE in CU.iter_DIEs():
                    # check for function tag
                    if DIE.tag == 'DW_TAG_subprogram':
                        # check for function name
                        try :
                            DIE.attributes['DW_AT_name'].value
                        except KeyError:
                            continue
                        if DIE.attributes['DW_AT_name'].value == function_name:
                            low_line, high_line, l, a, inline = get_max_min_line(CU, dwarfinfo)
                            if low_line is not None and high_line is not None:
                                source_code = get_code_lines(function_path, low_line, high_line)
                                lines = np.arange(low_line, high_line)
                                for i,line in enumerate(lines):
                                    idx = np.where(np.isin(l, line))
                                    if len(idx[0]) > 0 and len(source_code) > i:
                                        # check if address is in bitmap
                                        if a[idx[0][0]] in bitmap:
                                            print(f"Line {line} with Address {hex(a[idx[0][0]])} is covered")
                                            source_code[i] = html.Mark(source_code[i], style={'background-color': "rgba(0, 255, 0, 0.1)"})
                                        else:
                                            source_code[i] = html.Mark(source_code[i], style={'background-color': "rgba(255, 0, 0, 0.1)"})
        except KeyError:
            continue
    return source_code

def get_max_min_line(CU, dwarfinfo):
    lineprog = dwarfinfo.line_program_for_CU(CU)
    max = 0
    min = 100000
    prev_addr = 0
    lines = []
    addresses = []
    inline = []
    for entry in lineprog.get_entries():
        if entry.state is None:
            continue
        if prev_addr != entry.state.address:
            prev_addr = entry.state.address
            if entry.state.line not in lines:
                lines.append(entry.state.line)
                addresses.append(entry.state.address)
                if entry.state.file != 1:
                    inline.append(True)
                else:
                    inline.append(False)
        if entry.state.line > max:
            max = entry.state.line
        if entry.state.line < min:
            min = entry.state.line
    if max == 0 or min == 100000:
        return None, None, None, None, None
    
    return min, max, lines, addresses, inline

def get_code_lines(file_name, low_line, high_line):
    try:
        with open(file_name, 'r') as file:
            lines = file.readlines()
            return lines[low_line - 1:high_line]
    except FileNotFoundError:
        return f"File {file_name} not found."
    except IndexError:
        return f"Lines {low_line}:{high_line} out of range in {file_name}."
    
def read_roar_file():
    """
    Read a Roaring bitmap from a .roar file, assuming the file contains
    serialized 8-bit unsigned integers.
    """
    values = []
    with open(roar_path, 'rb') as f:
        # Read the entire file content as bytes
        data = f.read()
        
        # Ensure that the length of the data is not empty
        if len(data) == 0:
            raise ValueError("File is empty. No data to read.")
        
        # Each byte is an 8-bit unsigned integer
        for byte in data:
            values.append(byte)  # Append each byte (0-255) to the list

    return values

def init_bitmap():
    global bitmap
    #Load values from the .roar file
    values_from_file = read_roar_file()

    # Create a BitMap instance and update it with the values
    bm = BitMap()
    bm = bm.deserialize(bytes(values_from_file))

    bitmap = bm.to_array()

def format_code_coverage(df):
    # Function to apply styling without loop
    def highlight_green(column):
        # Create a Series where True values get 'background-color: green' and False gets ''
        return ['background-color: green' if v else '' for v in df['Highlight']]

    # Apply the style
    return df.style.apply(highlight_green, subset=['Code'])
