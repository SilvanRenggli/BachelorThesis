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

from os import system
from os import listdir
from os.path import isfile, join

from functools import reduce

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.SLATE], suppress_callback_exceptions=True)

#Set Path to data logs TODO: User can set this path inside the dashboard

path = "./dash-log-files/" #/ns3/ns-3.29

client_data = {}
router_data = {}

congestionProtocols = [{"label": 'TcpNewReno', "value": 'ns3::TcpNewReno'}, {"label": 'TcpCubic', "value": 'ns3::TcpCubic'}, {"label": 'TcpWestwood', "value": 'ns3::TcpWestwood'}, {"label": 'TcpVegas', "value": 'ns3::TcpVegas'}, {"label": 'TcpVeno', "value": 'ns3::TcpVeno'}, {"label": 'TcpBic', "value": 'ns3::TcpBic'}] 

#returns the id of a simulation file
def get_sim_id(file):
    match = re.search(r"^sim\d+", file)
    if match:
        return match.group()
    else:
        return -1

#returns all client outpur files that belong to this simulation
def get_outputs(path, simId):
    outputs = []
    for f in list( listdir( path )):
        if (str(f).startswith(simId) and not str(f).find('cl') == -1 and str(f).endswith("output.txt")):
            outputs.append(str(f))
    return outputs

app.layout = html.Div([
    dbc.Tabs(
        [
            dbc.Tab(label='Simulation Results', tab_id='results'),
            dbc.Tab(label='Compare Simulations', tab_id='compare'),
            dbc.Tab(label='New Simulation', tab_id='new'),
            dbc.Tab(label='Live Results', tab_id='live'),
        ],
        id="tabs",
        active_tab="results"
    ),

    html.Div(id='tab-content')
])

#load all dataframes from this simulation and store them in a dictionary
def load_data(path, simId):
    #get data for all clients
    for f in list( listdir( path )):
        if (str(f).startswith(simId) and not str(f).find('cl') == -1 and str(f).endswith("output.txt")):
            cdata = pd.read_csv(path + "/" + str(f), sep = ";")
            client_dict = {}
            tp = cdata.copy()
            tp = tp[["Time_Now","Bytes_Received"]].dropna()
            tp["Time_Now"] = pd.to_timedelta(tp["Time_Now"], unit = 'seconds')
            tp = tp.resample('1S', on= "Time_Now").sum() #TODO always start resampling at 2s
            tp.index = tp.index.seconds
            tp["Bytes_Received"] = tp["Bytes_Received"] * 8 * 0.001
            client_dict['tp'] = tp
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

#get the average of all dataframes
def get_average(dfs):
    avg = reduce(lambda a, b: a.add(b, fill_value=0), dfs)
    avg = avg.div(len(dfs))
    return avg

def get_algo(client):
    result = re.search('cl\d+_(.*)_output.txt', client)
    return result.group(1)


