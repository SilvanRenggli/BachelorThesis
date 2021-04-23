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
router_data = {}
live_client_data = {}
app_state = { "loading" : False, "simFinished" : True, "realTimeFile" : "", "eventSchedule" : [], "clients": [], "nrClients": 0}
extract_unit = { 
                "bl" : {"index": "Time_Now", "value": "Buffer_Level", "resample": False, "timeUnit": 'nanoseconds'},
                "tp" : {"index": "Time_Now", "value": "Bytes_Received", "resample": True, "timeUnit": 'seconds'},
                "segSize" : {"index": "Download_Request_Sent", "value": "Segment_Size", "resample": False, "timeUnit": 'nanoseconds'},
                "qualLevel" : {"index": "Time_Now", "value": "Rep_Level", "resample": False, "timeUnit": 'nanoseconds'},
                }

congestionProtocols = [{"label": 'TcpNewReno', "value": 'ns3::TcpNewReno'}, {"label": 'TcpWestwood', "value": 'ns3::TcpWestwood'}, {"label": 'TcpVegas', "value": 'ns3::TcpVegas'}, {"label": 'TcpVeno', "value": 'ns3::TcpVeno'}, {"label": 'TcpBic', "value": 'ns3::TcpBic'}] #{"label": 'TcpCubic', "value": 'ns3::TcpCubic'}
abrAlgorithms = ["panda", "tobasco", "festive"]

#returns the id of a simulation file
def get_sim_id(file):
    match = re.search(r"^sim\d+", file)
    if match:
        return match.group()
    else:
        return -1

#returns all client output files that belong to this simulation
def get_outputs(path, simId):
    outputs = []
    for f in list( listdir( path )):
        if (str(f).startswith(simId) and not str(f).find('cl') == -1 and str(f).endswith("output.txt")):
            outputs.append(str(f))
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
    #get data for all clients
    for f in list( listdir( path )):
        if (str(f).startswith(simId) and not str(f).find('cl') == -1 and str(f).endswith("output.txt")):
            cdata = pd.read_csv(path + "/" + str(f), sep = ";")
            client_dict = {}
            #get throughput
            tp = cdata.copy()
            tp = tp[["Time_Now","Bytes_Received"]].dropna()
            tp["Time_Now"] = pd.to_timedelta(tp["Time_Now"], unit = 'seconds')
            tp = tp.resample('1S', on= "Time_Now").sum() #TODO always start resampling at 2s
            tp.index = tp.index.seconds
            tp["Bytes_Received"] = tp["Bytes_Received"] * 8 * 0.001
            client_dict['tp'] = tp
            #get buffer level
            bl = cdata.copy()
            bl = bl[["Time_Now","Buffer_Level"]].dropna()
            bl["Time_Now"] = pd.to_timedelta(bl["Time_Now"], unit = 'nanoseconds')
            client_dict['bl'] = bl
            #get bufferunderrun log
            bul = cdata.copy()
            bul = bul[["Time_Now","Buffer_Underrun"]].dropna()
            bul["Time_Now"] = pd.to_timedelta(bul["Time_Now"], unit = 'nanoseconds')
            client_dict['bul'] = bul
            #get segment sizes
            segSize = cdata.copy()
            segSize = segSize[["Download_Request_Sent","Segment_Size"]].dropna()
            segSize["Download_Request_Sent"] = pd.to_timedelta(segSize["Download_Request_Sent"], unit = 'nanoseconds')
            client_dict['segSize'] = segSize
            #get quality levels
            qualLevel = cdata.copy()
            qualLevel = qualLevel[["Time_Now","Rep_Level"]].dropna()
            qualLevel["Time_Now"] = pd.to_timedelta(qualLevel["Time_Now"], unit = 'nanoseconds')
            client_dict['qualLevel'] = qualLevel
            client_data[str(f)] = client_dict
        if str(f).startswith(simId) and str(f).endswith("router_output.txt"):
            #get data for bottleneck router
            rdata = pd.read_csv(path + "/" + str(f), sep = ";")
            tp = rdata.copy()
            tp = tp[["Time_Now","Throughput"]].dropna()
            tp["Time_Now"] = pd.to_timedelta(tp["Time_Now"], unit = 'seconds')
            tp = tp.resample('1S', on= "Time_Now").sum() #TODO always start resampling at 2s
            tp.index = tp.index.seconds
            tp["Throughput"] = tp["Throughput"] * 8 * 0.001
            router_data['tp'] = tp

