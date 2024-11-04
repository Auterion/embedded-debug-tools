import pandas as pd
from queries import *
from display import *
from elfFileDecode import *
import argparse

def init_argparse():
    parser = argparse.ArgumentParser(description="Visualize trace metrics")
    parser.add_argument('-f','--file',
                        help='Path to protobuf trace file',
                        type = str,
                        required = False)
    parser.add_argument('-f2','--file2',
                        help='Path to second protobuf trace file for diffs',
                        type = str,
                        required = False)
    parser.add_argument('-wq','--work_queue_overview',
                        help='Display work queue overview. (Runnable/Running)',
                        action='store_true',
                        default = False)
    parser.add_argument('-dwq','--detailed_work_queue',
                        help='Display detailed work queue overview. (Runnable/Running)',
                        action='store_true',
                        default = False)
    parser.add_argument('-fp','--function_pairs',
                        help='Display function pairs',
                        action='store_true',
                        default = False)
    parser.add_argument('-fr','--function_regularity',
                        help='Display function regularity',
                        action='store_true',
                        default = False)
    parser.add_argument('-dma','--dma_throughputs',
                        help='Display DMA throughput',
                        action='store_true',
                        default = False)
    parser.add_argument('-sd','--semaphore_deadlocks',
                        help='Display semaphore deadlocks',
                        action='store_true',
                        default = False)
    parser.add_argument('-db','--debug',
                        help='Display debug information',
                        action='store_true',
                        default = False)
    parser.add_argument('-hp', "--heap_profile",
                        help='Display heap profile',
                        action='store_true',
                        default = False)
    parser.add_argument('-cc',"--code_coverage",
                        help='Display code coverage',
                        action='store_true',
                        default = False)
    parser.add_argument('-bm',"--bitmap",
                        help='Path to bitmap file which is needed for code coverage',
                        type = str,
                        required = False)
    parser.add_argument('-elf',"--elf_file",
                        help='Path to elf file which is needed for code coverage',
                        type = str,
                        required = False)

    parser.add_argument('-diff', "--difference",
                        help='Switch all other options to display differences between two trace files',
                        action='store_true',
                        default = False)
    
    return parser.parse_args()



def cpu_time():
    cpu_running = get_all_cpu_time('Running')
    cpu_runnable = get_all_cpu_time('R')
    total_cpu_running_time = cpu_running['cpu_time'].sum()
    cpu_running['percentage'] = cpu_running['cpu_time']/total_cpu_running_time * 100
    total_cpu_runnable_time = cpu_runnable['cpu_time'].sum()
    cpu_runnable['percentage'] = cpu_runnable['cpu_time']/total_cpu_runnable_time * 100
    bar_chart(cpu_running,cpu_runnable,'thread_name','percentage','cpu_time')

def cpu_waiting_time():
    df = get_detailed_thread_state_perfetto()
    cpu_waiting_time_pie_chart(df)

def function_distribution():
    functions = get_function_distribution()
    custom_data_bar_chart(functions)

def regularity():
    df = get_function_intervals()
    df['merged'] = df.apply(lambda row: (row['interval'], row['next_slice_id'],row['thread_name']), axis=1)
    dict = df.groupby('slice_name')['merged'].apply(list).to_dict()
    histogram(dict)

def dma_throughputs():
    pass

def semaphore_deadlocks():
    pass

def extract_malloc(df):
    df_malloc = df[df['allocation_type']=='malloc']
    df_malloc['allocation_info'] = df_malloc['slice_name'].apply(lambda x: x.split('[')[1][:-1])
    df_malloc['allocation_pointer'] = df_malloc['allocation_info'].apply(lambda x: x.split(',')[0])
    df_malloc['allocation_size'] = df_malloc['allocation_info'].apply(lambda x: int(x.split(',')[1]))
    return df_malloc

