import json
import re

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from millify import millify

from eur_energy import config
from eur_energy.model.countries import Country
from eur_energy.model.processes import VALID_SUBSECTOR_PROCESSES

st.set_page_config(
    page_title="Explore",
    page_icon="🔍",
    layout="wide"
)

# variables to display
dict_variable_types = {
    'Production': ['Capacity investment',
                   'Decommissioned capacity',
                   'Idle capacity',
                   'Installed capacity',
                   'Physical output', ],
    'Emissions': [
        'CO2 emissions',
        'CO2 emissions intensity',
    ],
    'Energy demand': [
        'final energy consumption',
        'final energy consumption intensity',
        'useful energy demand',
        'useful energy demand intensity'
    ]
}

# colors by country
color_dict = {
    'AT': '#2E91E5',
    'BE': '#E15F99',
    'BG': '#1CA71C',
    'CY': '#FB0D0D',
    'CZ': '#DA16FF',
    'DE': '#222A2A',
    'DK': '#B68100',
    'EE': '#750D86',
    'EL': '#EB663B',
    'ES': '#511CFB',
    'EU28': '#00A08B',
    'EU27+UK': '#00A08B',
    'FI': '#FB00D1',
    'FR': '#FC0080',
    'HR': '#B2828D',
    'HU': '#6C7C32',
    'IE': '#778AAE',
    'IT': '#862A16',
    'LT': '#A777F1',
    'LU': '#620042',
    'LV': '#1616A7',
    'MT': '#DA60CA',
    'NL': '#6C4516',
    'PL': '#0D2A63',
    'PT': '#AF0038',
    'RO': '#2E91E5',
    'SE': '#E15F99',
    'SI': '#1CA71C',
    'SK': '#FB0D0D',
    'UK': '#DA16FF'
}


@st.cache
def load_borders():
    path = config.DATA_FOLDER / 'NUTS_RG_60M_2021_4326.geojson'

    with open(path, 'r') as f:
        data = json.load(f)

    # keep only country level shapes
    features = [t for t in data['features'] if t['properties']['LEVL_CODE'] == 0]
    data['features'] = features

    return data


@st.cache
def load_dataset():
    # load data
    df_demand = pd.read_csv(config.DATA_FOLDER / 'formatted/demand_data.csv', index_col=0)
    df_activity = pd.read_csv(config.DATA_FOLDER / 'formatted/activity_data.csv', index_col=0)
    df_emissions = pd.read_csv(config.DATA_FOLDER / 'formatted/emission_data.csv', index_col=0)

    df_dem = df_demand.groupby(
        ['iso2', 'year', 'sector', 'sub_sector', 'process', 'variable', 'unit']).sum().reset_index()
    df_act = df_activity.groupby(
        ['iso2', 'year', 'sector', 'sub_sector', 'process', 'variable', 'unit']).sum().reset_index()
    df_emi = df_emissions.groupby(
        ['iso2', 'year', 'sector', 'sub_sector', 'process', 'variable', 'unit']).sum().reset_index()

    df = pd.concat([df_dem, df_act, df_emi], axis=0)

    return df


def generate_heatmap(df_map, variable_to_show, country_borders):
    df_show_map = df_map[
        (df_map['variable'] == variable_to_show) &
        # exclude EU28
        (df_map['iso2'] != 'EU28')
        ].copy()

    unit = df_show_map['unit'].values[0]

    fig = px.choropleth_mapbox(
        df_show_map, geojson=country_borders, color="value",
        animation_frame="year",
        mapbox_style="carto-positron",
        color_continuous_scale='Reds',
        zoom=2.2, center={"lon": 5.8849601082954734, "lat": 55.37918894782564},  # roughly center of europe
        locations="iso2", featureidkey="properties.FID",
        hover_data=["country", "sub_sector", "process", 'variable', 'unit'],
        labels={'value': f"<b>{process}</b><br>{variable_to_show}<br>({unit})"},
        range_color=(min(df_show_map['value']), max(df_show_map['value']))
    )

    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        coloraxis_colorbar_x=0.05,
        coloraxis_colorbar_bgcolor="rgba(155,155,155, .5)",
        height=600,
    )

    return fig


