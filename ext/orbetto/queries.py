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

def get_detailed_thread_state_perfetto():

    query = f"""
    DROP VIEW IF EXISTS workqueue_slices;
    CREATE VIEW workqueue_slices AS
    SELECT
        slice.ts as ts,
        slice.dur as dur,
        slice.id as slice_id,
        slice.name as slice_name,
        thread.name as thread_name,
        thread.utid as utid
    FROM slice
    JOIN thread_track ON thread_track.id = slice.track_id
    JOIN thread USING (utid)
    WHERE thread.tid < 10000;

    DROP TABLE IF EXISTS slice_thread_state_breakdown;
    CREATE VIRTUAL TABLE slice_thread_state_breakdown
    USING SPAN_LEFT_JOIN(
        workqueue_slices PARTITIONED utid,
        thread_state PARTITIONED utid
    );

    SELECT
        thread_name,
        slice_name,
        slice_id,
        SUM(CASE WHEN state = 'Running' THEN dur ELSE 0 END) as running_interval,
        SUM(CASE WHEN state = 'R' THEN dur ELSE 0 END) as runnable_interval,
        SUM(CASE WHEN state = 'S' THEN dur ELSE 0 END) as sleeping_interval
    FROM slice_thread_state_breakdown
    GROUP BY slice_id;
    """
    return tp.query(query).as_pandas_dataframe()

