#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <unistd.h>
#include <string.h>
#include <gelf.h>
#include <dwarf.h>
#include <libdwarf.h>

#include "loadelf.h"
#include "generics.h"

#define MAX_LINE_LEN (4095)
// ====================================================================================================
// ====================================================================================================
// ====================================================================================================
// Internal routines
// ====================================================================================================
// ====================================================================================================
// ====================================================================================================

static int _compareMem( const void *a, const void *b )
{
    const symbolMemaddr as = ( ( struct symbolMemoryStore * )a )->start;
    const symbolMemaddr bs = ( ( struct symbolMemoryStore * )b )->start;

    if ( as < bs )
    {
        return -1;
    }

    if ( as > bs )
    {
        return 1;
    }

    return 0;
}

// ====================================================================================================

static int _compareFunc( const void *a, const void *b )
{
    const symbolMemaddr as = ( *( struct symbolFunctionStore ** )a )->lowaddr;
    const symbolMemaddr bs = ( *( struct symbolFunctionStore ** )b )->lowaddr;

    if ( as < bs )
    {
        return -1;
    }

    if ( as > bs )
    {
        return 1;
    }

    return 0;
}

// ====================================================================================================

static int _matchFunc( const void *a, const void *b )
{
    const unsigned int key = *( uint64_t * )a;
    const symbolMemaddr as = ( *( struct symbolFunctionStore ** )b )->lowaddr;
    const symbolMemaddr ae = ( *( struct symbolFunctionStore ** )b )->highaddr;

    if ( key < as )
    {
        return -1;
    }

    if ( key > ae )
    {
        return 1;
    }

    return 0;
}

// ====================================================================================================

static int _compareLineMem( const void *a, const void *b )

{
    const symbolMemaddr as = ( *( struct symbolLineStore ** )a )->lowaddr;
    const symbolMemaddr bs = ( *( struct symbolLineStore ** )b )->lowaddr;

    if ( as < bs )
    {
        return -1;
    }

    if ( as > bs )
    {
        return 1;
    }

    return 0;
}

// ====================================================================================================

static int _matchLine( const void *a, const void *b )
{
    const symbolMemaddr key = *( uint64_t * )a;
    const symbolMemaddr as = ( *( struct symbolLineStore ** )b )->lowaddr;
    const symbolMemaddr ae = ( *( struct symbolLineStore ** )b )->highaddr;

    if ( key < as )
    {
        return -1;
    }

    if ( key > ae )
    {
        return 1;
    }

    return 0;
}
// ====================================================================================================

static bool _readProg( int fd, struct symbol *p )

{
    Elf *e;
    Elf_Scn *scn = NULL;
    GElf_Shdr shdr;
    size_t shstrndx;
    char *name;

    if ( elf_version( EV_CURRENT ) == EV_NONE )
    {
        fprintf( stderr, "ELF library initialization failed : %s ", elf_errmsg ( -1 ) );
        return p;
    }

    if ( ( e = elf_begin( fd, ELF_C_READ, NULL ) ) == NULL )
    {
        fprintf( stderr, "ELF Begin failed\n" );
        return false;
    }

    if ( elf_getshdrstrndx( e, &shstrndx ) != 0 )
    {
        fprintf( stderr, "elf_getshdrstrndx failed: %s\n", elf_errmsg( -1 ) );
        return false;
    }

    /* Read this into memory by iterating over sections */
    while ( ( scn = elf_nextscn( e, scn ) ) != NULL )
    {

        if ( gelf_getshdr( scn, &shdr ) != &shdr )
        {
            fprintf( stderr, "getshdr () failed : %s\n", elf_errmsg( -1 ) );
            return false;
        }

        if ( ( name = elf_strptr ( e, shstrndx, shdr.sh_name ) ) == NULL )
        {
            fprintf( stderr, " elf_strptr () failed : %s\n", elf_errmsg ( -1 ) );
            return false;
        }

        //            printf("%c ADDR=%08lx Type=%8x Flags=%04lx Size=%08lx Name=%s\n",((shdr.sh_flags & SHF_ALLOC) && (shdr.sh_type==SHT_PROGBITS))?'L':' ', shdr.sh_addr, shdr.sh_type, shdr.sh_flags, shdr.sh_size, name);

        if ( ( shdr.sh_flags & SHF_ALLOC ) && ( shdr.sh_type == SHT_PROGBITS ) )
        {
            Elf_Data *data = NULL;

            /* This is program code or data; Allocate a new section */
            if ( ( data = elf_rawdata ( scn, data ) ) != NULL )
            {
                p->mem = ( struct symbolMemoryStore * )realloc( p->mem, ( p->nsect_mem + 1 ) * sizeof( struct symbolMemoryStore ) );
                struct symbolMemoryStore *n = p->mem + p->nsect_mem;
                p->nsect_mem++;

                n->start = shdr.sh_addr;
                n->len   = shdr.sh_size;
                n->name  = strdup( name );
                n->data  = ( uint8_t * )malloc( n->len );
                memmove( n->data, data->d_buf, n->len );
            }
        }
    }

    /* Sort mem sections into order so it's straightforward to find matches */
    qsort( p->mem, p->nsect_mem, sizeof( struct symbolMemoryStore ), _compareMem );
    p->cachedSearchIndex = -1;
    elf_end( e );
    return p;
}

