#-------------------------------------------------------------------------------
#   Extract symbol Table
#
#   Simple functionality that extracts and inspects an ELF file's symbol table with
#   the high-level API of pyelftools.
#
#   Note:
#   This is adapted from the elf_low_high_api.py example from the pyelftools library
#
#   Installation:
#   pip install pyelftools
# 
#   Symbol Table:
#   The symbol table typically includes entries for each symbol, containing information
#   such as the symbol's name, type, size, and address. It also indicates whether the
#   symbol is defined in the file or is just a reference to an external symbol.
#
#-------------------------------------------------------------------------------
from elftools.common.utils import bytes2str
from elftools.dwarf.descriptions import describe_form_class
from elftools.elf.elffile import ELFFile
from elftools.elf.sections import SymbolTableSection,StringTableSection

import elftools.common.utils as ecu
import cxxfilt

def get_text_bin(filename):
    print("Get Text Bin ...")
    with open(filename, 'rb') as f:
        elffile = ELFFile(f)

        # Find the .text section
        text_section = elffile.get_section_by_name('.text')

        if text_section is None:
            print("  No .text section found in the ELF file.")
            return None

        # Read the binary content of the .text section
        f.seek(text_section['sh_offset'])
        print("  The offset of the .text section is %s" % text_section['sh_offset'])
        text_binary = f.read(text_section['sh_size'])

        return text_binary


def process_address(filename,address):
    print("Process Address ...")
    with open(filename, 'rb') as f:
        elffile = ELFFile(f)
        ro = elffile.get_section_by_name('.text')
        ro_addr_delta = ro['sh_addr'] - ro['sh_offset']
        offset = address - ro_addr_delta
        s = ecu.parse_cstring_from_stream(ro.stream, offset)
        print(  s.decode('utf-8') if s else '')

def process_addresses(filename,addresses):
    print("Process Addresses ...")
    with open(filename, 'rb') as f:
        elffile = ELFFile(f)
        ro = elffile.get_section_by_name('.text')
        ro_addr_delta = ro['sh_addr'] - ro['sh_offset']
        for address in addresses:
            offset = address - ro_addr_delta
            try:
                s = ecu.parse_cstring_from_stream(ro.stream, offset)
                #print( str(address))
                bin = s.decode('utf-8').encode('unicode_escape')
                if bin:
                    print(  bin )
                else:
                    pass
            except:
                pass

def demangle_cpp_function_name(func_name):
    # remove everything after the first . in func_name
    return cxxfilt.demangle(func_name)
    

def process_symbol_table(filename):
    functions = []
    names = []
    print("Process elf file ...")
    with open(filename, 'rb') as f:
        elffile = ELFFile(f)
        section = elffile.get_section_by_name('.symtab')
        if not section:
            print('  No symbol table found. Perhaps this ELF has been stripped?')
            return

        # A section type is in its header, but the name was decoded and placed in
        # a public attribute.
        print('  Section name: %s, type: %s' %(section.name, section['sh_type']))

        if isinstance(section, SymbolTableSection):
            num_symbols = section.num_symbols()
            for i in range(num_symbols):
                symbol = section.get_symbol(int(i))
                symbol_info = symbol['st_info']
                symbol_type = symbol_info['type']
                symbol_name = symbol.name
                symbol_address = symbol['st_value']
                symbol_other = symbol['st_other']
                # symbol_type == 'STT_NOTYPE' and symbol_info['bind']=='STB_LOCAL' and symbol_name == '$d' and symbol_other['local'] == 0 and symbol_other['visibility'] == "STV_DEFAULT" and symbol["st_name"] == 15
                if symbol_type == 'STT_FUNC':
                    #print("  The name of the %s th symbol is %s and its address is: 0x%0x and its type is %s and its size is %s" % (int(i),symbol_name,symbol_address,symbol_type,symbol['st_size']))
                    if symbol_name not in names:
                        names.append(symbol_name)
                        if(symbol_name[:2] == "_Z"):
                            demangled_name = demangle_cpp_function_name(symbol_name)
                            # print("  Demangled name: %s" % demangled_name)
                            functions.append((symbol_address,demangled_name))
                        else:
                            functions.append((symbol_address,symbol_name))
    sorted_functions = sorted(functions, key=lambda x: x[0])
    return sorted_functions

def process_string_table(filename):
    print("Process elf file ...")
    with open(filename, 'rb') as f:
        elffile = ELFFile(f)
        for section in elffile.iter_sections():
            if section.name == '.strtab':
                # .strtab is a common name for the string table section
                string_table = section
                break
        else:
            print("  No string table found in the ELF file.")
            return

        # Read the entire string table data
        string_table_data = string_table.data()

        # Extract strings from the string table
        string_offset = 0
        while string_offset < len(string_table_data):
            # Decode null-terminated strings
            string = ''
            while string_table_data[string_offset] != 0:
                string += chr(string_table_data[string_offset])
                string_offset += 1
            print(f"  String: {string}")
            # Move to the next string in the table
            string_offset += 1

def process_debug_string(filename):
    print("Process elf file ...")
    with open(filename,'rb') as f:
        elffile = ELFFile(f)

        debug_info_section = elffile.get_section_by_name('.debug_info')
        debug_str_section = elffile.get_section_by_name('.debug_str')

        if debug_str_section is None:
            print("  No .debug_str section found in the ELF file.")
            return

        # Iterate through compilation units in .debug_info
        for cu in elffile.get_dwarf_info().iter_CUs():
            for die in cu.iter_DIEs():
                #if die.tag == 'DW_TAG_string_type':
                # Iterate through all attributes in the DIE
                if 'DW_AT_name' in die.attributes:
                    # Get the offset of the string in .debug_str
                    print("  " + die.attributes['DW_AT_name'].value)


def print_sections(filename):
    print("Sections ...")
    with open(filename, 'rb') as f:
        elffile = ELFFile(f)
        for section in elffile.iter_sections():
            print(f"  Section {section.name} has Type {section['sh_type']}")
        