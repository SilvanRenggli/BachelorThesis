# Run this app with `python app.py` and
# visit http://127.0.0.1:8050/ in your web browser.

import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import re
from dash.dependencies import Input, Output, State

import os
from os import mkdir
from os import system
from os import listdir
from os.path import isfile, join

from functools import reduce

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.SLATE], suppress_callback_exceptions=True)


path = "./dash-log-files/" 
scratchPath = "./scratch/"

client_data = {}
eventLog_data = {}
live_client_data = {}
app_state = { "loading" : False, "simFinished" : True, "realTimeFile" : "", "eventSchedule" : [], "clients": [], "nrClients": 0}
extract_unit = { 
                "bl" : {"index": "Time_Now", "value": "Buffer_Level", "resample": True, "timeUnit": 'seconds', "y_axis": "BufferLevel(seconds)" ,"title": "Buffer Level", "line_shape": 'hv' },
                "tp" : {"index": "Time_Now", "value": "Bytes_Received", "resample": True, "timeUnit": 'seconds', "y_axis": "Kb","title": "Throughput", "line_shape": 'linear'},
                "eff" : {"index": "Time_Now", "value": "Bytes_Received", "resample": True, "timeUnit": 'seconds', "y_axis": "Capacity used","title": "Efficiency", "line_shape": 'linear'},
                "bul" : {"index": "Time_Now", "value": "Buffer_Underrun", "resample": True, "timeUnit": 'seconds', "y_axis": "Buffer Underrun" ,"title": "Buffer Underrun", "line_shape": 'hv'},
                "segSize" : {"index": "Download_Request_Sent", "value": "Segment_Size", "resample": True, "timeUnit": 'seconds', "y_axis": "Size (Bit)","title": "Segment Size", "line_shape": 'hv'},
                "qualLevel" : {"index": "Time_Now", "value": "Rep_Level", "resample": True, "timeUnit": 'seconds', "y_axis": "Quality Level","title": "Quality Level", "line_shape": 'hv'},
                }

live_extract_unit = { 
                "bl" : {"index": "Time_Now", "value": "Buffer_Level", "resample": False, "timeUnit": 'nanoseconds', "y_axis": "BufferLevel(seconds)" ,"title": "Buffer Level", "line_shape": 'hv' },
                "tp" : {"index": "Time_Now", "value": "Bytes_Received", "resample": True, "timeUnit": 'seconds', "y_axis": "Kb","title": "Throughput", "line_shape": 'linear'},
                "eff" : {"index": "Time_Now", "value": "Bytes_Received", "resample": True, "timeUnit": 'seconds', "y_axis": "Capacity used","title": "Efficiency", "line_shape": 'linear'},
                "bul" : {"index": "Time_Now", "value": "Buffer_Underrun", "resample": False, "timeUnit": 'nanoseconds', "y_axis": "Buffer Underrun" ,"title": "Buffer Underrun", "line_shape": 'hv'},
                "segSize" : {"index": "Download_Request_Sent", "value": "Segment_Size", "resample": False, "timeUnit": 'nanoseconds', "y_axis": "Size (Bit)","title": "Segment Size", "line_shape": 'hv'},
                "qualLevel" : {"index": "Time_Now", "value": "Rep_Level", "resample": False, "timeUnit": 'nanoseconds', "y_axis": "Quality Level","title": "Quality Level", "line_shape": 'hv'},
                }
aggregated_units = { "avgTp": {'unit': 'tp', 'aggregation': 'avg'},
                    "avgBl": {'unit': 'bl', 'aggregation': 'avg'},
                    "avgSegSize": {'unit': 'segSize', 'aggregation': 'avg'},
                    "avgQualLevel": {'unit': 'qualLevel', 'aggregation': 'avg'},
                    "totalEff": {'unit': 'eff', 'aggregation': 'stacked_sum'} }
congestionProtocols = [{"label": 'TcpNewReno', "value": 'ns3::TcpNewReno'}, {"label": 'TcpWestwood', "value": 'ns3::TcpWestwood'}, {"label": 'TcpVegas', "value": 'ns3::TcpVegas'}, {"label": 'TcpVeno', "value": 'ns3::TcpVeno'}, {"label": 'TcpBic', "value": 'ns3::TcpBic'}] #{"label": 'TcpCubic', "value": 'ns3::TcpCubic'}
abrAlgorithms = ["panda", "tobasco", "festive"]


#returns the id of a simulation file
def get_sim_id(file):
    match = re.search(r"^sim\d+", file)
    if match:
        return match.group()
    else:
        return -1

#returns the nr of a client
def get_client_nr(client):
    match = re.search(r"^sim\d+_cl(\d+)", client)
    if match:
        return int(match.group(1))
    else:
        return -1

def cmp_clients(c1, c2):
    c1nr = get_client_nr(c1)
    c2nr = get_client_nr(c2)
    if c1nr > c2nr:
        return 1
    elif c1nr == c2nr:
        return 0
    else:
        return -1 

#returns all client output files that belong to this simulation
def get_outputs(path, simId):
    outputs = []
    for f in list( listdir( path )):
        if (str(f).startswith(simId) and not str(f).find('cl') == -1 and str(f).endswith("output.txt")):
            outputs.append(str(f))
    outputs.sort(cmp_clients)
    return outputs

#returns all available scripts
def get_scripts():
    scripts = []
    for f in list( listdir( scratchPath )):
        if not str(f) == "scratch-simulator.cc" and str(f).endswith(".cc"):
            scripts.append(str(f)[:-3])
    return scripts

app.layout = html.Div([
    dbc.Tabs(
        [
            dbc.Tab(label='New Simulation', tab_id='new'),
            dbc.Tab(label='Simulation Results', tab_id='results'),
            dbc.Tab(label='Live Results', tab_id='live'),
        ],
        id="tabs",
        active_tab="new"
    ),

    html.Div(id='tab-content'),

    #hidden intermediate values
    html.Div(id='live_data', style={'display': 'none'})
])

#load all dataframes from this simulation and store them in a dictionary
def load_data(path, simId):
    client_data.clear()
    #get data for all clients
    for f in list( listdir( path )):
        if (str(f).startswith(simId) and not str(f).find('cl') == -1 and str(f).endswith("output.txt")):
            # read dataframe for client if it is the first time accessing this data
            if not str(f) in client_data:
                cdata = pd.read_csv(path + "/" + str(f), sep = ";")
                client_dict = {}
                client_dict["df"] = cdata
                client_data[str(f)] = client_dict