def get_detailed_thread_state():

    running_slices_query = f"""
    DROP VIEW IF EXISTS running_thread;
    CREATE VIEW running_thread AS
    SELECT
        thread.name as thread_name,
        thread_state.id as thread_state_id,
        thread_state.ts as thread_start_ts,
        thread_state.ts + thread_state.dur as thread_end_ts,
        thread.utid as utid
    FROM thread_state
    JOIN thread USING (utid)
    WHERE thread_state.state = 'Running' and thread.tid < 10000 and thread_state.dur > 0;

    DROP VIEW IF EXISTS workqueue_slices;
    CREATE VIEW workqueue_slices AS
    SELECT
        slice.ts as slice_start_ts,
        slice.ts + slice.dur as slice_end_ts,
        slice.id as slice_id,
        slice.name as slice_name,
        thread.utid as utid
    FROM slice
    JOIN thread_track ON thread_track.id = slice.track_id
    JOIN thread USING (utid)
    WHERE thread.tid < 10000;

    DROP VIEW IF EXISTS paired_running;
    CREATE VIEW paired_running AS
    SELECT
        running_thread.thread_name as thread_name,
        running_thread.thread_start_ts as thread_start_ts,
        running_thread.thread_end_ts as thread_end_ts,
        running_thread.thread_state_id as thread_state_id,
        running_thread.utid as utid,
        workqueue_slices.slice_start_ts as slice_start_ts,
        workqueue_slices.slice_end_ts as slice_end_ts,
        workqueue_slices.slice_id as slice_id,
        workqueue_slices.slice_name as slice_name,
        IIF(thread_start_ts>slice_start_ts,thread_start_ts,slice_start_ts) as start_ts,
        IIF(thread_end_ts>slice_end_ts,slice_end_ts,thread_end_ts) as end_ts
    FROM running_thread
    INNER JOIN workqueue_slices
    ON running_thread.utid = workqueue_slices.utid
    AND thread_end_ts > slice_start_ts 
    AND thread_start_ts < slice_end_ts;

    DROP VIEW IF EXISTS running_status;
    CREATE VIEW running_status AS
    SELECT
        slice_id,
        slice_name,
        thread_name,
        thread_state_id,
        thread_start_ts,
        end_ts - start_ts as running_interval,
        utid
    FROM paired_running
    WHERE thread_end_ts > slice_start_ts AND thread_start_ts < slice_end_ts;

    DROP VIEW IF EXISTS running_slices;
    CREATE VIEW running_slices AS
    SELECT
        slice_id,
        slice_name,
        thread_name,
        SUM(running_interval) as running_interval
    FROM running_status
    WHERE running_interval > 0
    GROUP BY slice_id;
    """

    sleeping_slices_query = f"""
    DROP VIEW IF EXISTS sleeping_thread;
    CREATE VIEW sleeping_thread AS
    SELECT
        thread.name as thread_name,
        thread_state.id as thread_state_id,
        thread_state.ts as thread_start_ts,
        thread_state.ts + thread_state.dur as thread_end_ts,
        thread.utid as utid
    FROM thread_state
    JOIN thread USING (utid)
    WHERE thread_state.state = 'S' and thread.tid < 10000 and thread_state.dur > 0;
    
    DROP VIEW IF EXISTS paired_sleeping;
    CREATE VIEW paired_sleeping AS
    SELECT
        sleeping_thread.thread_name as thread_name,
        sleeping_thread.thread_start_ts as thread_start_ts,
        sleeping_thread.thread_end_ts as thread_end_ts,
        sleeping_thread.thread_state_id as thread_state_id,
        sleeping_thread.utid as utid,
        workqueue_slices.slice_start_ts as slice_start_ts,
        workqueue_slices.slice_end_ts as slice_end_ts,
        workqueue_slices.slice_id as slice_id,
        workqueue_slices.slice_name as slice_name,
        IIF(thread_start_ts>slice_start_ts,thread_start_ts,slice_start_ts) as start_ts,
        IIF(thread_end_ts>slice_end_ts,slice_end_ts,thread_end_ts) as end_ts
    FROM sleeping_thread
    INNER JOIN workqueue_slices
    ON sleeping_thread.utid = workqueue_slices.utid AND ABS(thread_end_ts - slice_start_ts) < 1000000;

    DROP VIEW IF EXISTS sleeping_status;
    CREATE VIEW sleeping_status AS
    SELECT
        thread_name,
        slice_id,
        slice_name,
        thread_state_id,
        thread_start_ts,
        end_ts - start_ts as sleeping_interval,
        utid
    FROM paired_sleeping
    WHERE thread_end_ts > slice_start_ts AND thread_start_ts < slice_end_ts;

    DROP VIEW IF EXISTS sleeping_slices;
    CREATE VIEW sleeping_slices AS
    SELECT
        thread_name,
        slice_id,
        slice_name,
        SUM(sleeping_interval) as sleeping_interval
    FROM sleeping_status
    WHERE sleeping_interval > 0
    GROUP BY slice_id;
    """

    runnable_slices_query= f"""

    DROP VIEW IF EXISTS runnable_thread;
    CREATE VIEW runnable_thread AS
    SELECT
        thread_state.id as thread_state_id,
        thread_state.dur as dur,
        thread_state.ts + thread_state.dur as end_ts,
        thread.name as thread_name,
        thread.utid as utid
    FROM thread_state
    JOIN thread USING (utid)
    WHERE thread_state.state = 'R' and thread.tid < 10000 and thread_state.dur > 0;

    DROP VIEW IF EXISTS linked_running_slices;
    CREATE VIEW linked_running_slices AS
    SELECT
        slice_id,
        slice_name,
        MIN(thread_start_ts) as thread_start_ts,
        utid
    FROM running_status
    GROUP BY slice_id;

    DROP VIEW IF EXISTS cross_join;
    CREATE VIEW cross_join AS
    SELECT
        runnable_thread.thread_name as thread_name,
        runnable_thread.thread_state_id as thread_state_id,
        runnable_thread.dur as thread_dur,
        linked_running_slices.slice_id as slice_id,
        linked_running_slices.slice_name as slice_name
    FROM runnable_thread
    INNER JOIN linked_running_slices
    ON runnable_thread.utid = linked_running_slices.utid AND linked_running_slices.thread_start_ts - runnable_thread.end_ts = 0;

    DROP VIEW IF EXISTS runnable_slices;
    CREATE VIEW runnable_slices AS
    SELECT
        thread_state_id,
        thread_name,
        SUM(thread_dur) as runnable_interval,
        slice_name,
        slice_id
    FROM cross_join
    GROUP BY slice_id;
    """

    join_query = f"""
    
    DROP VIEW IF EXISTS join_all;
    CREATE VIEW join_all AS
    SELECT
        COALESCE(runnable_slices.thread_name,running_slices.thread_name,sleeping_slices.thread_name) as thread_name,
        COALESCE(runnable_slices.slice_id,running_slices.slice_id,sleeping_slices.slice_id) as slice_id,
        COALESCE(runnable_slices.slice_name,running_slices.slice_name,sleeping_slices.slice_name) as slice_name,
        runnable_slices.runnable_interval as runnable_interval,
        running_slices.running_interval as running_interval,
        sleeping_slices.sleeping_interval as sleeping_interval
    FROM runnable_slices
    FULL OUTER JOIN running_slices ON runnable_slices.slice_id = running_slices.slice_id
    FULL OUTER JOIN sleeping_slices ON COALESCE(runnable_slices.slice_id,running_slices.slice_id) = sleeping_slices.slice_id;

    SELECT *
    FROM join_all;
    """

    debug_select_query = f"""
    SELECT *
    FROM running_slices
    """

    query = f"""
    {running_slices_query}
    {debug_select_query}
    """

    # {runnable_slices_query}
    # {sleeping_slices_query}
    # {join_query}
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