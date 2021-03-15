# Run this app with `python app.py` and
# visit http://127.0.0.1:8050/ in your web browser.

import dash
import dash_core_components as dcc
import dash_html_components as html
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import re
from dash.dependencies import Input, Output, State

from os import listdir
from os.path import isfile, join

app = dash.Dash(__name__)

#Set Path to data logs TODO: User can set this path inside the dashboard
path = "./ns3/ns-3.29/dash-log-files/"

simulationOutput = {}

colors = {
    'background': '#111111',
    'text': '#7FDBFF'
}

app.layout = html.Div(children=[ 
    html.Label('Simulation'),
    dcc.Dropdown(
        id = 'simulation',
        options=[
            {"label": f, "value": f} for f in list(listdir(path))
        ],
        value=list(listdir(path))[0],
    ),

    html.Label('Nr of Clients'),
    dcc.Dropdown(
        id ='nrClients',
        options=[
        ],
        value='',
    ),

    html.Label('Simulation id'),
    dcc.Dropdown(
        id ='simId',
        options=[
        ],
        value='',
    ),

    html.Label('select clients'),
    dcc.Dropdown(
        id='selectClients',
        options=[],
        value=[],
        multi = True
    ),

    html.Label('Show stat'),
    dcc.Dropdown(
        id='showStat',
        options=[{"label":'Throughput', "value":'Bytes_Received'}, {"label":'Buffer Level', "value":'Buffer_Level'}], 
        value='Bytes_Received',
    ),

    html.Label('Aggregation'),
    dcc.Dropdown(
        id='aggregation',
        options=[{"label":'All data', "value":'all'}, {"label":'Mean and std', "value":'meanStd'}], 
        value='all',
    ),
    
    dcc.Graph(id="graph")
])

def get_sim_id(file):
    match = re.search(r"^sim\d", file)
    if match:
        return match.group()
    else:
        return -1

def get_outputs(path, simId):
    outputs = []
    for f in list( listdir( path )):
        if(str(f).startswith(simId) and str(f).endswith("output.txt")):
            outputs.append(str(f))
    return outputs

def loadOutput(op, path):
    df = pd.read_csv(path + "/" + op, sep = ";")
    simulationOutput[op] = df

def get_stats(stat, client):
    df = simulationOutput[client]
    filtered_df = df[["Time_Now", stat]].dropna()
    filtered_df["Time_Now"] = pd.to_timedelta(filtered_df["Time_Now"], unit = 'micro')
    if stat == "Bytes_Received":
        filtered_df["Bytes_Received"] = filtered_df["Bytes_Received"] * 0.000001
        filtered_df = filtered_df.resample('us', on= "Time_Now").sum()
    return filtered_df

#set clients according to simulation
@app.callback(
    Output('nrClients', 'options'),
    Input('simulation', 'value')
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
    State('simulation', 'value')
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


#set available clients for data visualisation
@app.callback(
    Output('selectClients', 'options'),
    Input('simId', 'value'),
    Input('nrClients', 'value'),
    Input('simulation', 'value')
)
def set_selectClients_options(simId, nrClients, simulation):
    outputs = get_outputs(path + simulation + "/" + nrClients, simId)
    options = [{"label": f, "value": f} for f in outputs]
    #load df for all options
    simulationOutput.clear()
    for op in outputs:
        loadOutput(op, path + simulation + "/" + nrClients)
    return options

#fill select Clients with all possible clients
@app.callback(
    Output('selectClients', 'value'),
    Input('selectClients', 'options')
)
def set_selectClients_value(options):
    if len(options) > 0:
        options = [ o["value"] for o in options ]
        options.sort()
        return options
    else:
        return "no output found"

@app.callback(
    Output('graph', 'figure'),
    Input('simId', 'value'),
    Input('selectClients','value'),
    Input('showStat', 'value'),
    Input('aggregation', 'value'),
    State('nrClients', 'value'),
    State('simulation', 'value')
)
def update_graph(simId, clients, statToShow, aggregation, nrClients, simulation):
    fig = go.Figure()
    if aggregation == "all":
        for client in clients:
            df = get_stats(statToShow, client)
            fig.add_scatter(x=df.index, y=df[statToShow], mode='lines')
            fig.update_layout(template="plotly_dark", plot_bgcolor='#272B30', paper_bgcolor='#272B30')
        return fig
    if aggregation == "meanStd":
        dataframes = []
        for client in clients:
            dataframes.append(get_stats(statToShow, client).reset_index())
        df = pd.concat(dataframes, axis = 0)
        df_mean = df.groupby(df.index).mean()
        fig.add_scatter(x=df_mean.index, y=df_mean[statToShow], mode='lines')
        fig.update_layout(template="plotly_dark", plot_bgcolor='#272B30', paper_bgcolor='#272B30')

        return fig

if __name__ == '__main__':
    app.run_server(debug=True)