// ====================================================================================================

int _findOrAddString( const char *stringToFindorAdd, char ***table, unsigned int *elementCount )

{
    /* Find the string in the specified table (and return its index) or create a new string record and return that index */
    for ( int i = 0; i < *elementCount; i++ )
    {
        if ( !strcmp( ( *table )[i], stringToFindorAdd ) )
        {
            return i;
        }
    }

    /* This string doesn't exist...add it and then return the index */
    *table = ( char ** )realloc( *table, sizeof( char * ) * ( ( *elementCount ) + 1 ) );
    ( *table )[*elementCount] = strdup( stringToFindorAdd );

    ( *elementCount )++;
    return ( *elementCount ) - 1;
}

// ====================================================================================================

static void _getSourceLines( struct symbol *p, Dwarf_Debug dbg, Dwarf_Die die )


{
    Dwarf_Unsigned version;
    Dwarf_Line_Context linecontext;
    Dwarf_Line *linebuf;
    Dwarf_Signed linecount;
    Dwarf_Small tc;
    Dwarf_Addr line_addr;
    char *file_name;
    Dwarf_Unsigned line_num;


    /* Now, for each source line, pull it into the line storage */
    if ( DW_DLV_OK == dwarf_srclines_b( die, &version, &tc, &linecontext, 0 ) )
    {
        dwarf_srclines_from_linecontext( linecontext, &linebuf, &linecount, 0 );

        for ( int i = 0; i < linecount; ++i )
        {
            // Get the line number and the corresponding address
            dwarf_lineno( linebuf[i], &line_num, 0 );
            dwarf_lineaddr( linebuf[i], &line_addr, 0 );
            dwarf_linesrc( linebuf[i], &file_name, 0 );

            p->line = ( struct symbolLineStore ** )realloc( p->line, sizeof( struct symbolLineStore * ) * ( p->nlines + 1 ) );
            struct symbolLineStore *newLine = p->line[p->nlines] = ( struct symbolLineStore * )calloc( 1, sizeof( struct symbolLineStore ) );
            p->nlines++;
            newLine->startline = line_num;
            newLine->lowaddr = line_addr;
            newLine->isinline = true;
            newLine->filename = _findOrAddString( file_name, &p->stringTable[PT_FILENAME],  &p->tableLen[PT_FILENAME] );
        }

        dwarf_srclines_dealloc_b( linecontext );
    }
}

// ====================================================================================================

static void _processFunctionDie( struct symbol *p, Dwarf_Debug dbg, Dwarf_Die die, int filenameN, int producerN )