#Components for result visualisation:
selectSimName = dbc.Col(
                    dbc.FormGroup([
                        dbc.Label("Simulation", html_for="simName"),
                        dbc.Select(
                            id="simName",
                            options=[
                                {"label": f, "value": f} for f in sorted(list(listdir(path)))
                            ],
                            value = sorted(list(listdir(path)))[0]
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

pandaClients = dbc.Col(
                    dbc.FormGroup([
                        dbc.Label("Clients using Panda", html_for="pandaClients"),
                         dbc.Input( 
                            id ='newId',
                            value=0,
                            type = "number", min=0, max=999, step=1
                        )     
                    ]),
                    width = {'size': 1, 'offset': 1}
                )

nrServers = dbc.Col(
                    dbc.FormGroup([
                        dbc.Label("Number of Servers:", html_for="nrServers"),
                         dbc.Input( 
                            id ='nrServers',
                            value=1,
                            type = "number", min=1, max=999, step=1
                        )     
                    ]),
                    width = 1
                )

pandaClients = dbc.Col(
                    dbc.FormGroup([
                        dbc.Label("Clients using Panda:", html_for="pandaClients"),
                         dbc.Input( 
                            id ='pandaClients',
                            value=0,
                            type = "number", min=0, max=999, step=1
                        )     
                    ]),
                    width = {'size': 1, 'offset': 1}
                )

tobascoClients = dbc.Col(
                    dbc.FormGroup([
                        dbc.Label("Clients using Tobasco:", html_for="tobascoClients"),
                         dbc.Input( 
                            id ='tobascoClients',
                            value=0,
                            type = "number", min=0, max=999, step=1
                        )     
                    ]),
                    width = 1
                )

festiveClients = dbc.Col(
                    dbc.FormGroup([
                        dbc.Label("Clients using Festive:", html_for="festiveClients"),
                         dbc.Input( 
                            id ='festiveClients',
                            value=0,
                            type = "number", min=0, max=999, step=1
                        )     
                    ]),
                    width = 1
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
                    width = {'size': 2, 'offset': 1}
                )

rateClients = dbc.Col(
                    dbc.FormGroup([
                        dbc.Label("Datarate for clients (Mbps):", html_for="rateClients"),
                         dbc.Input( 
                            id ='rateClients',
                            value=5,
                            type = "number", min=1, max=10000, step=1
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
                        dbc.Label("Datarate of bottleneck (Mbps):", html_for="rateBottle"),
                         dbc.Input( 
                            id ='rateBottle',
                            value=100,
                            type = "number", min=1, max=10000, step=1
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
        dbc.Row(id="tpGraph")
    ])

newSim_content = html.Div([
        dbc.Row([]),
        dbc.Row([
            newName,
            newId,
            selectTcp
        ]),
        dbc.Row([
            pandaClients,
            tobascoClients,
            festiveClients,
            nrServers,
            videoFile
        ]),
        dbc.Row([
            rateClients,
            delayClients,
            rateBottleneck,
            delayBottleneck
        ]),
        dbc.Row([
            dbc.Col(
                dbc.Button("New Simulation", color="primary", id="newSimButton", type= 'submit'),
                width = {'size': 10, 'offset': 1})
        ])
    ])

#show content of selected tab
@app.callback(Output('tab-content', 'children'),
              Input('tabs', 'active_tab'))
def switch_tab(at):
    if at == 'results':
        return results_content
    elif at == 'compare':
        return html.Div([
            html.H3('Compare content')
        ])
    elif at == 'new':
        return newSim_content
    elif at == 'live':
        return html.Div([
            html.H3('Live content')
        ])

#set clients according to simulation
@app.callback(
    Output('nrClients', 'options'),
    Input('simName', 'value')
)
def set_nrClients_options(selected_simulation):
    options = [{"label": f, "value": f} for f in list(listdir(path + selected_simulation))]
    sorted_options = sorted(options, key = lambda k: (int(k["value"])))
    return sorted_options

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
    simulations = list(dict.fromkeys([get_sim_id(s) for s in list(listdir(path + selected_simulation + "/" + nrClients))]))
    if -1 in simulations: simulations.remove(-1)
    options = [{"label": f, "value": f} for f in simulations]
    return options

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

#load the dataframes for the simulation and set client options
@app.callback(
    Output('selectOutputs', 'options'),
    Input('loadButton', 'n_clicks'),
    State('simId', 'value'),
    State('nrClients', 'value'),
    State('simName', 'value')
)
def loadSimData(n, simId, nrClients, simName):
    load_data(path + simName + "/" + nrClients, simId)
    outputs = get_outputs(path + simName + "/" + nrClients, simId)
    options = [{"label": f, "value": f} for f in outputs]
    options.sort()
    return options

#update throughput graph
@app.callback([
    Output('tpGraph', 'children'),
    Output('tpAvgGraph', 'children')],
    Input('selectOutputs','value')
)
def update_tpGraph(clients):
    tpFig = go.Figure()
    tpAvgFig = go.Figure()
    dfs = []
    
    if client_data:
        df = router_data['tp']
        tpFig.add_scatter(x=df.index, y=df["Throughput"], mode='lines', line=dict(color='firebrick', width=3), name="Bottleneck Link")
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

        return tpGraph, tpAvgGraph
    else:
        return [], []

#starts a new simulation
@app.callback(
    Output('newSimButton', 'color'),
    Input('newSimButton', 'n_clicks'),
    State('newName', 'value'),
    State('newId', 'value'),
    State('pandaClients', 'value'),
    State('tobascoClients', 'value'),
    State('festiveClients', 'value'),
    State('nrServers', 'value'),
    State('videoFile', 'value'),
    State('selectTcp', 'value'),
    State('rateBottle', 'value'),
    State('delayBottle', 'value'),
    State('rateClients', 'value'),
    State('delayClients', 'value'),
)
def start_newSim(n, name, simId, panda, tobasco, festive, servers, video, tcp, rateBottle, delayBottle, rateClients, delayClients):
    if n > 0:
    #    system("./waf --run=\"lan-simulation \
    #     --simulationName=BalancedSimulation\
    #     --simulationId=2 \
    #     --numberOfClients=30 \
    #     --numberOfServers=10 \
    #     --segmentDuration=2000000 \
    #     --pandaClients=10 \
    #     --tobascoClients=10 \
    #     --festiveClients=10 \
    #     --segmentSizeFile=contrib/dash/segmentSizes.txt \
    #     --tcp=ns3::TcpNewReno \
    #     --bottleNeckRate=100Mbps \
    #     --bottleNeckDelay=2ms \
    #     --channelRate=5Mbps \
    #     --channelDelay=2ms\"")
        system("./waf --run=\"lan-simulation \
            --simulationName=" + name +" \
            --simulationId=" + str(simId) +" \
            --numberOfClients=" + str(panda + tobasco + festive) + " \
            --numberOfServers=" + str(servers) +" \
            --segmentDuration=2000000 \
            --pandaClients=" + str(panda) +" \
            --tobascoClients=" + str(tobasco) +" \
            --festiveClients=" + str(festive) +" \
            --segmentSizeFile=DashVideos/" + video+" \
            --tcp=" + tcp + " \
            --bottleNeckRate=" + str(rateBottle) + "Mbps \
            --bottleNeckDelay=" + str(delayBottle) + "ms \
            --channelRate=" + str(rateClients) + "Mbps \
            --channelDelay=" + str(delayClients) + "ms\"")
    return 'secondary'

if __name__ == '__main__':
    app.run_server(debug=True)