import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import math as m
from dash import Dash, dcc, html, callback, Output, Input
import plotly.figure_factory as ff
from plotly.subplots import make_subplots
from queries import *

app = Dash(__name__)

widgets = []
active_threads = None
data = {}
hist_data = {}
df_thread_waiting_time_aggregated = None
df_thread_running_time_aggregated = None
df_thread_waiting_time = None
df_thread_running_time = None

def _find_outliers(thread_intervals,thread_ids):
    outlier_id = []
    for function_intervals,ids in zip(thread_intervals,thread_ids):
        # get mean
        mean = np.mean(function_intervals)
        # get std
        std = np.std(function_intervals)
        # get outlier indexes
        idx = np.where(np.abs(function_intervals - mean) > 3 * std)[0]
        # get ids of outliers
        outlier_id.extend(ids[idx].tolist())
    if len(outlier_id) > 0:
        return 'Outliers with Slice IDs: ' + ', '.join(map(lambda x:str(int(x)), outlier_id))
    else:
        return "No outliers found."

def _add_button_for_norm_switch(fig):
    # Create and add button
    fig.update_layout(
        updatemenus=[
            dict(
                buttons=list([
                    dict(label="Percentage",
                        method="update",
                        args=[{'histnorm': 'percent'}]
                    ),
                    dict(label="Count",
                        method="update",
                        args=[{'histnorm': 'count'}]
                    ),
                ]),
                direction="down",
                pad={"r": 10, "t": 10},
                showactive=True,
                x=0,
                xanchor="left",
                y=1.2,
                yanchor="top"
            ),
        ]
    )

def _add_slider_for_bin_size(fig,arr,title,unit):
    # Create and add slider
    num_steps = 100
    min_value = min(arr)
    max_value = max(arr)
    diff = max_value - min_value
    steps = []
    for i in range(num_steps):
        bin_size = diff * ((i+1)/100)**2
        step = dict(
            method="update",
            args=[{'xbins.size': bin_size},{'xbins.start': 0}],  # layout attribute
            label = f"{bin_size:.2f} {unit}"
        )
        # step["args"][0]["visible"][i] = True  # Toggle i'th trace to "visible"
        steps.append(step)

    sliders = [dict(
        active=10,
        currentvalue={"prefix": f"{title} "},
        steps=steps
    )]

    fig.update_layout(
        sliders=sliders
    )

def _add_dropdown_menu(fig):
    # Add dropdown
    fig.update_layout(
        updatemenus=[
            dict(
                buttons=list([
                    dict(label="Count",
                        method="update",
                        args=[{"visible": [True,False]},{'yaxis': {'title': 'Appearence'}}]
                    ),
                    dict(label="Percentage",
                        method="update",
                        args=[{"visible": [False, True]},{'yaxis': {'title': 'CPU Share in Thread (%)'}}]
                    ),
                ]),
                direction="down",
                pad={"r": 10, "t": 10},
                showactive=True,
                x=0,
                xanchor="left",
                y=1.2,
                yanchor="top"
            ),
        ]
    )

def _add_dropdown_menu_bar_chart(fig):
    # Add dropdown
    fig.update_layout(
        updatemenus=[
            dict(
                buttons=list([
                    dict(label="Percentage",
                        method="update",
                        args=[{"visible": [True,False,True,False]},{'yaxis': {'title': 'Total CPU Time (%)'}}]
                    ),
                    dict(label="Time Values",
                        method="update",
                        args=[{"visible": [False,True,False,True]},{'yaxis': {'title': 'Total CPU Time (ns)'}}]
                    ),
                ]),
                direction="down",
                pad={"r": 10, "t": 10},
                showactive=True,
                x=0,
                xanchor="left",
                y=1.2,
                yanchor="top"
            ),
        ]
    )

def bar_chart(df1,df2,x,y,z):
    widgets.append(html.H1("Thread CPU Time Overview",style={'textAlign': 'center'}))
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df1[x], y=df1[y],visible=True,name='Running'))
    fig.add_trace(go.Bar(x=df1[x], y=df1[z],visible=False,name='Running'))
    fig.add_trace(go.Bar(x=df2[x], y=df2[y],visible=True,name='Runnable'))
    fig.add_trace(go.Bar(x=df2[x], y=df2[z],visible=False,name='Runnable'))
    fig.update_layout(
        xaxis_title='Thread Name',
        yaxis_title='Total CPU Time (%)',
        # change angle of xAxis labels
        xaxis_tickangle=45,
        legend_title_text='Thread State'
    )
    _add_dropdown_menu_bar_chart(fig)
    widgets.append(dcc.Graph(figure=fig))