def extract_free(df):
    df_free = df[df['allocation_type']=='free']
    df_free['allocation_pointer'] = df_free['slice_name'].str.extract(r'\((.*?)\)')
    df_free['allocation_size'] = df_free['slice_name'].apply(lambda x: -int(x.split('(')[2][:-1]))
    return df_free


def match_heap_pointers(df1,df2):
    # copy
    df_malloc = df1.copy()
    df_free = df2.copy()
    # convert to int
    df_malloc['ts'] = df_malloc['ts'].astype(int)
    df_free['ts'] = df_free['ts'].astype(int)
    # reset index
    df_malloc.reset_index(drop=True, inplace=True)
    df_free.reset_index(drop=True, inplace=True)
    for index, row in df_malloc.iterrows():
        # Filter rows that match the conditions
        future_frees = df_free[(df_free['allocation_pointer'] == row['allocation_pointer']) &
                               (df_free['ts'] >= row['ts'])]
        if not future_frees.empty:
            df_malloc.drop(index, inplace=True)
            df_free.drop(future_frees['ts'].idxmin(), inplace=True)
    assert(df_free.empty)
    return df_malloc


def extract_heap_profile(df):
    if df.empty:
        print("No heap profile data found")
        return None
    df['allocation_type'] = df['slice_name'].apply(lambda x: x.split('(')[0])
    df_malloc = extract_malloc(df)
    df_free = extract_free(df)
    return pd.concat([df_malloc,df_free]), match_heap_pointers(df_malloc,df_free)

def heap_profile():
    df = get_heap_profile()
    df, df_matched = extract_heap_profile(df)
    if(df is not None):
        heap_pie_chart(df, title="absolute count")
        heap_counter(df, title="counter")
        heap_pie_chart(df_matched , title="absolute count matched")
        heap_counter(df_matched, title="counter_matched")


def diff_heap_profile(df1,df2):
    max_ts = min(df1['ts'].max(),df2['ts'].max())
    df1 = df1[df1['ts'] <= max_ts]
    df2 = df2[df2['ts'] <= max_ts]
    df2['allocation_size'] = df2['allocation_size'] * -1
    return pd.concat([df1,df2])

def heap_profile_diff():
    df1 = get_heap_profile()
    df1, df1_matched = extract_heap_profile(df1)
    df2 = get_heap_profile2()
    df2, df2_matched = extract_heap_profile(df2)
    if(df1 is not None and df2 is not None):
        df = diff_heap_profile(df1,df2)
        df_matched = diff_heap_profile(df1_matched,df2_matched)
        heap_pie_chart(df, title="absolute count")
        heap_counter(df, title="counter")
        heap_pie_chart(df_matched, title="absolute count matched")
        heap_counter(df_matched, title="counter_matched")


def code_coverage(elf, path):
    set_elffile_and_bitmap(elf, path)
    init_bitmap()
    df = get_all_function_names()
    display_code_coverage(df)


def code_coverage_diff():
    pass
    
if __name__ == "__main__":
    args = init_argparse()
    init_trace_processor(args.file)
    if args.difference:
        assert(args.file2)
        init_trace_processor2(args.file2)  
    if args.work_queue_overview:
        if args.difference:
            pass
        else:
            cpu_time()
    if args.detailed_work_queue:
        if args.difference:
            pass
        else:
            cpu_waiting_time()
    if args.function_pairs:
        if args.difference:
            pass
        else:
            function_distribution()
    if args.function_regularity:
        if args.difference:
            pass
        else:
            regularity()
    if args.dma_throughputs:
        if args.difference:
            pass
        else:
            dma_throughputs()
    if args.semaphore_deadlocks:
        if args.difference:
            pass
        else:
            semaphore_deadlocks()
    if args.heap_profile:
        if args.difference:
            heap_profile_diff()
        else:
            heap_profile()
    if args.code_coverage:
        if args.bitmap and args.elf_file:
            if args.difference:
                pass
            else:
                code_coverage(args.elf_file, args.bitmap)
        else:
            print("Please provide a bitmap file")
    show(args.debug)


