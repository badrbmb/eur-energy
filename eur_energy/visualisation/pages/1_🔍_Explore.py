import json

import pandas as pd
import streamlit as st
from millify import millify

from eur_energy import config
from eur_energy.model.countries import Country
from eur_energy.model.processes import VALID_SUBSECTOR_PROCESSES
from eur_energy.visualisation.figure_factory import generate_heatmap, generate_cumulative_chart, COLOR_DICT_ISO2

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


@st.cache(ttl=24 * 3600)
def load_borders():
    path = config.DATA_FOLDER / 'NUTS_RG_60M_2021_4326.geojson'

    with open(path, 'r') as f:
        data = json.load(f)

    # keep only country level shapes
    features = [t for t in data['features'] if t['properties']['LEVL_CODE'] == 0]
    data['features'] = features

    return data


@st.cache(ttl=24 * 3600)
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

    return pd.concat([df_dem, df_act, df_emi], axis=0)


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
        fig = generate_heatmap(df_map=df_filter, variable_to_show=variable, country_borders=geoshapes, process=process)
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
                            key='demand-variable-select',
                            help="`Final energy consumption` is the total energy consumed by end users; "
                                 "it is the energy which reaches the final consumer's door and excludes that "
                                 "which is used by the energy sector itself."
                                 "\n"
                                 "\n"
                                 "`Useful energy consumption` is the energy that goes towards the desired output "
                                 "of the end-use application; this is impacted by the efficiency of the process "
                                 "consuming the delivered energy to.")

with col3:
    st.write('##')
    show_annotations = st.checkbox(label='Show annotations', value=True)

fig = generate_cumulative_chart(df_filter, reference_year=year, variable_to_show=variable, colors_dict=COLOR_DICT_ISO2,
                                add_annotations=show_annotations)
st.plotly_chart(fig, use_container_width=True)

# add sidebar
with st.sidebar:
    st.write('Current selection:')
    st.text_input(label='Industry sub-sector:', value=sub_sector, disabled=True)
    st.text_input(label='Industrial process:', value=process, disabled=True)
