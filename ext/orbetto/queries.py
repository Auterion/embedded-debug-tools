from perfetto.trace_processor import TraceProcessor

tp = None

def init_trace_processor(trace):
    global tp
    tp = TraceProcessor(trace=trace)

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

def get_thread_waiting_time(state):
    # This query is also working for all threads at the same time
    # However for big tables there is a runtime issue aS INNER JOIN is used
    # which creates a huge table (order of millions of rows)
    query= f"""
    DROP VIEW IF EXISTS runnable_thread;
    CREATE VIEW runnable_thread AS
    SELECT
        thread_state.id as thread_state_id,
        thread_state.dur as dur,
        thread_state.ts as start_ts,
        thread_state.ts + thread_state.dur as end_ts,
        thread.name as thread_name,
        thread.utid as utid
    FROM thread_state
    JOIN thread USING (utid)
    WHERE thread_state.state = '{state}' and thread.tid < 10000 and thread_state.dur > 0;

    DROP VIEW IF EXISTS workqueue_slices;
    CREATE VIEW workqueue_slices AS
    SELECT
        slice.name as slice_name,
        slice.id as slice_id,
        slice.ts as slice_ts,
        thread.utid as utid
    FROM slice
    JOIN thread_track ON thread_track.id = slice.track_id
    JOIN thread USING (utid)
    WHERE thread.tid < 10000;

    DROP VIEW IF EXISTS paired;
    CREATE VIEW paired AS
    SELECT
        runnable_thread.thread_state_id as thread_state_id,
        runnable_thread.dur as thread_dur,
        runnable_thread.thread_name as thread_name,
        workqueue_slices.slice_name as slice_name,
        workqueue_slices.slice_id as slice_id,
        ABS(runnable_thread.end_ts - workqueue_slices.slice_ts) as diff
    FROM runnable_thread
    INNER JOIN workqueue_slices
    ON runnable_thread.utid = workqueue_slices.utid;

    DROP VIEW IF EXISTS ranked;
    CREATE VIEW ranked AS
    SELECT
        thread_dur,
        slice_name,
        slice_id,
        thread_name,
        ROW_NUMBER() OVER (PARTITION BY thread_state_id ORDER BY diff) as rank
    FROM paired;
    
    DROP VIEW IF EXISTS wq_slices;
    CREATE VIEW wq_slices AS
    SELECT
        thread_dur,
        slice_name,
        slice_id,
        thread_name
    FROM ranked
    WHERE rank = 1;

    SELECT 
        slice_name,
        thread_name,
        SUM(thread_dur) as waiting_time,
        AVG(thread_dur) as avg_waiting_time
    FROM wq_slices
    GROUP BY slice_name;
    """
    df_aggr = tp.query(query).as_pandas_dataframe()
    query2=f"""
    SELECT *
    FROM wq_slices;
    """
    return df_aggr,tp.query(query2).as_pandas_dataframe()

def get_thread_running_time(state):
    # This query is also working for all threads at the same time
    # However for big tables there is a runtime issue aS INNER JOIN is used
    # which creates a huge table (order of millions of rows)
    query= f"""
    DROP VIEW IF EXISTS runnable_thread;
    CREATE VIEW runnable_thread AS
    SELECT
        thread_state.id as thread_state_id,
        thread_state.dur as dur,
        thread_state.ts as thread_start_ts,
        thread_state.ts + thread_state.dur as thread_end_ts,
        thread.name as thread_name,
        thread.utid as utid
    FROM thread_state
    JOIN thread USING (utid)
    WHERE thread_state.state = '{state}' and thread.tid < 10000 and thread_state.dur > 0;

    DROP VIEW IF EXISTS workqueue_slices;
    CREATE VIEW workqueue_slices AS
    SELECT
        slice.name as slice_name,
        slice.ts as slice_start_ts,
        slice.ts + slice.dur as slice_end_ts,
        slice.id as slice_id,
        thread.utid as utid
    FROM slice
    JOIN thread_track ON thread_track.id = slice.track_id
    JOIN thread USING (utid)
    WHERE thread.tid < 10000;

    DROP VIEW IF EXISTS paired;
    CREATE VIEW paired AS
    SELECT
        runnable_thread.thread_start_ts as thread_start_ts,
        runnable_thread.thread_end_ts as thread_end_ts,
        workqueue_slices.slice_start_ts as slice_start_ts,
        workqueue_slices.slice_end_ts as slice_end_ts,
        runnable_thread.thread_state_id as thread_state_id,
        runnable_thread.dur as thread_dur,
        runnable_thread.thread_name as thread_name,
        workqueue_slices.slice_name as slice_name,
        workqueue_slices.slice_id as slice_id
    FROM runnable_thread
    INNER JOIN workqueue_slices
    ON runnable_thread.utid = workqueue_slices.utid;

    DROP VIEW IF EXISTS interval;
    CREATE VIEW interval AS
    WITH interval_bounds AS(
        SELECT
            IIF(thread_start_ts>slice_start_ts,thread_start_ts,slice_start_ts) as start_ts,
            IIF(thread_end_ts<slice_end_ts,thread_end_ts,slice_end_ts) as end_ts,
            thread_state_id,
            thread_dur,
            thread_name,
            slice_name,
            slice_id
        FROM paired
    )
    SELECT
        end_ts - start_ts as interval,
        thread_state_id,
        thread_dur,
        thread_name,
        slice_name,
        slice_id
    FROM interval_bounds
    WHERE end_ts - start_ts > 0;

    DROP VIEW IF EXISTS ranked;
    CREATE VIEW ranked AS
    SELECT
        thread_dur,
        slice_name,
        slice_id,
        thread_name,
        ROW_NUMBER() OVER (PARTITION BY thread_state_id ORDER BY interval DESC) as rank
    FROM interval;
    
    DROP VIEW IF EXISTS wq_slices;
    CREATE VIEW wq_slices AS
    SELECT
        thread_dur,
        slice_name,
        slice_id,
        thread_name
    FROM ranked
    WHERE rank = 1;

    SELECT 
        slice_name,
        thread_name,
        SUM(thread_dur) as running_time,
        AVG(thread_dur) as avg_running_time
    FROM wq_slices
    GROUP BY slice_name;
    """
    df_aggr = tp.query(query).as_pandas_dataframe()
    query2=f"""
    SELECT *
    FROM wq_slices;
    """
    return df_aggr,tp.query(query2).as_pandas_dataframe()


def get_function_distribution():
    query = """
    DROP VIEW IF EXISTS slice_with_thread_names;
    CREATE VIEW slice_with_thread_names AS
    SELECT
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
            tid,
            slice_name,
            thread_name,
            ROW_NUMBER() OVER () AS count
        FROM slice_with_thread_names
        GROUP BY slice_name
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