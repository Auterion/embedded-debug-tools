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
active_thread = None
df_functions = None
hist_data = {}
df_detailed_thread_state = None

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
                          multi= False,
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


def custom_data_bar_chart(df):
    global df_functions
    df_functions = df
    _add_dropdown_menu_threads(df['thread_name'].unique())
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

def pie_chart(df):
    global df_detailed_thread_state
    df_detailed_thread_state = df
    widgets.append(html.H1("Thread CPU Time Detailed",style={'textAlign': 'center'}))
    _add_dropdown_menu_threads_runtime(df['thread_name'].unique())
    widgets.append(html.Button('Toggle Normalization', id='toggle-normalization', n_clicks=0,style={'font-size': '15px','margin-top': '10px'}))
    widgets.append(dcc.Graph(id='aggr-thread-overview-graph',figure={}))
    widgets.append(dcc.Graph(id='thread-overview-graph-runnable',figure={}))
    widgets.append(dcc.Graph(id='thread-overview-graph-running',figure={}))
    widgets.append(dcc.Graph(id='thread-overview-graph-sleeping',figure={}))

def show(debug):
    app.layout = html.Div(widgets)
    app.run_server(debug=debug)

#---------------------- Dash CallBacks ----------------------#
@callback(
    Output('function-select', 'options'),
    Input('thread-select', 'value'),
)
def update_function_callback(thread):
    if thread is None:
        return []
    global active_thread
    active_thread = str(thread)
    return df_functions[df_functions['thread_name'] == active_thread]['slice_name'].unique().tolist()

@callback(
    Output('thread-graph', 'figure'),
    Input('function-select', 'value'),
)
def update_graph(selected_functions):
    fig = go.Figure()
    if active_thread is None:
        return fig
    df = df_functions[df_functions['thread_name'] == active_thread]
    for function in selected_functions:
        x_axis = np.sort(np.array(df[df['slice_name'] == function]['tss'].iloc[0].split(',')).astype(int)) / 1e6
        count = df[df['slice_name'] == function]['count'].iloc[0]
        y_axis = [i for i in range(1,count + 1)]
        fig.add_trace(go.Scatter(x=x_axis,
                                 y=y_axis,
                                 mode='lines+markers',
                                 name=function))
    fig.update_layout(
        xaxis_title='Time [ms]',
        yaxis_title='Appearence',
    )
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
    Output('thread-overview-graph-sleeping', 'figure'),
    Input('thread-overview-select', 'value'),
    Input('toggle-normalization', 'n_clicks')
)
def update_thread_overview(selected_thread,n_clicks):
    fig = make_subplots(rows=1, cols=3, specs=[[{'type':'domain'}, {'type':'domain'}, {'type':'domain'}]])
    fig2 = go.Figure()
    fig3 = go.Figure()
    fig4 = go.Figure()
    if selected_thread is None:
        return fig,fig2,fig3,fig4
    df = df_detailed_thread_state[df_detailed_thread_state['thread_name'] == str(selected_thread)]
    if len(df) == 0:
        return fig,fig2,fig3,fig4
    df['runnable_interval'] = df['runnable_interval']/1e6
    df['running_interval'] = df['running_interval']/1e6
    df['sleeping_interval'] = df['sleeping_interval']/1e6
    df_aggr = df.groupby('slice_name').agg({'runnable_interval': 'sum', 'running_interval': 'sum', 'sleeping_interval': 'sum'}).reset_index()
    title1 = 'Runnable'
    title2 = 'Running'
    title3 = 'Sleeping'
    if n_clicks % 2 == 1:
        df_aggr = df.groupby('slice_name').agg({'runnable_interval': 'mean', 'running_interval': 'mean', 'sleeping_interval': 'mean'}).reset_index()
        title1 = 'Average Runnable'
        title2 = 'Average Running'
        title3 = 'Average Sleeping'
    fig.add_trace(go.Pie(labels=df_aggr['slice_name'],
                        values=df_aggr['runnable_interval'],
                        title=title1),
                row = 1, col = 1)
    fig.add_trace(go.Pie(labels=df_aggr['slice_name'],
                        values=df_aggr['running_interval'],
                        title=title2),
                row = 1, col = 2 )
    fig.add_trace(go.Pie(labels=df_aggr['slice_name'],
                        values=df_aggr['sleeping_interval'],
                        title=title3),
                row = 1, col = 3 )
    fig2 = px.histogram(df, x='runnable_interval',color = 'slice_name', marginal="rug", hover_data=['slice_id','slice_name'], title='Runnable')
    fig2.update_layout(
        xaxis_title='Duration [ms]'
    )
    fig3 = px.histogram(df, x='running_interval',color = 'slice_name', marginal="rug", hover_data=['slice_id','slice_name'], title='Running')
    fig3.update_layout(
        xaxis_title='Duration [ms]'
    )
    fig4 = px.histogram(df, x='sleeping_interval',color = 'slice_name', marginal="rug", hover_data=['slice_id','slice_name'], title='Sleeping')
    fig4.update_layout(
        xaxis_title='Duration [ms]'
    )
    return fig,fig2,fig3,fig4