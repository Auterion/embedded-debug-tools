import pandas as pd
import numpy as np

import ripyl.protocol.spi as spi
import ripyl.streaming as streaming
from ripyl.streaming import SampleChunk



def analog_spi_csv(path):
    print("Parse analog SPI CSV ...")
    df = pd.read_csv(path)[0:20000]
    # convert timestamps to ns
    df['Time [s]'] = df['Time [s]'] * 1e9
    # convert timestamp to integer
    df['Time [s]'] = df['Time [s]'].astype(int)
    df = df.drop_duplicates(subset=['Time [s]'])
    tuples = df.to_records(index=False).tolist()
    return tuples

def digital_spi_csv(path):
    print("Parse digital SPI CSV ...")
    df = pd.read_csv(path)[0:20000]
    # convert timestamps to ns
    df['Time [s]'] = df['Time [s]'] * 1e9
    # convert every type to int
    df['Time [s]'] = df['Time [s]'].astype(int)
    # reduce df to unqiue timestamps
    df = df.drop_duplicates(subset=['Time [s]'])
    tuples = df.to_records(index=False).tolist()
    return tuples

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

def spi_decode_csv(path, cpol=1, cpha=0, lsb_first=0, stream_type=streaming.StreamType.Samples,voltage_levels=(0,3.3)):
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
    if (stream_type == streaming.StreamType.Samples):
        # get data from path
        clk,cs, miso, mosi, timestamps, sample_period = read_csv_file(path,signal_length=20000)
        #clk,cs, miso, mosi, timestamps, sample_period = read_csv_file(path)
        # Convert data to iterable SampleChunk objects
        clk = convert_to_iterable_SampleChunk(clk,timestamps,sample_period)
        miso = convert_to_iterable_SampleChunk(miso,timestamps,sample_period)
        mosi = convert_to_iterable_SampleChunk(mosi,timestamps,sample_period)
        cs = convert_to_iterable_SampleChunk(cs,timestamps,sample_period)
    elif (stream_type==streaming.StreamType.Edges):
        raise Exception("  StreamType.Edges not implemented yet")
    else:
        raise Exception("  Wrong StreamType. Choose between streaming.StreamType.Edges and streaming.StreamType.Samples")

    # decode the SPI stream
    mosi_it = spi.spi_decode(clk, mosi, cs, cpol=cpol, cpha=cpha, lsb_first=lsb_first,logic_levels=voltage_levels, stream_type=stream_type)
    miso_it = spi.spi_decode(clk, miso, cs, cpol=cpol, cpha=cpha, lsb_first=lsb_first,logic_levels=voltage_levels, stream_type=stream_type)
    # convert to list and display
    mosi_list = list(mosi_it)
    miso_list = list(miso_it)
    # extract every sample from the list which is a StreamSegment object
    mosi_bin = []
    for i in mosi_list:
        if(type(i)==spi.SPIFrame):
            bytes = decode_SPI_Frame(i.word_size,i.data)
            mosi_bin.append((int(i.start_time*1000000),int(i.end_time*1000000),bytes))
    miso_bin = []
    for i in miso_list:
        if(type(i)==spi.SPIFrame):
            bytes = decode_SPI_Frame(i.word_size,i.data)
            miso_bin.append((int(i.start_time*1000000),int(i.end_time*1000000),bytes))
    return mosi_bin,miso_bin