def loadEventLog(path, simId):
    df = pd.read_csv(path + "/" + simId + "_event_log.txt" , sep = ";")
    eventLog_data["BottleneckRate"] = df[df["Event"] == "BottleneckRate"] 

def load_unit(unit):
    for c in client_data:
        client_dict = client_data[c]
        if not unit in client_dict:
            df = client_dict["df"].copy()
            df = df[[ extract_unit[unit]["index"], extract_unit[unit]["value"] ]].dropna()
            df[extract_unit[unit]["index"]] = pd.to_timedelta(df[extract_unit[unit]["index"]], unit = extract_unit[unit]["timeUnit"])
            if extract_unit[unit]["resample"]:
                if unit == "tp":
                    df = df.resample('1S', on= extract_unit[unit]["index"]).sum()
                    df[extract_unit[unit]["value"]] = df[extract_unit[unit]["value"]] * 8 * 0.001
                elif unit == "bul":
                    df = df.resample('1S', on= extract_unit[unit]["index"]).min()
                    df = df.ffill()
                else:
                    df = df.resample('1S', on= extract_unit[unit]["index"]).mean()
                    df = df.ffill()
                df.index = df.index.seconds
            client_dict[unit] = df
            client_data[c] = client_dict




#update the dataframes from the currently running simulation    
def new_load_live_data(path, simId, unit):
    app_state["loading"] = True
    #get data for all clients
    for f in list( listdir( path )):
        if (str(f).startswith(simId) and not str(f).find('cl') == -1 and str(f).endswith("output.txt")):
            #read new data logs
            if not str(f) in live_client_data:
                cdata = pd.read_csv(path + "/" + str(f), sep = ";")
                client_dict = {}
                client_dict["lastRead"] = len(cdata.index)
                client_dict["df"] = cdata
                live_client_data[str(f)] = client_dict
            else:
                client_dict = live_client_data[str(f)]
                cdata = pd.read_csv(path + "/" + str(f), sep = ";", skiprows=range(1, client_dict["lastRead"]))
                client_dict["df"] = client_dict["df"].append(cdata)
                client_dict["lastRead"] = client_dict["lastRead"] + len(cdata.index)

            if not unit + "_lastRead" in client_dict:
                df = client_dict["df"].copy()
                client_dict[unit +"_lastRead"] = len(df)
                df = df[[ live_extract_unit[unit]["index"], live_extract_unit[unit]["value"] ]].dropna()
                df[live_extract_unit[unit]["index"]] = pd.to_timedelta(df[live_extract_unit[unit]["index"]], unit = live_extract_unit[unit]["timeUnit"])
                if  live_extract_unit[unit]["resample"]:
                    df = df.resample('1S', on= live_extract_unit[unit]["index"]).sum() 
                    if not df.empty:
                        df.index = df.index.seconds
                        df[live_extract_unit[unit]["value"]] = df[live_extract_unit[unit]["value"]] * 8 * 0.001
                client_dict[unit] = df
                
            else:
                lastRead = client_dict[unit +"_lastRead"]
                df = client_dict["df"][lastRead:].copy()
                df = df[[ live_extract_unit[unit]["index"], live_extract_unit[unit]["value"] ]].dropna()
                df[live_extract_unit[unit]["index"]] = pd.to_timedelta(df[live_extract_unit[unit]["index"]], unit = live_extract_unit[unit]["timeUnit"])
                if live_extract_unit[unit]["resample"]:
                    df = df.resample('1S', on= live_extract_unit[unit]["index"]).sum()
                    if not df.empty:
                        df.index = df.index.seconds
                        df[live_extract_unit[unit]["value"]] = df[live_extract_unit[unit]["value"]] * 8 * 0.001
                new_df = client_dict[unit].append(df)
                client_dict[unit] = new_df
                client_dict[unit +"_lastRead"] = len(client_dict["df"].index)
            
            
    app_state["loading"] = False

                    
                    
        

#get the average of all dataframes
def get_average(dfs):
    avg = reduce(lambda a, b: a.add(b, fill_value=0), dfs)
    avg = avg.div(len(dfs))
    return avg

#get the sum of all dataframes
def get_sum(dfs):
    res = reduce(lambda a, b: a.add(b, fill_value=0), dfs)
    return res

#sum up all values of the first column of a dataframe
def get_col_sum(df, col):
    return df[col].sum()

#sum up all values of the first column of a dataframe
def get_col_avg(df, col):
    return df[col].mean()

#count the changes in the first column of a dataframe
def count_changes(df):
    changes = (df.diff(axis=0) != 0).sum(axis=0)
    return changes[0] - 1 #Don't count first change in quality

def get_algo(client):
    result = re.search('cl\d+_(.*)_output.txt', client)
    return result.group(1)

def get_efficiency():
    load_unit('tp')
    for c in client_data:
        client_dict = client_data[c]
        if not "eff" in client_dict:
            bottleneck_rates = eventLog_data["BottleneckRate"]
            efficiency = client_dict["tp"].copy()
            for i in range(len(bottleneck_rates)):
                current_rate = bottleneck_rates.iloc[i]["Value"]
                if i == len(bottleneck_rates) -1:
                    eff = efficiency.loc[ efficiency.index >= bottleneck_rates.iloc[i]["Time_Now"], "Bytes_Received" ].div(current_rate)
                    efficiency.loc[ efficiency.index >= bottleneck_rates.iloc[i]["Time_Now"], "Bytes_Received" ] = eff
                else:
                    eff = efficiency.loc[ (efficiency.index >= bottleneck_rates.iloc[i]["Time_Now"]) & (efficiency.index < bottleneck_rates.iloc[i + 1]["Time_Now"]), "Bytes_Received" ].div(current_rate)
                    efficiency.loc[ (efficiency.index >= bottleneck_rates.iloc[i]["Time_Now"]) & (efficiency.index < bottleneck_rates.iloc[i + 1]["Time_Now"]), "Bytes_Received" ] = eff
            client_dict["eff"] = efficiency
            client_data[c] = client_dict
    
