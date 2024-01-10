import pandas as pd
import numpy as np
import time

import ripyl.protocol.spi as spi
import ripyl.streaming as streaming
from ripyl.streaming import SampleChunk

from signal_processor import find_edges_dynamic


def _get_protocol_information_only(df_input):
    """
    Extract all columns from DataFrame which are needed for SPI protocol analysis
    and perform some preprocessing.
    Inputs:
        df_input: DataFrame containing all columns
    Returns:
        df: DataFrame containing only the needed and transformed columns
    """
    pd.options.mode.chained_assignment = None
    df = df_input[['Time [s]', 'MOSI', 'MISO', 'CLK', 'CS']]
    # convert timestamps to ns with .loc()
    df['Time [s]'] = df['Time [s]'] * 1e9
    # convert every type to int
    df['Time [s]'] = df['Time [s]'].astype(int)
    if (df['CS'] > 3).any():
        # if cs is bigger than 3V, set every other signal to 0
        df.loc[df['CS'] > 3, ['MOSI', 'MISO', 'CLK']] = 0
        # get index of first CS rising edge
        start = df[df['CS'] > 3].index[0]
        # set every sample before the first CS rising edge to 0
        df.loc[0:start-1, ['MOSI', 'MISO', 'CLK']] = 0
    return df


def edge_detection_on_spi(df_input, buffer_dir):
    """
    Perform edge detection on analog SPI CSV.
    Inputs:
        df_input: DataFrame containing all columns
    Returns:
        miso_edges: list of tuples (timestamp,value)
        mosi_edges: list of tuples (timestamp,value)
        clk_edges: list of tuples (timestamp,value)
        cs_edges: list of tuples (timestamp,value)
    """
    print("Perform edge detection on analog SPI CSV ...")
    df = _get_protocol_information_only(df_input)
    # create SampleChunks
    period = df["Time [s]"][1]-df["Time [s]"][0]
    miso_sc = [SampleChunk(df["MISO"].tolist(), df["Time [s]"][0], period)]
    mosi_sc = [SampleChunk(df["MOSI"].tolist(), df["Time [s]"][0], period)]
    clk_sc = [SampleChunk(df["CLK"].tolist(), df["Time [s]"][0], period)]
    cs_sc = [SampleChunk(df["CS"].tolist(), df["Time [s]"][0], period)]
    # Perform edge detection
    miso_edges = find_edges_dynamic(miso_sc, buffer_dir / "miso.csv", (0, 5), hysteresis=0.4)
    mosi_edges = find_edges_dynamic(mosi_sc, buffer_dir / "mosi.csv", (0, 3.3), hysteresis=0.4)
    clk_edges = find_edges_dynamic(clk_sc, buffer_dir / "clk.csv", (0, 3.3), hysteresis=0.4)
    cs_edges = find_edges_dynamic(cs_sc, buffer_dir / "cs.csv", (0, 3.3), hysteresis=0.4)
    return miso_edges, mosi_edges, clk_edges, cs_edges

def _decode_SPI_Frame(word_size, value):
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


def spi_decode(signal, cpol=1, cpha=0, lsb_first=0, stream_type=streaming.StreamType.Edges):
    """
    Decode SPI messages with ripyl library from csv File
    Inputs:
        signal: list of tuples (timestamp,value) for MISO, MOSI, CLK and CS (in this order)
        cpol: Clock polarity: 0 or 1 (the idle state of the clock signal)
        cpha: Clock phase: 0 or 1 (data is sampled on the 1st clock edge (0) or the 2nd (1))
        lsb_first: Least significant bit first: 0 or 1
        stream_type: Streaming type: streaming.StreamType.Edges or streaming.StreamType.Samples
        voltage_levels: tuple of voltage levels (low,high)
    Returns:
        mosi_bin: array of decoded MOSI samples with timestamps (in this order: start_time, end_time, word)
        miso_bin: array of decoded MISO samples with timestamps (in this order: start_time, end_time, word)
    """
    print("Decode SPI CSV ...")
    # decode the SPI stream
    mosi_it = spi.spi_decode(iter(signal[2]), iter(signal[1]), iter(
        signal[3]), cpol=cpol, cpha=cpha, lsb_first=lsb_first, stream_type=stream_type)
    miso_it = spi.spi_decode(iter(signal[2]), iter(signal[0]), iter(
        signal[3]), cpol=cpol, cpha=cpha, lsb_first=lsb_first, stream_type=stream_type)
    # convert to list and display
    mosi_list = list(mosi_it)
    miso_list = list(miso_it)
    # extract every sample from the list which is a StreamSegment object
    mosi_bin = []
    for i in mosi_list:
        if (type(i) == spi.SPIFrame):
            word = _decode_SPI_Frame(i.word_size, i.data)
            mosi_bin.append((int(i.start_time), int(i.end_time), word))
    miso_bin = []
    for i in miso_list:
        if (type(i) == spi.SPIFrame):
            word = _decode_SPI_Frame(i.word_size, i.data)
            miso_bin.append((int(i.start_time), int(i.end_time), word))
    return mosi_bin, miso_bin
