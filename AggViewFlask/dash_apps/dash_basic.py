# import logging

from pg_shared.dash_utils import create_dash_app_util, date_range_control, compute_range
from agg_view import core, menu, Langstrings
from flask import session
from datetime import datetime as dt, timedelta

from dash import html, dcc, callback_context, no_update
import plotly.express as px
from dash.dependencies import Output, Input, State

import pandas as pd

view_name = "basic"  # this is required

agg_fields = ("tag", "plaything_name", "plaything_part", "specification_id")

plaything_names = list(core.aggregated_container.query_items("SELECT DISTINCT VALUE c.plaything_name FROM c", enable_cross_partition_query=True))
if "-" in plaything_names:
    plaything_names.remove("-")

def create_dash(server, url_rule, url_base_pathname):
    """Create a Dash view"""
    app = create_dash_app_util(server, url_rule, url_base_pathname)

    # dash app definitions goes here
    # app.config.suppress_callback_exceptions = True
    app.title = "Basic Aggregated Usage"

    app.layout = html.Div([
        dcc.Location(id="location"),
        html.Div(id="menu"),
        html.Div(
            [
                html.H1("(Basic Aggregations)", id="heading", className="header-title")
            ],
            className="header"
        ),

        # Outcome Proportion
        html.Div(
            [
                html.Div(
                    [
                        html.Label("(Plaything Name:)", id="plaything_name_label", style={"margin-top": "0px"}),
                        dcc.Dropdown(id="plaything_name", options=plaything_names, searchable=False, clearable=True, style={"margin-left": "10px"}),
                        html.Label("(Show Facets:)", id="facet_label", style={"margin-top": "10px"}),
                        dcc.Dropdown(value=None, options=agg_fields, id="facet_options", searchable=False, clearable=True, style={"margin-left": "10px"}),
                        html.Label("(Filter by:)", id="filter_by_label", style={"margin-top": "10px"}),
                        dcc.Dropdown(value=None, options=agg_fields, id="filter_by_options", searchable=False, clearable=True, style={"margin-left": "10px"}),
                        # html.Label("=", id="filter_value_label", style={"margin-top": "10px"}),
                        dcc.Dropdown(value=None, id="filter_value_options", searchable=False, clearable=True, style={"margin-left": "10px"})
                    ], className="col-sm-4"
                ),
                
                html.Div(id="date_range_div", className="col-sm-8")
            ], className="row"
        ),
        html.Div(
            [
                html.Div(
                    [
                        dcc.Loading(
                            dcc.Graph(id="counts_chart", config={'displayModeBar': True}),
                            type="circle"
                        )
                    ], className="col"
                )
            ], className="row"
        )

    ],
    className="wrapper"
    )

    # This callback handles initial setup of the menu, langstring labels, drop-down options
    @app.callback(
        [
            Output("menu", "children"),
            Output("heading", "children"),
            # category selectors
            Output("plaything_name_label", "children"),
            Output("facet_label", "children"),
            Output("filter_by_label", "children"),
            Output("date_range_div", "children")
        ],
        [
            Input("location", "pathname"),
            Input("location", "search")
            ]
    )
    def initial_load(pathname, querystring):
        lang = "en"
        if len(querystring) > 0:
            for param, value in [pv.split('=') for pv in querystring[1:].split("&")]:
                if param == "lang":
                    lang = value
                    break
        langstrings = Langstrings(lang)
    
        if callback_context.triggered_id == "location":
            # initial load
            menu_children = core.make_menu(menu, langstrings, core.at_root, view_name, query_string=querystring, for_dash=True)
            # start with today as the end of date range
            end_date_ = dt.utcnow().date()
            start_date_ = end_date_ + timedelta(days=7)
            output = [
                menu_children,
                langstrings.get("BASIC_TITLE"),
                langstrings.get("PLAYTHING_NAME"),
                langstrings.get("SHOW_FACET"),
                langstrings.get("FILTER_BY"),
                [   
                    date_range_control(start_date_, end_date_),
                    html.Div(
                        [
                            html.Label("Show:"),
                            dcc.RadioItems(options={"count": "Count", "sessions": "Sessions"}, value="count", id="metric", inline=True, inputStyle={"margin-left": "20px"})
                        ], className="mt-2"
                    )
                ]
            ]
        else:
            output = [no_update] * 6

        return output

    
    # date control buttoms
    @app.callback(
        [Output("date-start", "date"), Output("date-end", "date")],
        [Input("range-today", "n_clicks"), Input("range-yesterday", "n_clicks"), Input("minus-day", "n_clicks"), Input("plus-day", "n_clicks"),
         Input("range-7days", "n_clicks"), Input("minus-week", "n_clicks"), Input("plus-week", "n_clicks"),
         Input("range-lastmonth", "n_clicks"), Input("range-thismonth", "n_clicks"),  Input("minus-month", "n_clicks"), Input("plus-month", "n_clicks")],
        [State("date-start", "date"), State("date-end", "date")]
    )
    def set_range(rt_clicks, ry_clicks, dm_clicks, dp_clicks,
                  r7d_clicks, wm_clicks, wp_clicks,
                  rlm_clicks, rcm_clicks, mm_clicks, mp_clicks,
                  start_date, end_date):    # these two used for plus/minus only
        return compute_range(callback_context.triggered_id, start_date, end_date)
    
    # Something of a monster!
    # Handles drop-down changes, leading to both update of chart and [sometimes] of some dropdowns
    # Handles date range changes, leading to update of chart only
    @app.callback(
        [
            Output("facet_options", "options"),
            Output("facet_options", "value"),
            Output("filter_by_options", "options"),
            Output("filter_by_options", "value"),
            Output("filter_value_options", "options"),
            Output("filter_value_options", "value"),
            Output("counts_chart", "figure")
        ],
        [
            Input("plaything_name", "value"),
            Input("facet_options", "value"),
            Input("filter_by_options", "value"),
            Input("filter_value_options", "value"),
            Input("date-start", "date"),
            Input("date-end", "date"),
            Input("metric", "value")
        ]
    )
    def update_charts(plaything_name, facet_option, filter_by_option, filter_value_option, start_date, end_date, metric):
        tid = callback_context.triggered_id

        # effects on drop-down lists. first set up default outputs (default values are as Inputs)
        new_facet_options = no_update
        new_filter_by_options = no_update
        new_filter_value_options = no_update
        # facet and filter-by dropdowns contain all fields unless there is a selected plaything.
        if tid == "plaything_name":
            free_fields = sorted(agg_fields)
            if plaything_name is not None:
                free_fields.remove("plaything_name")
            new_facet_options = free_fields
            new_filter_by_options = free_fields
        # if a plaything is chosen, clear facet or filter dropdown values of "plaything name"
        if (tid == "plaything_name") and (plaything_name is not None):
            if facet_option == "plaything_name":
                facet_option = None
            if filter_by_option == "plaything_name":
                filter_by_option = None
                new_filter_value_options = []
        # if either a facet or filter-by is chosen then make sure the other one does not have the same field selected
        if (tid == "facet_options") and (facet_option is not None) and (facet_option == filter_by_option):
            filter_by_option = None
            new_filter_value_options = []
        if (tid == "filter_by_options") and (filter_by_option is not None) and (facet_option == filter_by_option):
            facet_option = None
        # if filter-by is used, populate the values options
        if tid == "filter_by_options":
            if filter_by_option is None:
                new_filter_value_options = []
            else:
                qry = f"SELECT DISTINCT VALUE c.{filter_by_option} FROM c"
                if plaything_name is not None:
                    qry += f" WHERE c.plaything_name = '{plaything_name}'"
                new_filter_value_options = list(core.aggregated_container.query_items(qry, enable_cross_partition_query=True))

        # if the filter-by has changed but the value not yet specified, DO NOT update the fiture, otherwise DO
        if (tid == "filter_by_options") and (filter_value_option is None):
            figure = no_update
        else:
            # chart prep
            start_dt = dt.strptime(start_date, "%Y-%m-%d")
            end_dt = dt.strptime(end_date, "%Y-%m-%d")
            start_ts = int(start_dt.timestamp())  # ts for DB query
            end_ts = int(end_dt.timestamp()) + 24 * 3600 # the dt at the **start** of the end date in the range
            # query data. for ranges of 5 days or less, query the date_hr set, otherwise query the date set
            is_date_hr = (end_dt - start_dt).days < 5
            period_name = "date_hr" if is_date_hr else "date"
            select_parts = [
                f"c.{period_name}",
                f"c.{metric}"
            ]
            if facet_option is not None:
                select_parts.append(f"c.{facet_option}")
            where_parts = [
                "IS_DEFINED(c.date_hr)" if is_date_hr else "IS_DEFINED(c.date)",
                f"c.start_ts >= {start_ts}",
                f"c.start_ts < {end_ts}"
            ]
            if plaything_name is not None:
                where_parts.append(f"c.plaything_name = '{plaything_name}'")
            if (filter_by_option is not None) and (filter_value_option is not None):
                where_parts.append(f"c.{filter_by_option} = '{filter_value_option}'")
            qry = f"SELECT {', '.join(select_parts)} FROM c WHERE {' AND '.join(where_parts)}"
            # print(qry)
            
            raw_df = pd.DataFrame(core.aggregated_container.query_items(qry, enable_cross_partition_query=True))
            if facet_option is None:
                # un-segmented bars, summed over each date or date_hr slot
                prep_df = raw_df.groupby(period_name)[metric].sum().reset_index()
                figure = px.bar(prep_df, x=period_name, y=metric)
            else:
                prep_df = raw_df.groupby([period_name, facet_option])[metric].sum().reset_index()
                figure = px.bar(prep_df, x=period_name, y=metric, color=facet_option)
        
        return [new_facet_options, facet_option, new_filter_by_options, filter_by_option, new_filter_value_options, filter_value_option, figure]

    return app.server