def filter_df():
    df_out = df[
        (df['sub_sector'] == sub_sector) &
        (df['process'] == process)
        ].copy()

    # filter producing iso2s only and chosen variable
    iso2_to_show = df_out[
        (df_out['variable'] == 'Physical output') & (df_out['value'] > 0)
        ]['iso2'].unique()

    df_out = df_out[df_out['iso2'].isin(iso2_to_show)].copy()

    # assign country name
    df_out['country'] = df_out['iso2'].apply(lambda x: Country(iso2=x).country_name)

    return df_out


def generate_cumulative_chart(df_data, reference_year, variable_to_show, colors_dict, add_annotations=True):
    df_stats = df_data[
        (df_data['year'] == reference_year) &
        (df_data['variable'].isin(['Physical output', variable_to_show])) &
        # exclude EU28
        (df_data['iso2'] != 'EU28')
        ].copy()
    # append unit to each variable
    df_stats['variable'] = df_stats.apply(lambda x: f"{x['variable']} ({x['unit']})", axis=1)
    df_stats = df_stats.pivot('iso2', 'variable', 'value').reset_index()
    # convert physical output to Mt
    df_stats['Physical output (tonne)'] *= 1 / 1e6
    df_stats.rename(columns={'Physical output (tonne)': 'Physical output (million tonnes)'}, inplace=True)

    # assign colors by country
    df_stats['colour'] = df_stats['iso2'].replace(colors_dict)

    # assign country
    df_stats['country'] = df_stats['iso2'].apply(lambda x: Country(iso2=x).country_name)

    col_x = "Physical output (million tonnes)"
    col_y = f"{variable_to_show} (GJ/tonne)"
    # col_y = 'useful energy demand intensity (GJ/tonne)'
    col_y_unit = re.findall('\((.*?)\)', col_y)[0]

    # sort values
    df_stats.sort_values(col_y, ascending=True, inplace=True)

    # add cumulative column
    df_stats['cumsum'] = df_stats[col_x].cumsum()

    # get quantile 10%
    q10 = np.quantile(df_stats[col_y], q=.1)

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=df_stats['cumsum'] - df_stats[col_x],
            y=df_stats[col_y],
            width=df_stats[col_x],
            marker_color=df_stats["colour"],
            marker=dict(opacity=.8),
            offset=0,
            textposition="auto",
            text=df_stats["iso2"],
            textfont=dict(color="white"),
            customdata=df_stats[col_x],
            hovertext=df_stats['country'],
            hovertemplate="%{hovertext}<br>$VAR1: %{customdata:.2f}<br><extra>$VAR2 <br> %{y:.2f}</extra>".replace(
                '$VAR1', col_x).replace('$VAR2', col_y)
        )
    )

    fig.add_hline(
        y=q10, line=dict(color='red', dash='dot'),
        annotation_text=f"<b>Top 10% ~ {round(q10, 2)} {col_y_unit}</b>", annotation_position='bottom right',
        annotation=dict(bgcolor='white', opacity=.7, font=dict(color="#2e2f31")),
    )

    fig.update_layout(
        xaxis=dict(title=f"Cumulative {col_x.lower()}"),
        yaxis=dict(title=col_y.replace(' intensity', '')),
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
    )

    if add_annotations:
        # add annotation biggest producer
        annotation_entry = df_stats[df_stats[col_x] == df_stats[col_x].max()].iloc[0].to_dict()
        fig.add_annotation(
            x=annotation_entry['cumsum'] - 0.5 * annotation_entry[col_x],
            ax=-60,
            ay=-70,
            y=annotation_entry[col_y],
            text=f"<b>{annotation_entry['country']}</b>, <b>the biggest producer in EU27 + UK</b>,<br>has a {col_y.replace(f'({col_y_unit})', '')}<br>of <b>{round(annotation_entry[col_y], 2)} {col_y_unit}</b>",
            showarrow=True,
            arrowhead=1,
            arrowsize=1.5,
            align='left',
            bgcolor="#e1e4e1",
            opacity=0.8,
            font=dict(color="#2e2f31"),
            arrowcolor="#9b9b9b",
        )

        # add annotation for bad performer versus q10
        last_entry = df_stats.iloc[-1].to_dict()
        last_entry['delta'] = round((last_entry[col_y] - q10) / q10 * 100, 2)

        fig.add_annotation(
            x=last_entry['cumsum'] - 0.5 * last_entry[col_x],
            ax=-200,
            ay=-20,
            y=last_entry[col_y],
            text=f"<b>{last_entry['country']}</b> {col_y.replace(f'({col_y_unit})', '')}<br>is <b>{round(last_entry['delta'])}% higher<br>than the top 10% countries</b> in EU27+UK",
            showarrow=True,
            arrowhead=1,
            arrowsize=1.5,
            align='left',
            bgcolor="#e1e4e1",
            opacity=0.8,
            font=dict(color="#2e2f31"),
            arrowcolor="#9b9b9b",
        )

    return fig


