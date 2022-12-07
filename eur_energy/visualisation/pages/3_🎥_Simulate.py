import numpy as np
import pandas as pd
import requests
import streamlit as st
from millify import millify
from streamlit_lottie import st_lottie

from eur_energy.ember.processor import get_electricity_carbon_intensity
from eur_energy.model.countries import Country, DeltaCountry
from eur_energy.visualisation.figure_factory import (
    COLOR_DICT_ISO2,
)
from eur_energy.visualisation.figure_factory import generate_dumbbell_scenario_chart
from eur_energy.visualisation.utils import (
    LOTTIE_URL,
    load_datasets,
    load_country_data
)


def get_country_name(iso2_code):
    return Country(iso2_code).country_name


@st.cache(ttl=24 * 3600)
def load_carbon_intensity_electricity_data():
    return get_electricity_carbon_intensity()


@st.cache(ttl=24 * 3600)
def get_default_carbon_intensity_electricity(df, iso3, ref_year):
    return df[
        (df['Country code'] == iso3) &
        (df['Year'] == ref_year)
        ]['Value'].values[0]  # expressed in kgCO2/GJ


@st.cache
def load_lottie_url(url: str):
    r = requests.get(url)
    if r.status_code != 200:
        return None
    return r.json()


def get_delta_summary(delta_country, variable, sub_sector):
    if variable == 'Total emissions':
        ref_col = 'Total emissions (kgCO2)'
    elif variable == 'Emission intensity':
        ref_col = 'Total emission intensity (kgCO2/tonne)'
    else:
        raise NotImplementedError(f"{variable} not handled!")

    summary1 = delta_country.ref_get_summary
    summary2 = delta_country.country.get_summary(add_fuels=False, return_df=True)

    df1 = summary1[[ref_col]].copy()
    df2 = summary2[[ref_col]].copy()

    df1.rename(columns={ref_col: 'reference'}, inplace=True)
    df2.rename(columns={ref_col: 'scenario'}, inplace=True)
    df_plot = pd.concat([df1, df2], axis=1)

    df_plot.reset_index(inplace=True)
    df_plot.rename(columns={'level_0': 'sub_sector', 'level_1': 'process'}, inplace=True)
    df_plot['change'] = round((df_plot['scenario'] - df_plot['reference']) * 100 / df_plot['reference'], 2)

    # filter sub-sector
    if sub_sector != 'All industries':
        df_plot = df_plot[df_plot['sub_sector'] == sub_sector].copy()

    return df_plot


# init. in session state previous base value for fast re-loading
if 'base_value_reference' not in st.session_state:
    st.session_state['base_value_reference'] = None


def reset_base_value():
    st.session_state['base_value_reference'] = None
    # set country default emission intensity
    _default_value = get_default_carbon_intensity_electricity(df_electricity_defaults, country.iso3, year)
    country.set_grid_carbon_intensity(_default_value)


def set_base_value():
    st.session_state['base_value_reference'] = st.session_state['carbon-intensities-select-reference']


def convert_base_value():
    if st.session_state['base_value_reference'] is not None:
        # 1kWh = 0.0036 GJ
        if st.session_state['unit-select'] == 'kgCO2/GJ':
            # convert back from kgCO2/kWh
            factor = 1 / 0.0036
        elif st.session_state['unit-select'] == 'kgCO2/kWh':
            # convert back from kgCO2/GJ
            factor = 0.0036
        else:
            raise NotImplementedError(f"{st.session_state['unit-select']} not handled!")
        # set value
        st.session_state['base_value_reference'] *= factor


st.set_page_config(
    page_title="Simulate",
    page_icon="🎥",
    layout="wide"
)

# define page layout
st.write('# Simulate')

st.markdown("""
- Start by choosing a scenario to simulate.
- Adjust the sliders according to your desired scenario.
- Your results will be automatically displayed in the section below.
""")

st.markdown("""---""")

_, col2, _ = st.columns([1, 2, 1])

with col2:
    scenario = st.selectbox(label='Choose a scenario', options=['Low carbon electricity', 'Fuel-switching'])

st.markdown("""---""")