#update the dataframes from the currently running simulation    
def new_load_live_data(path, simId, unit):
    if unit == 'avgTp':
        unit = 'tp'
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
                df = df[[ extract_unit[unit]["index"], extract_unit[unit]["value"] ]].dropna()
                df[extract_unit[unit]["index"]] = pd.to_timedelta(df[extract_unit[unit]["index"]], unit = extract_unit[unit]["timeUnit"])
                if extract_unit[unit]["resample"]:
                    df = df.resample('1S', on= extract_unit[unit]["index"]).sum() #TODO always start resampling at 2s
                    if not df.empty:
                        df.index = df.index.seconds
                        df[extract_unit[unit]["value"]] = df[extract_unit[unit]["value"]] * 8 * 0.001
                client_dict[unit] = df
                
            else:
                lastRead = client_dict[unit +"_lastRead"]
                df = client_dict["df"][lastRead:].copy()
                df = df[[ extract_unit[unit]["index"], extract_unit[unit]["value"] ]].dropna()
                df[extract_unit[unit]["index"]] = pd.to_timedelta(df[extract_unit[unit]["index"]], unit = extract_unit[unit]["timeUnit"])
                if extract_unit[unit]["resample"]:
                    df = df.resample('1S', on= extract_unit[unit]["index"]).sum() #TODO always start resampling at 2s
                    if not df.empty:
                        df.index = df.index.seconds
                        df[extract_unit[unit]["value"]] = df[extract_unit[unit]["value"]] * 8 * 0.001
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

def get_algo(client):
    result = re.search('cl\d+_(.*)_output.txt', client)
    return result.group(1)

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
        dbc.Row([]),
        dbc.Row([
            selectSimName,
            selectNrClients,
            selectSimId,
            dbc.Col(dbc.Button("Load Data", color="primary", id="loadButton", type= 'submit'), align='center')
        ]),
        dbc.Row([
            selectOutputs
        ]),
        dbc.Row(id="tpAvgGraph"),
        dbc.Row(id="tpGraph"),
        dbc.Row(id="blGraph"),
        dbc.Row(id="bulGraph"),
        dbc.Row(id="qualLevelGraph"),
        dbc.Row(id="segSizeGraph")
    ])

    return results_content




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
                            type = "number", min=100, max=100000, step=1
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
            dbc.Tab(label='Average Throughput', tab_id='avgTp'),
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
        options.sort()
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
        load_data(path + simName + "/" + nrClients, simId)
        outputs = get_outputs(path + simName + "/" + nrClients, simId)
        options = [{"label": f, "value": f} for f in outputs]
        options.sort()
        return options
    else:
        return []