{
    char *name = NULL;
    Dwarf_Addr h = 0;
    Dwarf_Addr l = 0;
    Dwarf_Attribute attr_data;
    Dwarf_Half attr_tag;
    struct symbolFunctionStore *newFunc;


    dwarf_highpc_b ( die, &h, 0, 0, 0 );
    dwarf_lowpc ( die, &l, 0 );

    if ( l && ( l != h ) )
    {
        /* This has length, so it's valid ... create a new function entry */
        if ( DW_DLV_OK != dwarf_diename( die, &name, 0 ) )
        {
            attr_tag = DW_AT_abstract_origin;

            if ( dwarf_attr( die, attr_tag, &attr_data, 0 ) == DW_DLV_OK )
            {
                Dwarf_Off abstract_origin_offset;
                Dwarf_Die abstract_origin_die;
                dwarf_global_formref( attr_data, &abstract_origin_offset, 0 );
                dwarf_offdie_b( dbg, abstract_origin_offset, true, &abstract_origin_die, 0 );
                dwarf_diename( abstract_origin_die, &name, 0 );
            }
        }

        p->func = ( struct symbolFunctionStore ** )realloc( p->func, sizeof( struct symbolFunctionStore * ) * ( p->nfunc + 1 ) );
        newFunc = p->func[p->nfunc] = ( struct symbolFunctionStore * )calloc( 1, sizeof( struct symbolFunctionStore ) );
        p->nfunc++;

        newFunc->funcname  = strdup( name );
        newFunc->producer  = producerN;
        newFunc->filename  = filenameN;
        newFunc->lowaddr   = l;
        newFunc->highaddr  = h - 1;

        /* Collect start of function line and column */
        attr_tag = DW_AT_decl_line;

        if ( dwarf_attr( die, attr_tag, &attr_data, 0 ) == DW_DLV_OK )
        {
            Dwarf_Unsigned no;
            dwarf_formudata( attr_data, &no, 0 );
            newFunc->startline = no;
        }

        attr_tag = DW_AT_decl_column;

        if ( dwarf_attr( die, attr_tag, &attr_data, 0 ) == DW_DLV_OK )
        {
            Dwarf_Unsigned no;
            dwarf_formudata( attr_data, &no, 0 );
            newFunc->startcol = no;
        }
    }
}

// ====================================================================================================

static void _processDie( struct symbol *p, Dwarf_Debug dbg, Dwarf_Die die, int level, int filenameN, int producerN )

{
    Dwarf_Error err;
    Dwarf_Half tag;

    dwarf_tag( die, &tag, &err );

    if ( tag == DW_TAG_subprogram )
    {
        _processFunctionDie( p, dbg, die, filenameN, producerN );
    }

    // Recursively process children DIEs
    Dwarf_Die child;

    int res = dwarf_child( die, &child, &err );

    if ( res == DW_DLV_OK )
    {
        do
        {
            _processDie( p, dbg, child, level + 1, filenameN, producerN );

        }
        while ( dwarf_siblingof_b( dbg, child, true, &child, &err ) == DW_DLV_OK );
    }
}
// ====================================================================================================