def refresh_simulation_results():

    #Components for result visualisation:
    selectSimName = dbc.Col(
                        dbc.FormGroup([
                            dbc.Label("Simulation", html_for="simName"),
                            dbc.Select(
                                id="simName",
                                options=[
                                    {"label": f, "value": f} for f in sorted(list(listdir(path)))
                                ],
                                value = sorted(list(listdir(path)))[0] if listdir(path) else "no simulations found"
                            )
                        ]),
                        width = {'size': 2, 'offset': 1}
                    )

    selectNrClients = dbc.Col(
                        dbc.FormGroup([
                            dbc.Label("#Clients", html_for="nrClients"),
                            dbc.Select(
                                id ='nrClients',
                                options=[
                                ],
                                value='',
                            )   
                        ]),
                        width = 2
                    )

    selectSimId = dbc.Col(
                        dbc.FormGroup([
                            dbc.Label("Simulation ID", html_for="simId"),
                            dbc.Select(
                                id ='simId',
                                options=[
                                ],
                                value='',
                            )   
                        ]),
                        width = 2
                    )

    selectOutputs = dbc.Col(
                        dbc.Card(
                            [
                                dbc.CardHeader(
                                    dbc.Button("Manage Clients", color="secondary", id="manageClients")
                                ),
                                dbc.Collapse(
                                    dcc.Dropdown(
                                        id='selectOutputs',
                                        options=[],
                                        value=[],
                                        multi = True
                                    ),   
                                    id="manageCollapse"   
                                ),
                            ]
                        ),
                        width = {'size': 10, 'offset': 1}
                    )
    
    results_content = html.Div([
        dbc.Row([
            selectSimName,
            selectNrClients,
            selectSimId,
            dbc.Col(dbc.Button("Load Data", color="primary", id="loadButton", type= 'submit'), align='center')
        ]),
        dbc.Row([
            selectOutputs
        ]),
        dbc.Row([
            selectGraphs
        ]),
        html.Div([], id="graphs")
    ])

    return results_content

def trim_client(client):
    result = re.search('sim\d+_(.*)_output.txt', client)
    return result.group(1)

def load_qualChanges():
    for c in client_data:
        client_dict = client_data[c]
        if not 'qualChanges' in client_dict:
            client_dict['qualChanges'] = count_changes(client_dict['qualLevel'])

def display_qualChanges(clients, aggregation):
    load_unit('qualLevel')
    load_qualChanges()
    df = pd.DataFrame(columns=['Client', 'Quality_Changes', 'Algorithm'])
    rows = []
    for client in clients:
        rows.append([trim_client(client), client_data[client]['qualChanges'], get_algo(client)])
    df2 = pd.DataFrame(rows, columns=['Client', 'Quality_Changes', 'Algorithm'], dtype=float)
    df = df.append(df2)
    Fig = go.Figure()
    if not aggregation:
        Fig.add_bar(x=df['Client'], y=df['Quality_Changes'])
        Fig.update_layout(xaxis_title="Client",
            yaxis_title="Total Quality Changes",
            title="Quality Changes",
            template="plotly_dark",
            plot_bgcolor='#272B30',
            paper_bgcolor='#272B30',
            height=700)
    else:
        Fig.add_box(x=df['Algorithm'], y=df['Quality_Changes'], width = 0.2)
        Fig.update_layout(xaxis_title="Algorithm",
            yaxis_title="Total Quality Changes",
            title="Quality Changes",
            template="plotly_dark",
            plot_bgcolor='#272B30',
            paper_bgcolor='#272B30',
            height=700)

    Graph = dbc.Col(dcc.Graph(id="graph", figure= Fig))
    return dbc.Row(Graph)

def load_bufferUnderruns():
    for c in client_data:
        client_dict = client_data[c]
        if not 'bufferUnderruns' in client_dict:
            client_dict['bufferUnderruns'] = get_col_sum(client_dict['bul'], 'Buffer_Underrun')

def display_Underruns(clients, aggregation):
    load_unit('bul')
    load_bufferUnderruns()
    df = pd.DataFrame(columns=['Client', 'Underruns', 'Algorithm'])
    rows = []
    for client in clients:
        rows.append([trim_client(client), client_data[client]['bufferUnderruns'], get_algo(client)])
    df2 = pd.DataFrame(rows, columns=['Client', 'Underruns', 'Algorithm'], dtype=float)
    df = df.append(df2)
    Fig = go.Figure()
    if not aggregation:
        Fig.add_bar(x=df['Client'], y=df['Underruns'])
        Fig.update_layout(xaxis_title="Client",
            yaxis_title="Total Underruns (seconds)",
            title="Buffer Underruns",
            template="plotly_dark",
            plot_bgcolor='#272B30',
            paper_bgcolor='#272B30',
            height=700)
    else:
        Fig.add_box(x=df['Algorithm'], y=df['Underruns'], width = 0.2)
        Fig.update_layout(xaxis_title="Algorithm",
            yaxis_title="Mean Total Underruns (seconds)",
            title="Buffer Underruns",
            template="plotly_dark",
            plot_bgcolor='#272B30',
            paper_bgcolor='#272B30',
            height=700)

    Graph = dbc.Col(dcc.Graph(id="graph", figure= Fig))
    return dbc.Row(Graph)

def load_avgQuality():
    for c in client_data:
        client_dict = client_data[c]
        if not 'avgQuality' in client_dict:
            client_dict['avgQuality'] = get_col_avg(client_dict['qualLevel'], 'Rep_Level')

def display_AvgQualLevel(clients, aggregation):
    load_unit('qualLevel')
    load_avgQuality()
    df = pd.DataFrame(columns=['Client', 'Quality', 'Algorithm'])
    rows = []
    for client in clients:
        rows.append([trim_client(client), client_data[client]['avgQuality'], get_algo(client)])
    df2 = pd.DataFrame(rows, columns=['Client', 'Quality', 'Algorithm'], dtype=float)
    df = df.append(df2)
    Fig = go.Figure()
    if not aggregation:
        Fig.add_bar(x=df['Client'], y=df['Quality'])
        Fig.update_layout(xaxis_title="Client",
            yaxis_title="Quality Level",
            title="Average Quality Level",
            template="plotly_dark",
            plot_bgcolor='#272B30',
            paper_bgcolor='#272B30',
            height=700)
    else:
        Fig.add_box(x=df['Algorithm'], y=df['Quality'], width = 0.2)
        Fig.update_layout(xaxis_title="Algorithm",
            yaxis_title="Quality Level",
            title="Average Quality Level",
            template="plotly_dark",
            plot_bgcolor='#272B30',
            paper_bgcolor='#272B30',
            height=700)

    Graph = dbc.Col(dcc.Graph(id="graph", figure= Fig))
    return dbc.Row(Graph)