# populate relevant templates based on scenario
if scenario == 'Low carbon electricity':

    # load default carbon emission intensity electricity values
    df_electricity_defaults = load_carbon_intensity_electricity_data()

    _, col2, col3, _ = st.columns([2, 2, 2, 2])

    with col2:
        iso2s = [t for t in sorted(list(set(COLOR_DICT_ISO2.keys()))) if t not in ['EU27+UK', 'EU28']]
        # add EU28 at the top of the list
        iso2s = ['EU28'] + iso2s
        iso2 = st.selectbox('Geography:', options=iso2s, key='geography-select-simulate',
                            format_func=get_country_name, on_change=reset_base_value)

    with col3:
        years = list(range(2000, 2016))
        year = st.selectbox('Base year:', options=years, index=len(years) - 1, key='year-select',
                            on_change=reset_base_value)

    # load the selected country
    with st.spinner(text='Loading selected geography information ...'):
        # load datasets
        activity_df, demand_df, emission_df = load_datasets(ref_iso2=iso2, ref_year=year)
        country = load_country_data(
            ref_iso2=iso2, ref_year=year, demand_df=demand_df, activity_df=activity_df, emission_df=emission_df
        )

    st.write('#')

    # create slider
    col1, col2, col3 = st.columns([2, 1, 1])

    with col2:
        unit = st.radio('Unit', options=['kgCO2/GJ', 'kgCO2/kWh'], key='unit-select', on_change=convert_base_value)

        if unit == 'kgCO2/GJ':
            # no need to convert
            conversion_factor = 1
        elif unit == 'kgCO2/kWh':
            conversion_factor = 0.0036  # 1kWh = 0.0036 GJ
        else:
            raise NotImplementedError(f'{unit} not handled!')

    with col2:
        reset_btn = st.button('Reset default values', on_click=reset_base_value)

    with col1:
        _max = float(np.ceil(df_electricity_defaults['Value'].max())) * conversion_factor
        if st.session_state['base_value_reference'] is None:
            # get country default value
            _default_value = get_default_carbon_intensity_electricity(
                df=df_electricity_defaults, iso3=country.iso3, ref_year=year
            ) * conversion_factor
        else:
            # load stored value from session state and make sure to convert it to kgCO2/GJ
            _default_value = float(st.session_state['base_value_reference'])

        _step = np.round(10. * conversion_factor, 2)

        base_value = st.slider(
            label='Reference carbon intensity electricity:',
            min_value=0.,
            max_value=_max,
            value=float(_default_value),
            step=_step,
            key='carbon-intensities-select-reference',
            on_change=set_base_value,
            help="This value set to a default value "
                 "automatically populated using best available data for **grid carbon intensity** in the given geography-year,"
                 " but can be adjust to reflect your own assumptions."
        )

        new_value = st.slider(
            label='Scenario carbon intensity electricity:',
            min_value=0.,
            max_value=base_value,
            value=0.,
            step=_step,
            key='carbon-intensities-select-scenario',
            on_change=set_base_value,
            help="This value corresponds to the low carbon intensity scenario to simulate."
        )

        # store values in dict for display
        stored_values = {
            'reference': round(base_value, 2),
            'scenario': round(new_value, 2),
            'unit': unit
        }

        # convert back to kgCO2/GJ for the rest of modelling
        new_value *= 1 / conversion_factor
        base_value *= 1 / conversion_factor

    with col3:
        # re-assign country intensity
        country.set_grid_carbon_intensity(base_value)

        # create DellaCountry object of the selected geography and modify the caron intensity of its electricity
        delta_country = DeltaCountry(country=country)
        delta_country.set_grid_carbon_intensity(new_value)

        # display metric change
        _change = round(delta_country.delta_emissions_change * 100, 1)
        reference_total_emissions_card = st.metric(
            label='Reference total emissions:',
            value=millify(delta_country.ref_total_emissions, prefixes=[' tCO2', ' ktCO2', ' mtCO2']),
        )
        scenario_total_emissions_card = st.metric(
            label='Scenario total emissions:',
            value=millify(delta_country.total_emissions, prefixes=[' tCO2', ' ktCO2', ' mtCO2']),
            delta=f"{_change}%",
            delta_color='normal'
        )

    st.write('##')
    # add industry details
    col1, col2 = st.columns([1, 3])
    with col1:
        sub_sector = st.selectbox('Filter sub-sector:', options=['All industries'] + country.sub_sector_names)

    with col2:
        variable = st.selectbox('Choose a variable to display:', options=['Total emissions', 'Emission intensity'])
        # plot dumbbell charts by process
        df_summary = get_delta_summary(delta_country, variable=variable, sub_sector=sub_sector)
        fig = generate_dumbbell_scenario_chart(df_summary, variable=variable, stored_values=stored_values)
        st.plotly_chart(fig, use_container_width=True)

elif scenario == 'Fuel-switching':

    # show not yet implemented message
    _, col2, _ = st.columns([1, 2, 1])

    with col2:
        lottie_json = load_lottie_url(LOTTIE_URL)
        st_lottie(lottie_json, speed=40)