static bool _readLines( int fd, struct symbol *p )
{
    Dwarf_Debug dbg;
    Dwarf_Error err;
    Dwarf_Unsigned cu_header_length;
    Dwarf_Half     version_stamp;
    Dwarf_Off      abbrev_offset;
    Dwarf_Half     address_size;
    Dwarf_Unsigned next_cu_header = 0;
    Dwarf_Die cu_die;

    Dwarf_Half dw_length_size;
    Dwarf_Half dw_extension_size;
    Dwarf_Sig8 dw_type_signature;
    Dwarf_Unsigned dw_typeoffset;
    Dwarf_Half dw_header_cu_type;

    char *name;
    char *producer;
    char *compdir;

    unsigned int filenameN;
    unsigned int producerN;

    if ( 0 != dwarf_init_b( fd, DW_GROUPNUMBER_ANY, NULL, NULL, &dbg, &err ) )
    {
        return false;
    }

    /* Add an empty string to each string table, so the 0th element is the empty string in all cases */
    for ( enum symbolTables pt = 0; pt < PT_NUMTABLES; pt++ )
    {
        _findOrAddString( "", &p->stringTable[pt],  &p->tableLen[pt] );
    }

    /* 1: Collect the functions and lines */
    /* ---------------------------------- */
    while (DW_DLV_OK == dwarf_next_cu_header_d( dbg, true, &cu_header_length, &version_stamp, &abbrev_offset, &address_size, &dw_length_size, &dw_extension_size, &dw_type_signature, &dw_typeoffset, &next_cu_header, &dw_header_cu_type, &err ))
    {
        dwarf_siblingof_b( dbg, NULL, 1, &cu_die, &err );
        dwarf_diename( cu_die, &name, &err );
        dwarf_die_text( cu_die, DW_AT_producer, &producer, &err );
        dwarf_die_text( cu_die, DW_AT_comp_dir, &compdir, &err );


        /* Need to construct the fully qualified filename from the directory + filename */
        char *s = ( char * )malloc( strlen( name ) + strlen( compdir ) + 2 );
        strcpy( s, compdir );
        strcat( s, "/" );
        strcat( s, name );
        filenameN  = _findOrAddString( s, &p->stringTable[PT_FILENAME],  &p->tableLen[PT_FILENAME] );
        free( s );
        producerN =  _findOrAddString( producer, &p->stringTable[PT_PRODUCER],  &p->tableLen[PT_PRODUCER] );

        /* Kickoff the process for the DIE and its children to get the functions in this cu */
        _processDie( p, dbg, cu_die, 0, filenameN, producerN );

        /* ...and the source lines */
        _getSourceLines( p, dbg, cu_die );
        }

    /* 2: We have the lines and functions. Clean them up and interlink them so they're useful to applications */
    /* ------------------------------------------------------------------------------------------------------ */
    /* Sort tables into address order, just in case they're not ... no gaurantees from the DWARF */
    qsort( p->line, p->nlines, sizeof( struct symbolLineStore * ), _compareLineMem );
    qsort( p->func, p->nfunc, sizeof( struct symbolFunctionStore * ), _compareFunc );

    /* Combine addresses in the lines table which have the same memory location...those aren't too useful for us      */
    for ( int i = 1; i < p->nlines; i++ )
    {
        while ( ( i < p->nlines ) && ( ( p->line[i]->filename == p->line[i - 1]->filename ) ) && ( ( p->line[i]->lowaddr == p->line[i - 1]->lowaddr ) ) )
        {
            /* This line needs to be freed in memory 'cos otherwise there is no reference to it anywhere */
            free( p->line[i - 1] );

            /* ...and move the following lines down */
            for ( int j = i; j < p->nlines; j++ )
            {
                p->line[j - 1] = p->line[j];
            }

            p->nlines--;
        }

        /* Now set the high extent address to one less than the low address of the following line */
        //      p->line[i-1]->highaddr = p->line[i]->lowaddr-1;
    }

    /* Now do the same for lines with the same line number and file */
    /* We can also set the high memory extent for each line here */
    for ( int i = 1; i < p->nlines; i++ )
    {
        while ( ( i < p->nlines ) &&
                ( p->line[i]->startline == p->line[i - 1]->startline ) &&
                ( p->line[i]->filename == p->line[i - 1]->filename ) )
        {

            p->line[i]->lowaddr = p->line[i - 1]->lowaddr;
            free( p->line[i - 1] );

            for ( int j = i; j < p->nlines; j++ )
            {
                p->line[j - 1] = p->line[j];
            }

            p->nlines--;
        }

        p->line[i - 1]->highaddr = p->line[i]->lowaddr - 1;
    }

    p->line[p->nlines - 1]->highaddr = -1;

    /* Allocate lines to functions ... these will be in address order 'cos the lines already are */
    for ( int i = 0; i < p->nlines; i++ )
    {
        struct symbolFunctionStore *f = symbolFunctionAt( p, p->line[i]->lowaddr );
        p->line[i]->function = f;
        p->line[i]->isinline = false;

        if ( f )
        {
            f->line = ( struct symbolLineStore ** )realloc( f->line, sizeof( struct symbolLineStore * ) * ( f->nlines + 1 ) );
            f->line[f->nlines] = p->line[i];
            f->nlines++;
        }
    }

    dwarf_finish( dbg );

    return true;
}

// ====================================================================================================

static bool _loadSource( struct symbol *p )