def load_avgEff():
    for c in client_data:
        client_dict = client_data[c]
        if not 'avgEff' in client_dict:
            client_dict['avgEff'] = get_col_avg(client_dict['eff'], 'Bytes_Received')

def display_AvgEff(clients, aggregation):
    load_unit('eff')
    load_avgEff()
    df = pd.DataFrame(columns=['Client', 'Efficiency', 'Algorithm'])
    rows = []
    for client in clients:
        rows.append([trim_client(client), client_data[client]['avgEff'], get_algo(client)])
    df2 = pd.DataFrame(rows, columns=['Client', 'Efficiency', 'Algorithm'], dtype=float)
    df = df.append(df2)
    Fig = go.Figure()
    if not aggregation:
        Fig.add_bar(x=df['Client'], y=df['Efficiency'])
        Fig.update_layout(xaxis_title="Client",
            yaxis_title="Efficiency",
            title="Average Efficiency",
            template="plotly_dark",
            plot_bgcolor='#272B30',
            paper_bgcolor='#272B30',
            height=700)
    else:
        Fig.add_bar(x=df['Algorithm'], y=df['Efficiency'], width = 0.2)
        Fig.update_layout(xaxis_title="Algorithm",
            yaxis_title="Efficiency",
            title="Average Efficiency",
            template="plotly_dark",
            plot_bgcolor='#272B30',
            paper_bgcolor='#272B30',
            height=700)

    Graph = dbc.Col(dcc.Graph(id="graph", figure= Fig))
    return dbc.Row(Graph)

def display_graph(clients, unit, aggregation):
    Fig = go.Figure()
    load_unit(unit)
    if aggregation == 'all':
        for client in clients:
            df = client_data[str(client)][unit]
            Fig.add_scatter(x=df.index, y=df[extract_unit[unit]["value"]], mode='lines', line_shape=extract_unit[unit]["line_shape"], name=str(client))
        Fig.update_layout(xaxis_title="seconds",
        yaxis_title=extract_unit[unit]["y_axis"],
        title=extract_unit[unit]["title"],
        template="plotly_dark",
        plot_bgcolor='#272B30',
        paper_bgcolor='#272B30',
        height=700)
        Graph = dbc.Col(dcc.Graph(id="graph", figure= Fig))
        return dbc.Row(Graph)
    if aggregation == 'stacked':
        for client in clients:
            df = client_data[str(client)][unit]
            Fig.add_scatter(x=df.index, y=df[extract_unit[unit]["value"]], mode='lines', line_shape=extract_unit[unit]["line_shape"], name=str(client), stackgroup='one')
        Fig.update_layout(xaxis_title="seconds",
        yaxis_title=extract_unit[unit]["y_axis"],
        title=extract_unit[unit]["title"],
        template="plotly_dark",
        plot_bgcolor='#272B30',
        paper_bgcolor='#272B30',
        height=700)
        Graph = dbc.Col(dcc.Graph(id="graph", figure= Fig))
        return dbc.Row(Graph)
    if aggregation == 'avg':
        dfs = []
        abrAlgos = {}
        for client in clients:
            algo = get_algo(client)
            if not algo in abrAlgos:
                abrAlgos[algo] = []
            abrAlgos[algo].append(client_data[str(client)][unit])
            dfs.append(client_data[str(client)][unit])
        avgAll = get_average(dfs)
        Fig.add_scatter(x=avgAll.index, y=avgAll[extract_unit[unit]["value"]], mode='lines' , name="All Clients")
        for key, value in abrAlgos.items():
            avg = get_average(value)
            Fig.add_scatter(x=avg.index, y=avg[extract_unit[unit]["value"]], mode='lines' , name= key)
        Fig.update_layout(xaxis_title="seconds",
        yaxis_title=extract_unit[unit]["y_axis"],
        title= "Average " + extract_unit[unit]["title"],
        template="plotly_dark",
        plot_bgcolor='#272B30',
        paper_bgcolor='#272B30',
        height=700)
        Graph = dbc.Col(dcc.Graph(id="graph", figure=Fig))
        return dbc.Row(Graph)
    if aggregation == 'sum':
        dfs = []
        abrAlgos = {}
        for client in clients:
            algo = get_algo(client)
            if not algo in abrAlgos:
                abrAlgos[algo] = []
            abrAlgos[algo].append(client_data[str(client)][unit])
            dfs.append(client_data[str(client)][unit])
        avgAll = get_sum(dfs)
        Fig.add_scatter(x=avgAll.index, y=avgAll[extract_unit[unit]["value"]], mode='lines' , name="All Clients")
        for key, value in abrAlgos.items():
            avg = get_sum(value)
            Fig.add_scatter(x=avg.index, y=avg[extract_unit[unit]["value"]], mode='lines' , name= key)
        Fig.update_layout(xaxis_title="seconds",
        yaxis_title=extract_unit[unit]["y_axis"],
        title= "Average " + extract_unit[unit]["title"],
        template="plotly_dark",
        plot_bgcolor='#272B30',
        paper_bgcolor='#272B30',
        height=700)
        Graph = dbc.Col(dcc.Graph(id="graph", figure=Fig))
        return dbc.Row(Graph)
    if aggregation == 'stacked_sum':
        dfs = []
        abrAlgos = {}
        for client in clients:
            algo = get_algo(client)
            if not algo in abrAlgos:
                abrAlgos[algo] = []
            abrAlgos[algo].append(client_data[str(client)][unit])
            dfs.append(client_data[str(client)][unit])
        avgAll = get_sum(dfs)
        for key, value in abrAlgos.items():
            avg = get_sum(value)
            Fig.add_scatter(x=avg.index, y=avg[extract_unit[unit]["value"]], mode='lines' , name= key, stackgroup='one')
        Fig.update_layout(xaxis_title="seconds",
        yaxis_title=extract_unit[unit]["y_axis"],
        title= "Average " + extract_unit[unit]["title"],
        template="plotly_dark",
        plot_bgcolor='#272B30',
        paper_bgcolor='#272B30',
        height=700)
        Graph = dbc.Col(dcc.Graph(id="graph", figure=Fig))
        return dbc.Row(Graph)


