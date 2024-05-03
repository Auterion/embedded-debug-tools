from perfetto.trace_processor import TraceProcessor
tp = TraceProcessor(trace='/Users/lukasvonbriel/Desktop/PX4_ITM_Trace/orbetto.perf')

cpu_metrics = tp.metric(['android_cpu'])
print(cpu_metrics)