{
    char *w = NULL;
    size_t m = 0;
    FILE *fd;
    char commandLine[MAX_LINE_LEN];
    bool notProcess;

    /* We need to aqquire source code for all of the files that we have an entry in the stringtable, so let's start by making room */
    p->source = ( struct symbolSourcecodeStore ** )calloc( 1, sizeof( struct symbolSourcecodeStore * )*p->tableLen[PT_FILENAME] );

    for ( int i = 0; i < p->tableLen[PT_FILENAME]; i++ )
    {
        /* Try and grab the file via a prettyprinter. If that doesn't work, grab it via cat */
        if ( getenv( "ORB_PRETTYPRINTER" ) )
        {
            /* We have an environment variable containing the prettyprinter...lets use that */
            snprintf( commandLine, MAX_LINE_LEN, "%s %s", getenv( "ORB_PRETTYPRINTER" ), p->stringTable[PT_FILENAME][i] );
        }
        else
        {
            /* No environment variable, use the default */
            snprintf( commandLine, MAX_LINE_LEN, "source-highlight -f esc -o STDOUT -i %s 2>/dev/null", p->stringTable[PT_FILENAME][i] );
        }

        fd = popen( commandLine, "r" );
        /* Perform a single read...this will lead to eof if the command wasn't valid */
        getline( &w, &m, fd );

        if ( feof( fd ) )
        {
            pclose( fd );
            notProcess = true;

            if ( !( fd = fopen( p->stringTable[PT_FILENAME][i], "r" ) ) )
            {
                continue;
            }

            getline( &w, &m, fd );
        }

        /* Create an entry for this file. It will be zero (NULL) if there are no lines in it */
        struct symbolSourcecodeStore *store = p->source[i] = ( struct symbolSourcecodeStore * )calloc( 1, sizeof( struct symbolSourcecodeStore ) );

        while ( !feof( fd ) )
        {
            /* Add this line to the storage. We strdup the line storage because the getline call tends to be too generous */
            store->linetext = ( char ** )realloc( store->linetext, sizeof( char * ) * ( store->nlines + 1 ) );
            store->linetext[store->nlines++] = strdup( w );
            getline( &w, &m, fd );
        }

        /* Close the process or file, depending on what it was that actually got opened */
        notProcess ? fclose( fd ) : pclose( fd );
    }

    free( w );
    return true;
}

// ====================================================================================================
// ====================================================================================================
// ====================================================================================================
// Publically available routines
// ====================================================================================================
// ====================================================================================================
// ====================================================================================================

const char *symbolSource( struct symbol *p, unsigned int fileNumber, unsigned int lineNumber )

/* Return pointer to source code for specified line in file index */

{
    assert( p );

    if ( ( fileNumber < p->tableLen[PT_FILENAME] ) && ( lineNumber < p->source[fileNumber]->nlines ) )
    {
        return ( const char * )p->source[fileNumber]->linetext[lineNumber];
    }
    else
    {
        return NULL;
    }
}
// ====================================================================================================

struct symbolFunctionStore *symbolFunctionAt( struct symbol *p, symbolMemaddr addr )

/* Return function that encloses specified address, or NULL */

{
    assert( p );
    struct symbolFunctionStore **fp = ( struct symbolFunctionStore ** )bsearch( &addr, p->func, p->nfunc, sizeof( struct symbolFunctionStore * ), _matchFunc );

    return fp ? *fp : NULL;
}

// ====================================================================================================

struct symbolFunctionStore *symbolFunctionIndex( struct symbol *p, unsigned int index )

/* Get indexed function, or NULL if out of range */

{
    assert( p );
    return ( index < p->nfunc ) ? p->func[index] : NULL;
}

// ====================================================================================================
struct symbolLineStore *symbolLineIndex( struct symbol *p, unsigned int index )

/* Get indexed line, or NULL if out of range */

{
    assert( p );
    return ( index < p->nlines ) ? p->line[index] : NULL;
}
// ====================================================================================================

struct symbolLineStore *symbolFunctionLineIndex( struct symbolFunctionStore *f, unsigned int index )

/* Get indexed line with distinct memory address covered by function */

{
    assert( f );
    return ( index < f->nlines ) ? f->line[index] : NULL;
}
// ====================================================================================================

struct symbolLineStore *symbolLineAt( struct symbol *p, symbolMemaddr addr )

/* Return line covered by specified memory address, or NULL */

{
    assert( p );
    struct symbolLineStore **l = ( struct symbolLineStore ** )bsearch( &addr, p->line, p->nlines, sizeof( struct symbolLineStore * ), _matchLine );
    return l ? *l : NULL;
}

// ====================================================================================================

const char *symbolGetProducer( struct symbol *p, unsigned int index )

/* Get command line that produced this code */

{
    assert( p );
    return ( index < p->tableLen[PT_PRODUCER] ) ? p->stringTable[PT_PRODUCER][index] : NULL;
}

// ====================================================================================================

const char *symbolGetFilename( struct symbol *p, unsigned int index )

/* Get filename string for specified index */

{
    assert( p );
    return ( index < p->tableLen[PT_FILENAME] ) ? p->stringTable[PT_FILENAME][index] : NULL;
}