def generate_text_map(df_in, variable_to_show):
    # get the highest value description
    df_text = df_in[df_in['variable'] == variable_to_show].copy()
    _max_value = df_text[df_text['iso2'] != 'EU28']['value'].max()
    info_dict = df_text[df_text['value'] == _max_value].iloc[0].to_dict()
    # store unit
    _unit = info_dict['unit']
    _variable = info_dict['variable'].lower().replace('co2', 'CO2')
    _process = info_dict['process']
    _value = millify(round(info_dict['value']), precision=1)
    info_text1 = f"""
    **{info_dict['country']}** had the **highest {_variable}** from "{_process}",
    peaking at **{_value} {_unit}** in **{info_dict['year']}**.
    """

    # get evolution of across all EU27 + UK countries
    df_text.sort_values('year', inplace=True)
    _start = df_text['year'].min()
    _end = df_text['year'].max()
    df_average = df_text.loc[df_text['iso2'] == 'EU28', 'value'].copy()
    _rel_delta = round(((df_average.iloc[-1] - df_average.iloc[0]) * 100 / df_average.iloc[0]), 2)
    _move = 'decreased' if _rel_delta < 0 else 'increased'
    info_text2 = f"""
    From {_start} to {_end}, {_variable} from "{_process}" **{_move}** by **{abs(_rel_delta)}%** across all 
    EU27 + UK countries.
    """

    return info_text1, info_text2


# Load the formatted JRC IDEES dataset
df = load_dataset()

# load borders
geoshapes = load_borders()

# get dropdown options
sub_sector_names = sorted(VALID_SUBSECTOR_PROCESSES.keys())

# define page layout
st.write('# Explore')

st.write("Choose a `sub-sector` and an industrial `process` from the dropdown options below, "
         "and explore the evolution of production and energy demand from the European industry.")

st.markdown("""---""")

# organise layout in columns
col1, col2 = st.columns([2, 2])

with col1:
    sub_sector = st.selectbox('Sub-sector:', options=sub_sector_names, key='sub-sector-select')

# define choice of sectors
with col2:
    process = st.selectbox('Process:', options=VALID_SUBSECTOR_PROCESSES[sub_sector], key='process-select')

# divider
st.markdown("""---""")

# map area

st.write(f'#### EU27 + UK heatmap')
st.write('###')

col1, col2 = st.columns([2, 3])

with col1:
    variable_category = st.radio(label='Category:', options=sorted(dict_variable_types.keys()))

    variable = st.selectbox('Variable:', options=dict_variable_types[variable_category], key='variable-select')

    # filter df based on selection
    df_filter = filter_df()

    info1, info2 = generate_text_map(df_filter, variable_to_show=variable)

    st.warning(info2)
    st.write('#####')
    st.info(info1)

with col2:
    if not df_filter.empty:
        # display map
        fig = generate_heatmap(df_map=df_filter, variable_to_show=variable, country_borders=geoshapes)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error('Nothing to display! Try another set of parameters', icon='🚨')

st.write('###')
st.write(f'#### Cumulative production vs. Energy demand')

st.write('###')
col1, col2, col3 = st.columns([1, 2, 1])

with col1:
    years = sorted(list(df['year'].unique()))
    year = st.selectbox('Reference year:', options=years, index=len(years) - 1, key='year-select')

with col2:
    variable = st.selectbox('Demand variable:',
                            options=['final energy consumption intensity', 'useful energy demand intensity'],
                            key='demand-variable-select')

with col3:
    st.write('##')
    show_annotations = st.checkbox(label='Show annotations', value=True)

fig = generate_cumulative_chart(df_filter, reference_year=year, variable_to_show=variable, colors_dict=color_dict,
                                add_annotations=show_annotations)
st.plotly_chart(fig, use_container_width=True)

# add side-bar
with st.sidebar:
    st.write('Current selection:')
    st.text_input(label='Industry sub-sector:', value=sub_sector, disabled=True)
    st.text_input(label='Industrial process:', value=process, disabled=True)
