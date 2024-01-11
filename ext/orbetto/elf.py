# -------------------------------------------------------------------------------
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
# -------------------------------------------------------------------------------

from elftools.elf.elffile import ELFFile
from elftools.elf.sections import SymbolTableSection

import cxxfilt


def get_text_bin(filename):
    """
    Get the binary content of the .text section of the given ELF file.
    Input:
        - filename : path to the elf file
    Output:
        - text_binary : binary content of the .text section
    """
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
        print("  The offset of the .text section is %s" %
              text_section['sh_offset'])
        text_binary = f.read(text_section['sh_size'])

        return text_binary


def _demangle_cpp_function_name(func_name):
    """
    Demangle a C++ function name using the cxxfilt module.
    Input:
        - func_name : C++ function name
    Output:
        - demangled_name : demangled C++ function name
    """
    # remove everything after the first . in func_name
    return cxxfilt.demangle(func_name)


def process_symbol_table(filename):
    """
    Process the symbol table of the given ELF file and extract all function names and pointers to start of function.
    Also demangle C++ function names.
    Input:
        - filename : path to the elf file
    Output:
        - sorted_functions : list of tuples (address,name) sorted by address (ascending)
    """
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
        print('  Section name: %s, type: %s' %
              (section.name, section['sh_type']))

        if isinstance(section, SymbolTableSection):
            num_symbols = section.num_symbols()
            for i in range(num_symbols):
                symbol = section.get_symbol(int(i))
                symbol_info = symbol['st_info']
                symbol_type = symbol_info['type']
                symbol_name = symbol.name
                symbol_address = symbol['st_value']
                if symbol_type == 'STT_FUNC':
                    # print("  The name of the %s th symbol is %s and its address is: 0x%0x and its type is %s and its size is %s" % (int(i),symbol_name,symbol_address,symbol_type,symbol['st_size']))
                    if symbol_name not in names:
                        names.append(symbol_name)
                        if (symbol_name[:2] == "_Z"):
                            demangled_name = _demangle_cpp_function_name(
                                symbol_name)
                            # print("  Demangled name: %s" % demangled_name)
                            functions.append((symbol_address, demangled_name))
                        else:
                            functions.append((symbol_address, symbol_name))
    sorted_functions = sorted(functions, key=lambda x: x[0])
    return sorted_functions