// ====================================================================================================

symbolMemptr symbolCodeAt( struct symbol *p, symbolMemaddr addr, unsigned int *len )

/* Get pointer to memory at specified address...can move backwards and forwards through the region */

{
    assert( p );
    int i;

    /* A speedup in case we're looking in the same region as previously */
    if ( ( p->cachedSearchIndex != -1 ) &&
            ( p->mem[p->cachedSearchIndex].start < addr ) &&
            ( addr - p->mem[p->cachedSearchIndex].start < p->mem[p->cachedSearchIndex].len ) )
    {
        if ( len )
        {
            *len = p->mem[p->cachedSearchIndex].len - ( addr - p->mem[p->cachedSearchIndex].start );
        }

        return &( p->mem[p->cachedSearchIndex].data[addr - p->mem[p->cachedSearchIndex].start] );
    }

    /* Search backwards for candidate section for memory to be in. This could be       */
    /* slightly more efficient as a binary search, but setup would offset any benefits */
    for ( i = p->nsect_mem - 1; i && p->mem[i].start > addr; i-- );

    /* Are we within this code? */
    if ( addr - p->mem[i].start < p->mem[i].len )
    {
        p->cachedSearchIndex = i;

        if ( len )
        {
            *len = p->mem[i].len - ( addr - p->mem[i].start );
        }

        return &( p->mem[i].data[addr - p->mem[i].start] );
    }
    else
    {
        p->cachedSearchIndex = -1;
        return NULL;
    }
}

// ====================================================================================================

void symbolDelete( struct symbol *p )

/* Delete symbol set */

{
    if ( p )
    {
        if ( p->nsect_mem )
        {
            for ( int i = p->nsect_mem - 1; i; i-- )
            {
                if ( p->mem[i].name )
                {
                    free( p->mem[i].name );

                    if ( p->mem[i].data )
                    {
                        free( p->mem[i].data );
                    }
                }
            }

            free( p->mem );
        }

        while ( p->nfunc )
        {
            struct symbolFunctionStore *f = p->func[--p->nfunc];

            if ( f->funcname )
            {
                /* Remove the functionName, assuming we have one */
                free( f->funcname );
            }

            if ( f->line )
            {
                /* ...and any source code cross-references */
                free( f->line );
            }

            free( f );
        }

        /* Flush the string tables */
        for ( enum symbolTables pt = 0; pt < PT_NUMTABLES; pt++ )
        {
            while ( p->tableLen[pt] )
            {
                free( p->stringTable[pt][--p->tableLen[pt]] );
            }
        }

        /* Flush the source code line records */
        for ( int i = 0; i < p->nlines; i++ )
        {
            free( p->line[i] );
        }

        if ( p->line )
        {
            free( p->line );
        }

        /* Remove any source code we might be holding */
        for ( int i = 0; i < p->tableLen[PT_FILENAME]; i++ )
        {
            for ( int j = 0; j < p->source[i]->nlines; j++ )
            {
                free( p->source[i]->linetext );
            }

            free( p->source[i] );
        }

        free( p );
    }
}

// ====================================================================================================

struct symbol *symbolAqquire( char *filename, bool loadlines, bool loadmem, bool loadsource )

/* Collect symbol set with specified components */

{
    int fd;
    struct symbol *p = NULL;

    if ( ( fd = open( filename, O_RDONLY, 0 ) ) < 0 )
    {
        return NULL;
    }

    p = ( struct symbol * )calloc( 1, sizeof( struct symbol ) );

    /* Load the memory image if this was requested...if it fails then we fail */
    if ( loadmem && ( !_readProg( fd, p ) ) )
    {
        symbolDelete( p );
        close( fd );
        return NULL;
    }

    /* Load the functions and source code line mappings if requested */
    if ( loadlines && !_readLines( fd, p ) )
    {
        symbolDelete( p );
        close( fd );
        return NULL;
    }

    close( fd );

    /* ...finally, the source code if requested. This can only be done if mem or functions we requested */
    if ( ( loadsource && ( loadmem || loadlines ) )  && !_loadSource( p ) )
    {
        symbolDelete( p );
        return NULL;
    }

    return p;
}
// ====================================================================================================
bool symbolSetValid( struct symbol *p, char *filename )

/* Check if current symbols are valid */

{
    return p != NULL;
}

