import pandas as pd
from queries import *
from display import *
import argparse

def init_argparse():
    parser = argparse.ArgumentParser(description="Visualize trace metrics")
    parser.add_argument('-f','--file',
                        help='Path to protobuf trace file',
                        type = str,
                        required = True)
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
    thread_waiting_time_aggregated,thread_waiting_time = get_thread_waiting_time('R')
    thread_running_time_aggregated,thread_running_time = get_thread_running_time('Running')
    pie_chart(thread_waiting_time_aggregated,thread_running_time_aggregated,thread_waiting_time,thread_running_time)

def function_distribution():
    functions = get_function_distribution()
    threads = functions['thread_name'].unique()
    thread_functions_dict = {}
    for thread in threads:
        data = functions[functions['thread_name'] == thread].sort_values(by='count',ascending=False)
        total_cpu_time = data['cpu_time'].sum()
        data['percentage'] = data['cpu_time']/total_cpu_time * 100
        thread_functions_dict.update([(thread,data)])
    custom_data_bar_chart(thread_functions_dict)

def regularity():
    df = get_function_intervals()
    df['merged'] = df.apply(lambda row: (row['interval'], row['next_slice_id'],row['thread_name']), axis=1)
    dict = df.groupby('slice_name')['merged'].apply(list).to_dict()
    histogram(dict)

def dma_throughputs():
    pass

def semaphore_deadlocks():
    pass

if __name__ == "__main__":
    args = init_argparse()
    init_trace_processor(args.file)
    if args.work_queue_overview:
        cpu_time()
    if args.detailed_work_queue:
        cpu_waiting_time()
    if args.function_pairs:
        function_distribution()
    if args.function_regularity:
        regularity()
    if args.dma_throughputs:
        dma_throughputs()
    if args.semaphore_deadlocks:
        semaphore_deadlocks()
    show(args.debug)