def _add_dropdown_menu_threads(thread_list):
    widgets.append(html.H1("Detailed Function Overview", style={'textAlign': 'center'}))
    widgets.append(html.H4("Select Threads:",style={'margin-bottom': '10px'}))
    dropdown = dcc.Dropdown(id='thread-select',
                          options=thread_list,
                          multi= True,
                          clearable=True,
                          value=[])
    widgets.append(dropdown)

def _add_dropdown_menu_functions():
    widgets.append(html.H4("Select Functions:",style={'margin-bottom': '10px','margin-left': '20px'}))
    dropdown = dcc.Dropdown(id='function-select',
                          options=[],
                          multi= True,
                          clearable=True,
                          value=[],
                          style={'margin-left': '10px'})
    widgets.append(dropdown)


def custom_data_bar_chart(dict):
    global data
    data = dict
    _add_dropdown_menu_threads(list(dict.keys()))
    _add_dropdown_menu_functions()
    widgets.append(dcc.Graph(id='thread-graph',figure={}))
    return

def _add_dropdown_menu_reg_function(function_list):
    widgets.append(html.H4("Select Function:",style={'margin-bottom': '10px'}))
    dropdown = dcc.Dropdown(id='reg-function-select',
                          options=function_list,
                          multi= False,
                          clearable=True,
                          value=[])
    widgets.append(dropdown)
    # include button for reciprocal with increase size
    widgets.append(html.Button('Toggle Reciprocal', id='toggle-reciprocal', n_clicks=0,style={'font-size': '15px','margin-top': '10px'}))

def histogram(dict):
    global hist_data
    hist_data = dict
    widgets.append(html.H1("Regularity Function Overview",style={'textAlign': 'center'}))
    _add_dropdown_menu_reg_function(list(dict.keys()))
    widgets.append(dcc.Graph(id='regularity-graph',figure={}))
    widgets.append(html.H3("PDF",style={'textAlign': 'center','margin-bottom': '10px'}))
    widgets.append(dcc.Graph(id='normal-dist-graph',figure={}))
    widgets.append(html.H5(f"No outliers found.",id='outliers'))

def _add_dropdown_menu_threads_runtime(thread_list):
    widgets.append(html.H4("Select Thread:",style={'margin-bottom': '10px'}))
    dropdown = dcc.Dropdown(id='thread-overview-select',
                          options=thread_list,
                          multi= False,
                          clearable=True,
                          value=[])
    widgets.append(dropdown)

def pie_chart(thread_waiting_time_aggregated,thread_running_time_aggregated,thread_waiting_time,thread_running_time):
    global df_thread_waiting_time_aggregated,df_thread_running_time_aggregated,df_thread_waiting_time,df_thread_running_time
    df_thread_waiting_time_aggregated,df_thread_running_time_aggregated,df_thread_waiting_time,df_thread_running_time = thread_waiting_time_aggregated,thread_running_time_aggregated,thread_waiting_time,thread_running_time
    widgets.append(html.H1("Thread CPU Time Detailed",style={'textAlign': 'center'}))
    _add_dropdown_menu_threads_runtime(df_thread_waiting_time['thread_name'].unique())
    widgets.append(html.Button('Toggle Normalization', id='toggle-normalization', n_clicks=0,style={'font-size': '15px','margin-top': '10px'}))
    widgets.append(dcc.Graph(id='aggr-thread-overview-graph',figure={}))
    widgets.append(dcc.Graph(id='thread-overview-graph-runnable',figure={}))
    widgets.append(dcc.Graph(id='thread-overview-graph-running',figure={}))

def show(debug):
    app.layout = html.Div(widgets)
    app.run_server(debug=debug)

#---------------------- Dash CallBacks ----------------------#
@callback(
    Output('function-select', 'options'),
    Input('thread-select', 'value'),
)
def update_function_callback(threads):
    global active_threads
    active_threads = threads
    options = []
    for t in threads:
        for _,f in data[t].iterrows():
            options.append(f"{f['slice_name']}({t}, {f['count']}, {f['percentage']:.2f}%)")
    return options

@callback(
    Output('thread-graph', 'figure'),
    Input('function-select', 'value'),
)
def update_graph(selected_functions):
    fig = go.Figure()
    if active_threads is None:
        return fig
    for thread in active_threads:
        df = data[thread]
        split = lambda x:x.split("(")[0]
        df = df[df['slice_name'].isin(list(map(split, selected_functions)))]
        fig.add_trace(go.Bar(x=df['slice_name'], y=df['count'],visible=True,name=thread))
        fig.add_trace(go.Bar(x=df['slice_name'], y=df['percentage'],visible=False,name=thread))
    fig.update_layout(
        xaxis_title='Function Name',
        yaxis_title='Appearence',
    )   
    _add_dropdown_menu(fig)
    return fig

