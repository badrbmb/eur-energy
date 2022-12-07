import numpy as np
import requests
import streamlit as st
from millify import millify
from streamlit_lottie import st_lottie

from eur_energy.ember.processor import get_electricity_carbon_intensity
from eur_energy.model.countries import Country, DeltaCountry
from eur_energy.visualisation.figure_factory import (
    COLOR_DICT_ISO2,
)
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


# init. in session state previous base value for fast re-loading
if 'base_value' not in st.session_state:
    st.session_state['base_value'] = None


def reset_base_value():
    st.session_state['base_value'] = None
    # set country default emission intensity
    _default_value = df_electricity_defaults[
        (df_electricity_defaults['Country code'] == country.iso3) &
        (df_electricity_defaults['Year'] == year)
        ]['Value'].values[0]  # expressed in kgCO2/GJ
    country.set_grid_carbon_intensity(_default_value)


def set_base_value():
    st.session_state['base_value'] = max(st.session_state['carbon-intensities-select'])


def convert_base_value():
    if st.session_state['base_value'] is not None:
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
        st.session_state['base_value'] *= factor


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

    # create slider
    _, col2, col3 = st.columns([1, 2, 1])

    with col3:
        unit = st.radio('Unit', options=['kgCO2/GJ', 'kgCO2/kWh'], key='unit-select', on_change=convert_base_value)

        if unit == 'kgCO2/GJ':
            # no need to convert
            conversion_factor = 1
        elif unit == 'kgCO2/kWh':
            conversion_factor = 0.0036  # 1kWh = 0.0036 GJ
        else:
            raise NotImplementedError(f'{unit} not handled!')

    with col2:
        _max = float(np.ceil(df_electricity_defaults['Value'].max())) * conversion_factor
        if st.session_state['base_value'] is None:
            # get country default value
            _default_val = float(country.grid_carbon_intensity) * conversion_factor
        else:
            # load stored value from session state and make sure to convert it to kgCO2/GJ
            _default_val = float(st.session_state['base_value'])

        _step = np.round(10. * conversion_factor, 2)

        # TODO save/load value for lower bound of slider too?
        carbon_intensities = st.slider(
            label='Carbon intensity electricity:',
            min_value=0.,
            max_value=_max,
            value=[0., _default_val],
            step=_step,
            key='carbon-intensities-select',
            on_change=set_base_value,
            help="**The upper bound** of the slider corresponds to the **base electricity carbon intensity** - "
                 "a default value is automatically populated using best available data for the given geography-year, but can be adjust to reflect your assumptions."
                 "**The lower bound** of the slider corresponds to the low carbon intensity scenario to simulate."
        )

        # convert back to kgCO2/GJ for the rest of modelling
        carbon_intensities = [t * 1 / conversion_factor for t in carbon_intensities]
        # assign values to each country object
        new_value = min(carbon_intensities)  # new value to be set as comparison
        base_value = max(carbon_intensities)  # value to serve as a reference

    # re-assign country intensity
    country.set_grid_carbon_intensity(base_value)

    # create DellaCountry object of the selected geography and modify the caron intensity of its electricity
    delta_country = DeltaCountry(country=country)
    delta_country.set_grid_carbon_intensity(new_value)

    # get total values card
    _, col2, _ = st.columns([2, 1, 2])
    with col2:
        _change = round(delta_country.delta_emissions_change * 100, 1)
        total_emissions_card = st.metric(
            label='Total emissions',
            value=millify(delta_country.total_emissions, prefixes=[' tCO2', ' ktCO2', ' mtCO2']),
            delta=f"{_change}% compared to ref.",
            delta_color='normal'
        )


elif scenario == 'Fuel-switching':

    # show not yet implemented message
    _, col2, _ = st.columns([1, 2, 1])

    with col2:
        lottie_json = load_lottie_url(LOTTIE_URL)
        st_lottie(lottie_json, speed=40)
