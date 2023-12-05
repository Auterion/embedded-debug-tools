import pandas as pd
import numpy as np
import time

import ripyl.protocol.spi as spi
import ripyl.streaming as streaming
from ripyl.streaming import SampleChunk
from ripyl.decode import find_edges

def _get_protocol_information_only(df_input):
    """
    Extract all columns from DataFrame which are needed for SPI protocol analysis
    """
    pd.options.mode.chained_assignment = None
    df = df_input[['Time [s]','MOSI','MISO','CLK','CS']]
    # convert timestamps to ns with .loc()
    df['Time [s]'] = df['Time [s]'] * 1e9
    # convert every type to int
    df['Time [s]'] = df['Time [s]'].astype(int)
    # if cs is bigger than 3V, set every other signal to 0
    df.loc[df['CS'] > 3, ['MOSI','MISO','CLK']] = 0
    # get index of first CS rising edge
    start = df[df['CS'] > 3].index[0]
    # set every sample before the first CS rising edge to 0
    df.loc[0:start-1, ['MOSI','MISO','CLK']] = 0
    return df


def digital_spi_csv(df_input):
    print("Perform edge detection on analog SPI CSV ...")
    df = _get_protocol_information_only(df_input)
    # create SampleChunks
    period = df["Time [s]"][1]-df["Time [s]"][0]
    miso_sc = [SampleChunk(df["MISO"].tolist(),df["Time [s]"][0],period)]
    mosi_sc = [SampleChunk(df["MOSI"].tolist(),df["Time [s]"][0],period)]
    clk_sc = [SampleChunk(df["CLK"].tolist(),df["Time [s]"][0],period)]
    cs_sc = [SampleChunk(df["CS"].tolist(),df["Time [s]"][0],period)]
    # Perform edge detection
    miso_edges = list(find_edges(miso_sc, (0,5),hysteresis=0.4))
    mosi_edges = list(find_edges(mosi_sc, (0,3.3),hysteresis=0.4))
    clk_edges = list(find_edges(clk_sc, (0,3.3),hysteresis=0.4))
    cs_edges = list(find_edges(cs_sc, (0,3.3),hysteresis=0.4))
    return miso_edges, mosi_edges, clk_edges, cs_edges

def read_csv_file(path, signal_length=None):
    """
    Read csv file and return lists of SPI Channels
    Inputs:
        path: Path to the csv file containing the samples
        signal_length: Number of samples to read (optional)
    Returns:
        clk: list of CLK samples
        cs: list of CS samples
        miso: list of MISO samples
        mosi: list of MOSI samples
        timestamps: list of timestamps
        sample_period: list of sample periods
"""
    start=0
    # read csv file with pandas
    df = pd.read_csv(path)
    df.loc[df['CS'] > 3.1, ['MOSI','MISO','CLK']] = 0
    # get index of first CS rising edge
    start = df[df['CS'] > 3].index[0]
    # set every sample before the first CS rising edge to 0
    df.loc[0:start-1, ['MOSI','MISO','CLK']] = 0
    try:
        sample_period = df["Time [s]"][1]-df["Time [s]"][0]
    except:
        # print Error message
        raise Exception("CSV File seems empty")
    if signal_length != None:
        return df['CLK'][start:signal_length].tolist(), df['CS'][start:signal_length].tolist(), df['MISO'][start:signal_length].tolist(), df['MOSI'][start:signal_length].tolist(),df["Time [s]"][start:signal_length].tolist(), sample_period
    else:
        return df['CLK'].tolist(), df['CS'].tolist(), df['MISO'].tolist(), df['MOSI'].tolist(),df["Time [s]"].tolist(), sample_period

def convert_to_iterable_SampleChunk(data,timestamps,sample_period):
    """
    Converts a list of samples to a SampleChunk object with constant sample period 
    Inputs:
        data: list of samples
        timestamps: list of timestamps
        sample_period: sample period
    Returns:
        chunk: iterable SampleChunk object
    """
    return [SampleChunk(data,timestamps[0],sample_period)]

def decode_SPI_Frame(word_size, value):
    """
    Decodes a SPI Frame
    Inputs:
        word_size: size of the word in bits
        value: value of the word
    Returns:
        data: decoded data
    """
    data = []
    for i in range(int(word_size/8)):
        data.append((value >> (i*8)) & 0xFF)
    return data

def spi_decode_csv(miso, mosi, clk, cs, cpol=1, cpha=0, lsb_first=0, stream_type=streaming.StreamType.Edges):
    """
    Decode SPI messages with ripyl library from csv File
    Inputs:
        path: Path to the csv file containing the samples
        cpol: Clock polarity: 0 or 1 (the idle state of the clock signal)
        cpha: Clock phase: 0 or 1 (data is sampled on the 1st clock edge (0) or the 2nd (1))
        lsb_first: Least significant bit first: 0 or 1
        stream_type: Streaming type: streaming.StreamType.Edges or streaming.StreamType.Samples
        voltage_levels: tuple of voltage levels (low,high)
    Returns:
        mosi_bin: array of MOSI samples with timestamps
        miso_bin: array of MISO samples with timestamps
    """
    print("Decode SPI CSV ...")
    # decode the SPI stream
    mosi_it = spi.spi_decode(iter(clk), iter(mosi), iter(cs), cpol=cpol, cpha=cpha, lsb_first=lsb_first, stream_type=stream_type)
    miso_it = spi.spi_decode(iter(clk), iter(miso), iter(cs), cpol=cpol, cpha=cpha, lsb_first=lsb_first, stream_type=stream_type)
    # convert to list and display
    mosi_list = list(mosi_it)
    miso_list = list(miso_it)
    # extract every sample from the list which is a StreamSegment object
    mosi_bin = []
    for i in mosi_list:
        if(type(i)==spi.SPIFrame):
            word = decode_SPI_Frame(i.word_size,i.data)
            mosi_bin.append((int(i.start_time),int(i.end_time),word))
    miso_bin = []
    for i in miso_list:
        if(type(i)==spi.SPIFrame):
            word = decode_SPI_Frame(i.word_size,i.data)
            miso_bin.append((int(i.start_time),int(i.end_time),word))
    return mosi_bin, miso_bin