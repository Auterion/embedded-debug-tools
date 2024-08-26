from perfetto.trace_processor import TraceProcessor

tp = None
tp2 = None

def init_trace_processor(trace):
    global tp
    tp = TraceProcessor(trace=trace)
def init_trace_processor2(trace):
    global tp2
    tp2 = TraceProcessor(trace=trace)

def display_all_available_tables():
    # Display all the available columns in the trace
    return tp.query("SELECT name FROM sqlite_master WHERE type='table';").as_pandas_dataframe()

def get_all_cpu_time(state):
    query= f"""
    DROP VIEW IF EXISTS cpu_time;
    CREATE VIEW cpu_time AS
    SELECT
        dur,
        thread.name as thread_name
    FROM thread_state
    JOIN thread USING (utid)
    WHERE state = '{state}';

    SELECT *
    FROM (
        SELECT 
            SUM(dur) AS cpu_time,
            thread_name
        FROM cpu_time
        GROUP BY thread_name
    ) AS subquery
    ORDER BY cpu_time DESC;
    """
    return tp.query(query).as_pandas_dataframe()


def get_function_distribution():
    query = """
    DROP VIEW IF EXISTS slice_with_thread_names;
    CREATE VIEW slice_with_thread_names AS
    SELECT
        ts,
        dur,
        tid,
        slice.name as slice_name,
        slice.id as slice_id,utid,
        thread.name as thread_name
    FROM slice
    JOIN thread_track ON thread_track.id = slice.track_id
    JOIN thread USING (utid);

    SELECT *
    FROM (
        SELECT 
            SUM(dur) AS cpu_time,
            GROUP_CONCAT(DISTINCT ts) AS tss,
            tid,
            slice_name,
            thread_name,
            COUNT(*) AS count
        FROM slice_with_thread_names
        GROUP BY slice_name, tid
    ) AS subquery
    WHERE tid > 100000
    ORDER BY cpu_time DESC;
    """
    return tp.query(query).as_pandas_dataframe()

def get_function_intervals():
    query = """
    DROP VIEW IF EXISTS slice_with_thread_names;
    CREATE VIEW slice_with_thread_names AS
    SELECT
        ts,
        dur,
        tid,
        slice.name as slice_name,
        slice.id as slice_id,utid,
        thread.name as thread_name
    FROM slice
    JOIN thread_track ON thread_track.id = slice.track_id
    JOIN thread USING (utid);

    SELECT *
    FROM(
        SELECT
            ts,
            dur,
            LEAD(ts) OVER (PARTITION BY slice_name ORDER BY ts) AS next_ts,
            LEAD(ts) OVER (PARTITION BY slice_name ORDER BY ts) - (ts + dur) AS interval,
            slice_name,
            LEAD(slice_id) OVER (PARTITION BY slice_name ORDER BY ts) AS next_slice_id,
            thread_name
        FROM (
            SELECT
                ts - 35696370 AS ts,
                dur,
                tid,
                slice_name,
                slice_id,
                thread_name
            FROM slice_with_thread_names
            ORDER BY ts
        ) AS subquery1
        WHERE tid > 100000
        ORDER BY slice_name, ts
    )AS subquery2;
    """
    return tp.query(query).as_pandas_dataframe()

heap_query ="""
    DROP VIEW IF EXISTS mallocs;
    CREATE VIEW mallocs AS
    SELECT
        slice.ts,
        slice.id as slice_id,
        slice.name as slice_name,
        thread.name as thread_name
    FROM slice
    JOIN thread_track ON thread_track.id = slice.track_id
    JOIN thread USING (utid)
    WHERE (slice.name LIKE '%malloc%' AND slice.name LIKE '%[%') OR (slice.name LIKE '%free%' AND slice.name LIKE '%<-%');

    SELECT *
    FROM mallocs
    ORDER BY ts;
    """

def get_heap_profile():
    return tp.query(heap_query).as_pandas_dataframe()

def get_heap_profile2():
    return tp2.query(heap_query).as_pandas_dataframe()