newName = dbc.Col(
                    dbc.FormGroup([
                        dbc.Label("Simulation Name", html_for="newName"),
                        dbc.Input( 
                            id ='newName',
                            placeholder='Name of simulation',
                            type = "text",
                        )   
                    ]),
                    width = {'size': 2, 'offset': 1}
                )

newId = dbc.Col(
                    dbc.FormGroup([
                        dbc.Label("Simulation ID", html_for="newId"),
                        dbc.Input( 
                            id ='newId',
                            value=0,
                            type = "number", min=0, max=99, step=1
                        )   
                    ]),
                    width = 1
                )

newSimScript = dbc.Col(
                    dbc.FormGroup([
                        dbc.Label("Simulation Script", html_for="simScript"),
                        dbc.Select(
                            id="simScript",
                            options=[
                                {"label": f, "value": f} for f in get_scripts()
                            ],
                            value = get_scripts()[0]
                        )
                    ]),
                    width = {'size': 2}
                )

enableLiveInputs = dbc.Col( 
                    dbc.FormGroup([
                        dbc.Label("Live Inputs"),
                        dbc.Checklist(
                            options=[
                                {"label": "Enabled", "value": 0},
                            ],
                            labelCheckedStyle={"color": "green"},
                            value=[],
                            id="live-inputs",
                            inline=True,
                        )
                    ]),
                    width = 1
)


nrServers = dbc.Col(
                    dbc.FormGroup([
                        dbc.Label("Servers:", html_for="nrServers"),
                         dbc.Input( 
                            id ='nrServers',
                            value=1,
                            type = "number", min=1, max=999, step=1
                        )     
                    ]),
                    width = {'size': 1, 'offset' : 1}
                )

nrClients = dbc.Col(
                    dbc.FormGroup([
                        dbc.Label("Amount:", html_for="nrClients"),
                         dbc.Input( 
                            id ='nrClients',
                            value=1,
                            type = "number", min=1, max=999, step=1
                        )     
                    ]),
                    width = 1, align = 'end'
                )

segmentDuration = dbc.Col(
                    dbc.FormGroup([
                        dbc.Label("Segment Duration (sec):", html_for="segmentDuration"),
                         dbc.Input( 
                            id ='segmentDuration',
                            value=2,
                            type = "number", min=1, max=60, step=1
                        )     
                    ]),
                    width = 1.5
                )
clientAlgo = dbc.Col(
                    dbc.FormGroup([
                        dbc.Label("Algorithm", html_for="clientAlgo"),
                        dbc.Select(
                            id="clientAlgo",
                            options= [{"label": a, "value": a} for a in abrAlgorithms ],
                            value = "panda"
                        )
                    ]),
                    width = 2, align = 'end'
                )

selectTcp = dbc.Col(
                    dbc.FormGroup([
                        dbc.Label("Congestion Protocol", html_for="selectTcp"),
                        dbc.Select(
                            id="selectTcp",
                            options= congestionProtocols,
                            value = "ns3::TcpNewReno"
                        )
                    ]),
                    width = 2
                )

enablePacing = dbc.Col( 
                    dbc.FormGroup([
                        dbc.Label("Packet Pacing"),
                        dbc.Checklist(
                            options=[
                                {"label": "Enabled", "value": 0},
                            ],
                            labelCheckedStyle={"color": "green"},
                            value=[],
                            id="packet-pacing",
                            inline=True,
                        )
                    ]),
                    width = 1
)

rateClients = dbc.Col(
                    dbc.FormGroup([
                        dbc.Label("Datarate for clients (Kbps):", html_for="rateClients"),
                         dbc.Input(
                            id ='rateClients',
                            value=5000,
                            type = "number", min=100, max=1000000, step=1
                        )     
                    ]),
                    width = {'size': 1, 'offset': 1}
                )

delayClients = dbc.Col(
                    dbc.FormGroup([
                        dbc.Label("Delay for clients (ms):", html_for="delayClients"),
                         dbc.Input( 
                            id ='delayClients',
                            value=2,
                            type = "number", min=0, max=3600, step=1
                        )     
                    ]),
                    width = 1
                )

rateBottleneck = dbc.Col(
                    dbc.FormGroup([
                        dbc.Label("Datarate of bottleneck (Kbps):", html_for="rateBottle"),
                         dbc.Input( 
                            id ='rateBottle',
                            value=5000,
                            type = "number", min=1000, max=300000, step=1
                        )     
                    ]),
                    width = 1
                )

delayBottleneck = dbc.Col(
                    dbc.FormGroup([
                        dbc.Label("Delay of bottleneck (ms):", html_for="delayBottle"),
                         dbc.Input( 
                            id ='delayBottle',
                            value=2,
                            type = "number", min=0, max=3600, step=1
                        )     
                    ]),
                    width = 1
                )

videoFile = dbc.Col(
                    dbc.FormGroup([
                        dbc.Label("Video File", html_for="videoFile"),
                        dbc.Select(
                            id="videoFile",
                            options=[
                                {"label": f, "value": f} for f in sorted(list(listdir('./DashVideos')))
                            ],
                            value = sorted(list(listdir('./DashVideos')))[0]
                        )
                    ]),
                    width = 2, align = 'end'
                )

liveEventType = dbc.Col(
                    dbc.FormGroup([
                        dbc.Label("Event Type", html_for="liveEventType"),
                        dbc.Select(
                            id="liveEventType",
                            options=[
                                {"label": "Bottleneck Rate", "value": "BottleneckRate"},
                                {"label": "End Simulation", "value": "EndSimulation"}
                            ],
                            value = "BottleneckRate"
                        )
                    ]),
                    width = {'size': 2, 'offset': 1}, align = 'end'
                )

