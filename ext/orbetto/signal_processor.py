from ripyl.decode import find_edges
import pandas as pd
import os

def find_edges_dynamic(data, name, logic_levels,hysteresis):
    """
    Find edges in a list of samples
    Inputs:
        data: list of samples
        logic_levels: Tuple of logic levels (low,high) [V]
        hysteresis: hysteresis [V]
    Returns:
        edges: list of tuples (time,value)
    """
    edges = []
    # check if buffer folder exits in current directory
    if not os.path.exists("buffer"):
        os.makedirs("buffer")
    # check if csv file with data already exists
    if os.path.exists("buffer/"+name+".csv"):
        # read csv file with pandas
        df = pd.read_csv("buffer/"+name+".csv")
        # check if csv file contains data
        if len(df.index) > 0:
            # convert df to list of tuples
            edges = list(df.itertuples(index=False, name=None))
    else:
        # compute edges
        edges = list(find_edges(data, logic_levels,hysteresis=hysteresis))
        # save as csv file in buffer folder
        df = pd.DataFrame(edges,columns=['Time [s]','Value'])
        df.to_csv("buffer/"+name+".csv",index=False)
    return edges