@callback(
    Output('regularity-graph', 'figure'),
    Output('normal-dist-graph', 'figure'),
    Output('outliers', 'children'),
    Input('reg-function-select', 'value'),
    Input('toggle-reciprocal', 'n_clicks'),
)
def update_reg_graph(selected_function,reciprocal):
    fig = go.Figure()
    if selected_function is None or len(selected_function) == 0:
        return fig,fig,"No outliers found."
    title = 'Interval [ms]'
    unit = 'ms'
    if reciprocal % 2 == 1:
        title = 'Frequency [kHz]'
        unit = 'kHz'
    np_hist = np.array(hist_data[selected_function])

    threads = np.unique(np_hist[:,2])
    thread_names = []
    thread_ids = []
    thread_intervals = []
    for thread in threads:
        function_intervals = np_hist[np_hist[:,2] == thread][:,0].tolist()
        # remove None values
        function_intervals = [x for x in function_intervals if x is not None]
        function_intervals = np.divide(function_intervals,1e6)
        if reciprocal % 2 == 1:
            function_intervals = np.reciprocal(function_intervals)
        if len(function_intervals) >= 2:
            thread_intervals.append(function_intervals)
            thread_names.append(thread)
            thread_ids.append(np_hist[np_hist[:,2] == thread][:,1])
            fig.add_trace(
                go.Histogram(
                    x=function_intervals,
                    histnorm='percent',
                    name=thread,
                )
            )
    fig.update_layout(
        xaxis_title=title,
    )
    _add_slider_for_bin_size(fig,function_intervals,title,unit)
    _add_button_for_norm_switch(fig)
    normal_dist_fig = ff.create_distplot(thread_intervals,group_labels=thread_names,bin_size=.1)
    normal_dist_fig.update_layout(
        xaxis_title=title,
        yaxis_title='Probability Density',
    )
    outliers = _find_outliers(thread_intervals,thread_ids)
    return fig,normal_dist_fig,outliers

@callback(
    Output('aggr-thread-overview-graph', 'figure'),
    Output('thread-overview-graph-running', 'figure'),
    Output('thread-overview-graph-runnable', 'figure'),
    Input('thread-overview-select', 'value'),
    Input('toggle-normalization', 'n_clicks')
)
def update_thread_overview(selected_thread,n_clicks):
    fig = make_subplots(rows=1, cols=2, specs=[[{'type':'domain'}, {'type':'domain'}]])
    fig2 = go.Figure()
    fig3 = go.Figure()
    if selected_thread is None:
        return fig,fig2,fig3
    df1_aggr = df_thread_waiting_time_aggregated[df_thread_waiting_time_aggregated['thread_name'] == selected_thread]
    df2_aggr = df_thread_running_time_aggregated[df_thread_running_time_aggregated['thread_name'] == selected_thread]
    df1 = df_thread_waiting_time[df_thread_waiting_time['thread_name'] == selected_thread]
    df2 = df_thread_running_time[df_thread_running_time['thread_name'] == selected_thread]
    df1['thread_dur'] = df1['thread_dur']/1e6
    df2['thread_dur'] = df2['thread_dur']/1e6
    if len(df1_aggr) == 0:
        return fig,fig2,fig3
    y1 = 'waiting_time'
    y2 = 'running_time'
    title1 = 'Runnable'
    title2 = 'Running'
    if n_clicks % 2 == 1:
        y1 = 'avg_waiting_time'
        y2 = 'avg_running_time'
        title1 = 'Average Runnable'
        title2 = 'Average Running'
    fig.add_trace(go.Pie(labels=df1_aggr['slice_name'],
                        values=df1_aggr[y1]/1e6,
                        title=title1),
                row = 1, col = 1)
    fig.add_trace(go.Pie(labels=df2_aggr['slice_name'],
                        values=df2_aggr[y2]/1e6,
                        title=title2),
                row = 1, col = 2 )
    fig2 = px.histogram(df1, x='thread_dur',color = 'slice_name', marginal="rug", hover_data=df1.columns, title='Runnable')
    fig2.update_layout(
        xaxis_title='Duration [ms]'
    )
    fig3 = px.histogram(df2, x='thread_dur',color = 'slice_name', marginal="rug", hover_data=df2.columns, title='Running')
    fig3.update_layout(
        xaxis_title='Duration [ms]'
    )
    return fig,fig2,fig3