liveEventRateBottleneck = dbc.Col(
                    dbc.FormGroup([
                        dbc.Label("Datarate of bottleneck (Kbps):", html_for="liveEventRateBottleneck"),
                         dbc.Input( 
                            id ='liveEventRateBottleneck',
                            value=5000,
                            type = "number", min=100, max=100000, step=1
                        )     
                    ]),
                    width = 1
                )

scheduleEventType = dbc.Col(
                    dbc.FormGroup([
                        dbc.Label("Event Type", html_for="scheduleEventType"),
                        dbc.Select(
                            id="scheduleEventType",
                            options=[
                                {"label": "Bottleneck Rate", "value": "BottleneckRate"},
                            ],
                            value = "BottleneckRate"
                        )
                    ]),
                    width = 2, align = 'end'
                )

scheduleEventRateBottleneck = dbc.Col(
                    dbc.FormGroup([
                        dbc.Label("(Kbps):", html_for="scheduleEventRateBottleneck"),
                         dbc.Input( 
                            id ='scheduleEventRateBottleneck',
                            value=5000,
                            type = "number", min=100, max=100000, step=1
                        )     
                    ]),
                    width = 1
                )

scheduleEventTime = dbc.Col(
                    dbc.FormGroup([
                        dbc.Label("seconds:", html_for="scheduleEventTime"),
                         dbc.Input( 
                            id ='scheduleEventTime',
                            value=10,
                            type = "number", min=1, max=3600, step=1
                        )     
                    ]),
                    width = {'size':1, 'offset': 1}
                )

eventSchedule = dbc.Col(
    html.Div([
        dbc.Alert(e, color="info") for e in app_state["eventSchedule"]
    ]), id = 'eventSchedule'
)

setupClients = dbc.Card(
    [
        dbc.CardHeader("Client Setup"),
        dbc.CardBody(
            [
                dbc.Row([
                    nrClients,
                    clientAlgo,
                    videoFile,
                    segmentDuration,
                    dbc.Col(dbc.Button("Add clients", color="primary", id="clientButton", type= 'submit'), align='center')
                ])
            ]
        ),
        dbc.CardFooter(
            dbc.ListGroup(
                [
                    dbc.ListGroupItem("Item 1"),
                    dbc.ListGroupItem("Item 2"),
                    dbc.ListGroupItem("Item 3"),
                ],
                flush=True, id="addedClients"
            )
        )
    ],
)

scheduleEvent = dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                dbc.Button("Schedule Events", color="secondary", id="scheduleEvent")
                            ),
                            dbc.Collapse(
                                html.Div([
                                    dbc.Row([
                                        scheduleEventTime,
                                        scheduleEventType,
                                        scheduleEventRateBottleneck,
                                        dbc.Col(dbc.Button("Schedule Event", color="primary", id="scheduleEventButton", type= 'submit'), align='center')
                                    ]),
                                    dbc.Row([eventSchedule])
                                ]),  
                                id="scheduleCollapse"    
                            ),
                        ]
                    ),
                    width = {'size': 10, 'offset': 1}
                )

selectGraphs = dbc.Col(
    dbc.FormGroup(
        [
            dbc.Label("Display Graphs"),
            dbc.Checklist(
                options=[
                    {"label": "Throughput", "value": "tp"},
                    {"label": "Average Throughput", "value": "avgTp"},
                    {"label": "Buffer Level", "value": "bl"},
                    {"label": "Average Buffer Level", "value": "avgBl"},
                    {"label": "Efficiency", "value": "eff"},
                    {"label": 'Total Efficiency', "value": "totalEff"},
                    {"label": "Buffer Underrun", "value": "bul"},
                    {"label": "Segment Sizes", "value": "segSize"},
                    {"label": "Average Segment Sizes", "value": "avgSegSize"},
                    {"label": "Quality Level", "value": "qualLevel"},
                    {"label": "Average Quality Level", "value": "avgQualLevel"},
                    {"label": "Quality Changes", "value": "qualChanges"},
                    {"label": "Total Buffer Underruns", "value": "bufferUnderruns"},
                    {"label": "Average Playback Quality", "value": "avgQuality"},
                    {"label": 'Average Efficiency', "value": "avgEff"}
                ],
                value=[],
                id="selectedGraphs",
                inline=True,
            ),
        ]
    ), width = {'size': 10, 'offset': 1}
)




newSim_content = html.Div([
        dbc.Row([]),
        dbc.Row([
            newName,
            newId,
            newSimScript,
            enableLiveInputs
        ]),
        dbc.Row([
            rateClients,
            delayClients,
            rateBottleneck,
            delayBottleneck
        ]),
        dbc.Row([
            nrServers,
            selectTcp,
            enablePacing
        ]),
        dbc.Row([
            dbc.Col(
            setupClients,
            width = {'size': 10, 'offset': 1}
            )
        ]),
        dbc.Row([
            scheduleEvent
        ]),
        dbc.Row([
            dbc.Col(
                dbc.Button("Start Simulation", color="primary", id="newSimButton", type= 'submit'),
                width = {'size': 10, 'offset': 1})
        ]),
    ])

liveRes_content = html.Div([
        dbc.Tabs(
        [
            dbc.Tab(label='Buffer Level', tab_id='bl'),
            dbc.Tab(label='Throughput', tab_id='tp'),
            dbc.Tab(label='Segment Size', tab_id='segSize'),
            dbc.Tab(label='Video Quality', tab_id='qualLevel'),
        ],
        id="liveTabs",
        active_tab="bl"
        ),
        dbc.Row(id="liveGraph"),
        dcc.Interval(
            id = 'live_update',
            interval = 1*1000,
            n_intervals = 0,
        ),
         dbc.Row([
            liveEventType,
            liveEventRateBottleneck,
            dbc.Col(dbc.Button("Execute Event", color="primary", id="liveEventButton", type= 'submit'), align='center')
        ]),
    ])

#show content of selected tab
@app.callback(Output('tab-content', 'children'),
              Input('tabs', 'active_tab'))
def switch_tab(at):
    if at == 'results':
        content = refresh_simulation_results()
        return content
    elif at == 'new':
        return newSim_content
    elif at == 'live':
        return liveRes_content

