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

from os import listdir
from os.path import isfile, join

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.SLATE], suppress_callback_exceptions=True)

#Set Path to data logs TODO: User can set this path inside the dashboard

path = "./ns3/ns-3.29/dash-log-files/"

#returns the id of a simulation file
def get_sim_id(file):
    match = re.search(r"^sim\d+", file)
    if match:
        return match.group()
    else:
        return -1

#returns all files that belong to this simulation
def get_outputs(path, simId):
    outputs = []
    for f in list( listdir( path )):
        if(str(f).startswith(simId) and str(f).endswith("output.txt")):
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
                                dbc.Button("Manage Outputs", color="secondary", id="manageOutputs")
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
        return html.Div([
            html.H3('NewSim content')
        ])
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

#set available outputs for data visualisation
@app.callback(
    Output('selectOutputs', 'options'),
    Input('simId', 'value'),
    State('nrClients', 'value'),
    State('simName', 'value')
)
def set_selectClients_options(simId, nrClients, simulation):
    outputs = get_outputs(path + simulation + "/" + nrClients, simId)
    options = [{"label": f, "value": f} for f in outputs]
    options.sort()
    return options

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
    Input('manageOutputs', 'n_clicks')
)
def toggle_manageOutputs(n):
    print(n)
    if n:
        return (n % 2)
    else:
        return False


if __name__ == '__main__':
    app.run_server(debug=True)