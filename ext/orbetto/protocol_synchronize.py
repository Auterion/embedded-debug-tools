import pandas as pd
import numpy as np
from ripyl.decode import find_edges
from ripyl.streaming import SampleChunk

def getWorkQueuePattern(path,length=20,logic_levels=(0,3.3),hyst=0.4):
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
    df = pd.read_csv(path)
    try:
        sample_period = df["Time [s]"][1]-df["Time [s]"][0]
    except:
        # print Error message
        raise Exception("  CSV File seems empty")
    try:
        sync_analog = [SampleChunk(df["Sync"][0:100000000].tolist(),df["Time [s]"][0],sample_period)]
    except:
        # print Error message
        raise Exception("  CSV File does not contain Sync information")
    # get edges
    edges = list(find_edges(sync_analog, logic_levels,hysteresis=hyst))
    # get first 20 intervals
    if (length > (len(edges))):
        print("  Warning: Number of sampled work queue switches is less than the specified pattern length")
        length = len(edges)
    work_queue_pattern = []
    for i in range(50,50+length):
        work_queue_pattern.append(int((edges[i+1][0]-edges[i][0])*1e9))
    return work_queue_pattern, int(edges[0][0]*1e9)