#set clients according to simulation
@app.callback(
    Output('nrClients', 'options'),
    Input('simName', 'value')
)
def set_nrClients_options(selected_simulation):
    if selected_simulation != "no simulations found":
        options = [{"label": f, "value": f} for f in list(listdir(path + selected_simulation))]
        sorted_options = sorted(options, key = lambda k: (int(k["value"])))
        return sorted_options
    else:
        return []

#set choosen clients to first available option
@app.callback(
    Output('nrClients', 'value'),
    Input('nrClients', 'options')
)
def set_nrClients_value(options):
    if len(options) > 0:
        return options[0]['value']
    else:
        return "no simulations found"

#set simIds according to nrClients
@app.callback(
    Output('simId', 'options'),
    Input('nrClients', 'value'),
    State('simName', 'value')
)
def set_simId_options(nrClients, selected_simulation):
    if nrClients != "no simulations found":
        simulations = list(dict.fromkeys([get_sim_id(s) for s in list(listdir(path + selected_simulation + "/" + nrClients))]))
        if -1 in simulations: simulations.remove(-1)
        options = [{"label": f, "value": f} for f in simulations]
        return options
    else:
        return []

#choose simId first available option
@app.callback(
    Output('simId', 'value'),
    Input('simId', 'options')
)
def set_simId_value(options):
    if len(options) > 0:
        return options[0]['value']
    else:
        return "no simId found"

#fill select outputs with all possible outputs
@app.callback(
    Output('selectOutputs', 'value'),
    Input('selectOutputs', 'options')
)
def set_selectClients_value(options):
    if len(options) > 0:
        options = [ o["value"] for o in options ]
        return options
    else:
        return "no output found"

#toggle whether manage outputs options are shown
@app.callback(
    Output('manageCollapse', 'is_open'),
    Input('manageClients', 'n_clicks')
)
def toggle_manageClients(n):
    if n:
        return (n % 2)
    else:
        return False

#toggle whether schedule events options are shown
@app.callback(
    Output('scheduleCollapse', 'is_open'),
    Input('scheduleEvent', 'n_clicks')
)
def toggle_scheduleEvents(n):
    if n:
        return (n % 2)
    else:
        return False

#load the dataframes for the simulation and set client options
@app.callback(
    Output('selectOutputs', 'options'),
    Input('loadButton', 'n_clicks'),
    State('simId', 'value'),
    State('nrClients', 'value'),
    State('simName', 'value')
)
def loadSimData(n, simId, nrClients, simName):
    if n > 0:
        loadEventLog(path + simName + "/" + nrClients, simId)
        load_data(path + simName + "/" + nrClients, simId)
        outputs = get_outputs(path + simName + "/" + nrClients, simId)
        options = [{"label": f, "value": f} for f in outputs]
        return options
    else:
        return []

#update all graphs
@app.callback(
    Output('graphs', 'children'),
    Input('selectOutputs','value'),
    Input('selectedGraphs','value')
)
def update_allGraphs(clients, selectedGraphs):
    
    if client_data:
        graphs = []
        for g in selectedGraphs:
            if g == 'eff' or g == 'totalEff' or g == 'avgEff':
                get_efficiency()
            g = str(g)
            if g == "qualChanges":
                graphs.append( display_qualChanges(clients, False) )
                graphs.append( display_qualChanges(clients, True) )
            elif g == 'eff':
                graphs.append( display_graph(clients, g, 'stacked') )
            elif g == "bufferUnderruns":
                graphs.append(display_Underruns(clients, False) )
                graphs.append(display_Underruns(clients, True) )
            elif g == "avgQuality":
                graphs.append(display_AvgQualLevel(clients, False) )
                graphs.append(display_AvgQualLevel(clients, True) )
            elif g == "avgEff":
                graphs.append(display_AvgEff(clients, False) )
                graphs.append(display_AvgEff(clients, True) )
            elif g in aggregated_units:
                graphs.append( display_graph(clients, aggregated_units[g]['unit'], aggregated_units[g]['aggregation']) )
            else:
                graphs.append( display_graph(clients, g, 'all') )

        return graphs
    else:
        return []

#prepare a new simulation
@app.callback(
    Output('live_data', 'children'),
    Input('newSimButton', 'n_clicks'),
    State('newName', 'value'),
    State('newId', 'value'),
    State('nrServers', 'value'),
    State('videoFile', 'value'),
    State('selectTcp', 'value'),
    State('rateBottle', 'value'),
    State('delayBottle', 'value'),
    State('rateClients', 'value'),
    State('delayClients', 'value'),
)
def prepare_newSim(n, name, simId, servers, video, tcp, rateBottle, delayBottle, rateClients, delayClients):
    if n > 0 and name:
        nrClients = str(app_state["nrClients"])
        if not os.path.exists(path + name):
            mkdir(path + name)
        if not os.path.exists(path + name + "/" + nrClients):
            mkdir(path + name + "/" + nrClients)
        livePath = path + name + "/" + nrClients + "/"
        eventFile = open(livePath + "sim" + str(simId) + "_event_schedule.txt", "w")
        eventFile.write("Event Time Parameters\n")
        for event in app_state["eventSchedule"]:
            eventFile.write(event)
        eventFile.close()
        clientFile = open(livePath + "sim" + str(simId) + "_clients.txt", "w")
        for client in app_state["clients"]:
            clientFile.write(client)
        clientFile.close()
        realTimeEventFile = open(livePath + "sim" + str(simId) + "_real_time_events.txt", "w")
        app_state["realTimeFile"] = livePath + "sim" + str(simId) + "_real_time_events.txt"
        realTimeEventFile.close()
        app_state["eventSchedule"] = []
        app_state["clients"] = []
        return  [livePath, simId]
    return []

