import pandas as pd
import numpy as np
from ripyl.streaming import SampleChunk

from signal_processor import find_edges_dynamic

def getWorkQueuePattern(df,length=20,logic_levels=(0,3.3),hyst=0.05):
    """
    Read csv file of analog SPI and generate pattern for Sync data
    Inputs:
        path: Path to the csv file containing the samples
        signal_length: Number of work queue switches to analyze (optional)
        logic_levels: Tuple of logic levels (low,high) [V]
    Returns:
        work_queue_pattern: list of work queue switch intervals
    """
    print("Parse SPI SYNC data ...")
    # read csv file with pandas
    try:
        sample_period = df["Time [s]"][1]-df["Time [s]"][0]
    except:
        # print Error message
        raise Exception("  CSV File seems empty")
    try:
        sync_list = df["Sync"].tolist()
    except:
        # print Error message
        # only valid for Salea Sampling Rate of 10 [MS/s]
        raise Exception("  You need at least 100000000 samples to build a valid pattern")
    try:
        sync_analog = [SampleChunk(sync_list,df["Time [s]"][0],sample_period)]
    except:
        # print Error message
        raise Exception("  CSV File does not contain Sync information")
    # get edges
    edges = find_edges_dynamic(sync_analog,"sync", logic_levels,hysteresis=hyst)
    # get first 20 intervals
    if (length > (len(edges))):
        print("  Warning: Number of sampled work queue switches is less than the specified pattern length")
        length = len(edges)
    # get two intervals which are at 1/3 and 2/3 of the total length
    work_queue_patterns = []
    for offset in [int(len(edges)/3),int(2*len(edges)/3)]:
        work_queue_pattern = []
        for i in range(offset,offset+length):
            work_queue_pattern.append((int(edges[i][0]*1e9),int((edges[i+1][0]-edges[i][0])*1e9)))
        work_queue_patterns.append(work_queue_pattern)
    # work_queue_pattern2 = []
    # for i in range(start2,start2+length):
    #     work_queue_pattern2.append(int((edges[i+1][0]-edges[i][0])*1e9))
    # convert list of tuples to df
    df_edges = pd.DataFrame(edges,columns=['Time [s]','Value'])
    # change time to ns
    df_edges['Time [s]'] = df_edges['Time [s]']*1e9
    # convert time to int
    df_edges['Time [s]'] = df_edges['Time [s]'].astype(int)
    # convert back to list of tuples
    edges_return = list(df_edges.itertuples(index=False, name=None))
    return work_queue_patterns,edges_return



