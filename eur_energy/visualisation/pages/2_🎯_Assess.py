import pandas as pd
import streamlit as st
from millify import millify

from eur_energy import config
from eur_energy.model.composer import compose_country
from eur_energy.model.countries import Country
from eur_energy.model.processes import VALID_SUBSECTOR_PROCESSES
from eur_energy.visualisation.figure_factory import COLOR_DICT_ISO2, generate_country_fuel_demand

st.set_page_config(
    page_title="Assess",
    page_icon="🎯",
    layout="wide"
)


@st.cache
def load_datasets():
    path = config.FORMATTED_DATA_FOLDER
    activity_df = None
    demand_df = None
    emission_df = None
    for p in path.glob('*.csv'):
        if 'activity_data' in p.name:
            activity_df = pd.read_csv(p)
        elif 'demand_data' in p.name:
            demand_df = pd.read_csv(p)
        elif 'emission_data' in p.name:
            emission_df = pd.read_csv(p)
        else:
            raise NotImplementedError(f'{p.name} not implemented!')

    return activity_df, demand_df, emission_df


def get_country_name(iso2_code):
    return Country(iso2_code).country_name


def generate_country_fuel_demand_text(df, country_name, year, sub_sector=None):
    # Demand by fuel
    df['share'] = df['value'] / df['value'].sum()
    df.sort_values('share', ascending=True, inplace=True)
    df['cumulative_share'] = df['share'].cumsum()

    # get list of fuels accounting for more than 50%
    fuel_list = df[df['cumulative_share'] >= .5].copy()

    if len(fuel_list) == 0:
        # take the first  element only
        fuel_list = df.tail(1).set_index('fuel').to_dict()['share']
    else:
        fuel_list = fuel_list.set_index('fuel').to_dict()['share']
    if len(fuel_list) > 1:
        fuel_list = [f"{u} [{round(v * 100, 2)}%]" for u, v in fuel_list.items()]
        fuel_list = ', '.join(fuel_list[:-1]) + f' and {fuel_list[-1]} are the main fuels'
    else:
        print('****')
        _key = list(fuel_list.keys())[0]
        fuel_list = f"**{_key} [{round(fuel_list[_key] * 100, 2)}%]** is the main fuel"

    if sub_sector is not None:
        return f"""
        {fuel_list} consumed in **{country_name}** by the **{sub_sector}** in **{year}**
        """
    else:
        return f"""
                {fuel_list} consumed in **{country_name}** in **{year}**
                """


# load datasets
activity_df, demand_df, emission_df = load_datasets()

# get dropdown options
sub_sector_names = sorted(VALID_SUBSECTOR_PROCESSES.keys())

# define page layout
st.write('# Assess')

st.markdown("""
- Start by choosing a `geography` and a `year` from the dropdown options below.
- Then choose a `sub-sector` for more general information.
- Finally pick an industrial `process` to derive insights from granular data on each stage of the manufacturing process.
""")

st.markdown("""---""")

# organise layout in columns
_, col2, col3, _ = st.columns([2, 1, 1, 2])

with col2:
    iso2s = sorted(list(set(COLOR_DICT_ISO2.keys())))
    iso2 = st.selectbox('Geography:', options=iso2s, key='geography-select',
                        format_func=get_country_name)

with col3:
    years = list(range(2000, 2016))
    year = st.selectbox('Year:', options=years, index=len(years) - 1, key='year-select')

# load the selected country
with st.spinner(text='Loading selected geography information ...'):
    country = compose_country(
        iso2=iso2, year=year, demand_df=demand_df, activity_df=activity_df, emission_df=emission_df
    )

    # derive fuel demand and total emissions
    df_fuel_demand = pd.DataFrame(country.get_total_fuel_demand())
    total_final_demand = df_fuel_demand['value'].sum()
    total_emissions = country.total_emissions

    st.write('##')
    # display metrics
    _, col2, col3, _ = st.columns([2, 1, 1, 2])

    with col2:
        st.metric(
            label="Total final energy demand",
            value=f"{millify(total_final_demand * 1e9, prefixes=[' kJ', ' MJ', ' GJ', ' TJ', ' PJ'])}",
        )
    with col3:
        st.metric(
            label="Total emissions",
            value=f"{millify(total_emissions, prefixes=[' tCO2', ' ktCO2', ' mtCO2'])}",
        )

    st.write("#### Final energy demand by fuel")

    # generate text
    text_fuel_demand = generate_country_fuel_demand_text(
        df_fuel_demand,
        country_name=get_country_name(iso2),
        year=year
    )
    st.info(text_fuel_demand)

    fig = generate_country_fuel_demand(df_fuel_demand)
    st.plotly_chart(fig, use_container_width=True)

st.markdown("""---""")
_, col2, _ = st.columns([2, 1, 2])
with col2:
    sub_sector = st.selectbox('Sub-sector:', options=sub_sector_names, key='sub-sector-select')

st.markdown("""---""")
_, col2, _ = st.columns([2, 1, 2])
with col2:
    process = st.selectbox('Process:', options=VALID_SUBSECTOR_PROCESSES[sub_sector], key='process-select')

with st.sidebar:
    st.write('Current selection:')
    st.text_input(label='Geography:', value=get_country_name(iso2), disabled=True)
    st.text_input(label='Reference year:', value=year, disabled=True)
    st.text_input(label='Industry sub-sector:', value=sub_sector, disabled=True)
    st.text_input(label='Industrial process:', value=process, disabled=True)