#update all graphs
@app.callback([
    Output('tpGraph', 'children'),
    Output('tpAvgGraph', 'children'),
    Output('blGraph', 'children'),
    Output('bulGraph', 'children'),
    Output('segSizeGraph', 'children'),
    Output('qualLevelGraph', 'children')],
    Input('selectOutputs','value')
)
def update_allGraphs(clients):
    tpFig = go.Figure()
    tpAvgFig = go.Figure()
    blFig = go.Figure()
    bulFig = go.Figure()
    segSizeFig = go.Figure()
    qualLevelFig = go.Figure()
    dfs = []
    
    if client_data:
        #df = router_data['tp']
        #tpFig.add_scatter(x=df.index, y=df["Throughput"], mode='lines', line=dict(color='firebrick', width=3), name="Bottleneck Link")
        for client in clients:
            df = client_data[str(client)]['tp']
            tpFig.add_scatter(x=df.index, y=df["Bytes_Received"], mode='lines', name=str(client))
        tpFig.update_layout(xaxis_title="seconds",
        yaxis_title="Kb",
        title="Throughput",
        template="plotly_dark",
        plot_bgcolor='#272B30',
        paper_bgcolor='#272B30',
        height=700)
        tpGraph = dbc.Col(dcc.Graph(id="graph", figure= tpFig))

        abrAlgos = {}
        for client in clients:
            algo = get_algo(client)
            if not algo in abrAlgos:
                abrAlgos[algo] = []
            abrAlgos[algo].append(client_data[str(client)]['tp'])
            dfs.append(client_data[str(client)]['tp'])
        avgAll = get_average(dfs)
        tpAvgFig.add_scatter(x=avgAll.index, y=avgAll["Bytes_Received"], mode='lines' , name="All Clients")
        for key, value in abrAlgos.items():
            avg = get_average(value)
            tpAvgFig.add_scatter(x=avg.index, y=avg["Bytes_Received"], mode='lines' , name= key)
        tpAvgFig.update_layout(xaxis_title="seconds",
        yaxis_title="Kb",
        title="Average Throughput",
        template="plotly_dark",
        plot_bgcolor='#272B30',
        paper_bgcolor='#272B30',
        height=700)
        tpAvgGraph = dbc.Col(dcc.Graph(id="graph", figure=tpAvgFig))

        for client in clients:
            df = client_data[str(client)]['bl']
            blFig.add_scatter(x=df["Time_Now"], y=df["Buffer_Level"], mode='lines', line_shape='hv', name=str(client))
        blFig.update_layout(xaxis_title="seconds",
        yaxis_title="BufferLevel(seconds)",
        title="Buffer Level",
        template="plotly_dark",
        plot_bgcolor='#272B30',
        paper_bgcolor='#272B30',
        height=700)
        blGraph = dbc.Col(dcc.Graph(id="graph", figure= blFig))

        for client in clients:
            df = client_data[str(client)]['bul']
            bulFig.add_scatter(x=df["Time_Now"], y=df["Buffer_Underrun"], mode='lines', line_shape='hv', name=str(client))
        bulFig.update_layout(xaxis_title="seconds",
        yaxis_title="Buffer Underrun",
        title="Buffer Underrun",
        template="plotly_dark",
        plot_bgcolor='#272B30',
        paper_bgcolor='#272B30',
        height=700)
        bulGraph = dbc.Col(dcc.Graph(id="graph", figure= bulFig))

        for client in clients:
            df = client_data[str(client)]['segSize']
            segSizeFig.add_scatter(x=df["Download_Request_Sent"], y=df["Segment_Size"], mode='lines', line_shape='hv', name=str(client))
        segSizeFig.update_layout(xaxis_title="seconds",
        yaxis_title="Size(Bit)",
        title="Segment Sizes",
        template="plotly_dark",
        plot_bgcolor='#272B30',
        paper_bgcolor='#272B30',
        height=700)
        segSizeGraph = dbc.Col(dcc.Graph(id="graph", figure= segSizeFig))

        for client in clients:
            df = client_data[str(client)]['qualLevel']
            qualLevelFig.add_scatter(x=df["Time_Now"], y=df["Rep_Level"], mode='lines', line_shape='hv', name=str(client))
        qualLevelFig.update_layout(xaxis_title="seconds",
        yaxis_title="Quality Level",
        title="Video Quality",
        template="plotly_dark",
        plot_bgcolor='#272B30',
        paper_bgcolor='#272B30',
        height=700)
        qualLevelGraph = dbc.Col(dcc.Graph(id="graph", figure= qualLevelFig))

        return tpGraph, tpAvgGraph, blGraph, bulGraph, segSizeGraph, qualLevelGraph
    else:
        return [], [], [], [], [], []

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
        print("pressed")
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
        if liveTab == 'avgTp':
            dfs = []
            abrAlgos = {}
            for client in clients:
                if str(client) in live_client_data and 'tp' in live_client_data[str(client)]:
                    algo = get_algo(client)
                    if not algo in abrAlgos:
                        abrAlgos[algo] = []
                    abrAlgos[algo].append(live_client_data[str(client)]['tp'])
                    dfs.append(live_client_data[str(client)]['tp'])
            if dfs:
                avgAll = get_average(dfs)
                Fig.add_scatter(x=avgAll.index, y=avgAll["Bytes_Received"], mode='lines' , name="All Clients")
            for key, value in abrAlgos.items():
                if value:
                    avg = get_average(value)
                    Fig.add_scatter(x=avg.index, y=avg["Bytes_Received"], mode='lines' , name= key)
            Fig.update_layout(xaxis_title="seconds",
            yaxis_title="Kb",
            title="Average Throughput",
            template="plotly_dark",
            plot_bgcolor='#272B30',
            paper_bgcolor='#272B30',
            height=700)
            tpAvgGraph = dbc.Col(dcc.Graph(id="graph", figure=Fig))
            return tpAvgGraph, False
        
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