#starts a new simulation
@app.callback(
    Output('newSimButton', 'color'), #Todo finish indicator
    Input('live_data', 'children'),
    State('newName', 'value'),
    State('newId', 'value'),
    State('nrServers', 'value'),
    State('selectTcp', 'value'),
    State('rateBottle', 'value'),
    State('delayBottle', 'value'),
    State('rateClients', 'value'),
    State('delayClients', 'value'),
    State('live-inputs', 'value'),
    State('packet-pacing', 'value'),
    State('simScript', 'value')
)
def start_newSim(p, name, simId, servers, tcp, rateBottle, delayBottle, rateClients, delayClients, lInputs, pacing, script):
    if p and app_state["simFinished"]:
        nrClients = str(app_state["nrClients"])
        app_state["nrClients"] = 0
        app_state["simFinished"] = False
        live_client_data = {}
        liveInputsEnabled = 1 if lInputs else 0
        packetPacingEnabled = 1 if pacing else 0 
        print("starting simulation")
        system("./waf --run=\"" + script +" \
            --simulationName=" + name +" \
            --simulationId=" + str(simId) +" \
            --numberOfClients=" + nrClients + " \
            --numberOfServers=" + str(servers) +" \
            --tcp=" + tcp + " \
            --bottleNeckRate=" + str(rateBottle) + "Kbps \
            --bottleNeckDelay=" + str(delayBottle) + "ms \
            --channelRate=" + str(rateClients) + "Kbps \
            --channelDelay=" + str(delayClients) + "ms \
            --liveInputs=" + str(liveInputsEnabled) + " \
            --packetPacing=" + str(packetPacingEnabled) + "\"")
        print("sim finished")
        app_state["simFinished"] = True
        return  'primary'
    print("no sim started")
    return 'primary'

#updates live results
@app.callback(Output('liveGraph', 'children'),
              Output('live_update', 'disabled'),                            
              Input('live_update', 'n_intervals'),
              State('live_data', 'children'),
              State('tabs', 'active_tab'),
              State('liveTabs', 'active_tab'),
              State('liveGraph', 'children'),)
def updateLiveGraphs(n ,liveData, tab, liveTab, prevGraph):
    if tab == 'live' and liveData:
        livePath = liveData[0]
        liveId = "sim" + str(liveData[1])
        if not app_state["loading"]:
            new_load_live_data(livePath, liveId, liveTab)
        Fig = go.Figure()
        clients = get_outputs(livePath, liveId)
        if liveTab == 'bl':
            for client in clients:
                if str(client) in live_client_data and 'bl' in live_client_data[str(client)]:
                    df = live_client_data[str(client)]['bl']
                    Fig.add_scatter(x=df["Time_Now"], y=df["Buffer_Level"], mode='lines', line_shape='hv', name=str(client))
            Fig.update_layout(xaxis_title="seconds",
            yaxis_title="BufferLevel(seconds)",
            title="Buffer Level",
            template="plotly_dark",
            plot_bgcolor='#272B30',
            paper_bgcolor='#272B30',
            height=700)
            blGraph = dbc.Col(dcc.Graph(id="graph", figure= Fig))
            return blGraph, False
        if liveTab == 'tp':
            for client in clients:
                if str(client) in live_client_data and 'tp' in live_client_data[str(client)]:
                    df = live_client_data[str(client)]['tp']
                    Fig.add_scatter(x=df.index, y=df["Bytes_Received"], mode='lines', name=str(client))
            Fig.update_layout(xaxis_title="seconds",
            yaxis_title="Kb",
            title="Throughput",
            template="plotly_dark",
            plot_bgcolor='#272B30',
            paper_bgcolor='#272B30',
            height=700)
            tpGraph = dbc.Col(dcc.Graph(id="graph", figure= Fig))
            return tpGraph, False
        if liveTab == 'segSize':
            for client in clients:
                if str(client) in live_client_data and 'segSize' in live_client_data[str(client)]:
                    df = live_client_data[str(client)]['segSize']
                    Fig.add_scatter(x=df["Download_Request_Sent"], y=df["Segment_Size"], mode='lines', line_shape='hv', name=str(client))
            Fig.update_layout(xaxis_title="seconds",
            yaxis_title="Segment Size",
            title="SegmentSize",
            template="plotly_dark",
            plot_bgcolor='#272B30',
            paper_bgcolor='#272B30',
            height=700)
            segSizeGraph = dbc.Col(dcc.Graph(id="graph", figure= Fig))
            return segSizeGraph, False
        if liveTab == 'qualLevel':
            for client in clients:
                if str(client) in live_client_data and 'qualLevel' in live_client_data[str(client)]:
                    df = live_client_data[str(client)]['qualLevel']
                    Fig.add_scatter(x=df["Time_Now"], y=df["Rep_Level"], mode='lines', line_shape='hv', name=str(client))
            Fig.update_layout(xaxis_title="seconds",
            yaxis_title="Quality Level",
            title="Video Quality",
            template="plotly_dark",
            plot_bgcolor='#272B30',
            paper_bgcolor='#272B30',
            height=700)
            qualLevelGraph = dbc.Col(dcc.Graph(id="graph", figure= Fig))
            return qualLevelGraph, False
        
        return [], False
    return [], True

#execute a live event
@app.callback(
    Output('liveEventButton', 'color'),
    Input('liveEventButton', 'n_clicks'),
    State('liveEventType', 'value'),
    State('liveEventRateBottleneck', 'value'),
)
def executeEvent(n, eventType, bottleneckRate):
    if n > 0:
        realTimeEventFile = open(app_state["realTimeFile"], "a")
        realTimeEventFile.write(eventType + " " + str(bottleneckRate)+"Kbps" + "\n")
        realTimeEventFile.close()
    return "primary"

#schedule an event
@app.callback(
    Output('eventSchedule', 'children'),
    Input('scheduleEventButton', 'n_clicks'),
    State('scheduleEventType', 'value'),
    State('scheduleEventRateBottleneck', 'value'),
    State('scheduleEventTime', 'value')
)
def scheduleEvents(n, eventType, bottleneckRate, time):
    if n > 0:
        app_state["eventSchedule"].append(eventType + " " + str(time) + " " + str(bottleneckRate) + "Kbps\n")
    return [ dbc.ListGroupItem(e) for e in app_state["eventSchedule"] ]

#add clients to simulation
@app.callback(
    Output('addedClients', 'children'),
    Input('clientButton', 'n_clicks'),
    State('nrClients', 'value'),
    State('clientAlgo', 'value'),
    State('videoFile', 'value'),
    State('segmentDuration', 'value')
)
def addClients(n, nrClients, algo, video, segDuration):
    if n > 0:
        app_state["clients"].append(str(nrClients) + " " + algo + " " + video + " " + str(segDuration) + " sec\n")
        app_state["nrClients"] += nrClients
    return [ dbc.ListGroupItem(c) for c in app_state["clients"] ]

if __name__ == '__main__':
    app.run_server(debug=True)