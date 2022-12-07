import re

import pandas as pd
import streamlit as st
from millify import millify

from eur_energy.model.countries import Country
from eur_energy.model.processes import VALID_SUB_SECTOR_PROCESSES
from eur_energy.visualisation.figure_factory import (
    COLOR_DICT_ISO2,
    generate_country_fuel_demand,
    generate_country_demand_by_sub_sector,
    generate_emission_intensities_by_sub_sector,
    generate_country_emissions_by_sub_sector,
    generate_sub_sector_summary_plot,
    generate_process_details_graph
)
from eur_energy.visualisation.utils import load_datasets, load_country_data

st.set_page_config(
    page_title="Assess",
    page_icon="🎯",
    layout="wide"
)


@st.cache(allow_output_mutation=True, ttl=24 * 3600)
def load_sub_sector_summary(sub_sector):
    df = pd.DataFrame(sub_sector.get_summary(add_fuels=False))
    df = df.reset_index().melt(id_vars='index', var_name='process')
    df.rename(columns={'index': 'variable'}, inplace=True)
    df['unit'] = df['variable'].apply(lambda x: re.findall('\((.*?)\)', x)[0])
    df['variable'] = df['variable'].apply(lambda x: re.sub('\((.*?)\)', '', x).strip())

    return df


def get_country_name(iso2_code):
    return Country(iso2_code).country_name


def get_process_information(process, variable):
    # get related information
    if variable == 'Energy consumption intensity':
        _property = 'fuel_intensity_details'
        _unit = 'GJ/tonne'
        _rounding = 2
    elif variable == 'Emission intensity':
        _property = 'emission_intensity_details'
        _unit = 'kgCO2/tonne'
        _rounding = 0
    else:
        raise NotImplementedError(f'{variable} not handled!')
    # load data
    data = getattr(process, _property)

    return data, _property, _unit, _rounding


def generate_text(df, country_name, year, sub_sector=None, category='fuel', variable=None):
    # fill text based on category
    if category == 'fuel_demand':
        _lookup = 'fuel'
        _fill_text = "the main fuel"
        _fill_text2 = ' consumed'
    elif category == 'sub_sector_demand':
        _lookup = 'sub_sector'
        _fill_text = "the major energy consumer"
        _fill_text2 = ''
    elif category == 'sub_sector_emissions':
        _lookup = 'sub_sector'
        _fill_text = "the major industrial emitter"
        _fill_text2 = ''
    elif category == 'sub_sector_emission_intensity':
        _lookup = 'sub_sector'
        _fill_text = "the major emitter"
        _fill_text2 = 'by unit of production'
    elif category == 'sub_sector_summary_variable':
        _lookup = 'process'
        _fill_text = "the major contributor"
        _fill_text2 = f"by **{variable.lower()}**"
    elif category == 'process_summary_variable':
        _lookup = 'category'
        _fill_text = "the major contributor"
        _fill_text2 = f"for the total **{variable.lower()}**"
    else:
        raise NotImplementedError(f"category={category} not implemented!")

    # Demand by fuel
    df['share'] = df['value'] / df['value'].sum()
    df.sort_values('share', ascending=True, inplace=True)
    df['cumulative_share'] = df['share'].cumsum()

    # get list of fuels accounting for more than 50%
    category_list = df[df['cumulative_share'] >= .5].copy()

    if len(category_list) == 0:
        # take the first  element only
        category_list = df.tail(1).set_index(_lookup).to_dict()['share']
    else:
        category_list = category_list.set_index(_lookup).to_dict()['share']
    if len(category_list) > 1:
        category_list = [f"'{u}' [{round(v * 100, 1)}%]" for u, v in category_list.items()]
        category_list = '**' + ', '.join(category_list[:-1]) + f' and {category_list[-1]}** are {_fill_text}s'
    else:
        _key = list(category_list.keys())[0]
        category_list = f"**'{_key}' [{round(category_list[_key] * 100, 2)}%]** is {_fill_text}"

    if sub_sector is not None:
        return f"""
        {category_list} {_fill_text2} in **{country_name}** by the **{sub_sector}** in **{year}**
        """
    else:
        return f"""
                {category_list} {_fill_text2} in **{country_name}** in **{year}**
                """


# get dropdown options
sub_sector_names = sorted(VALID_SUB_SECTOR_PROCESSES.keys())

# define page layout
st.write('# Assess')

st.markdown("""
- Start by choosing a `geography` and a `year` from the dropdown options below.
- Then choose a `sub-sector` for more general information.
- Finally pick an industrial `process` to derive insights from granular data on each stage of the manufacturing process.
""")

st.markdown("""---""")

# organise layout in columns
_, col2, col3, _ = st.columns([2, 2, 2, 2])

with col2:
    iso2s = [t for t in sorted(list(set(COLOR_DICT_ISO2.keys()))) if t not in ['EU27+UK', 'EU28']]
    # add EU28 at the top of the list
    iso2s = ['EU28'] + iso2s
    iso2 = st.selectbox('Geography:', options=iso2s, key='geography-select-assess',
                        format_func=get_country_name)
    # get the country name
    country_name = get_country_name(iso2)

with col3:
    years = list(range(2000, 2016))
    year = st.selectbox('Year:', options=years, index=len(years) - 1, key='year-select')

# load the selected country
with st.spinner(text='Loading selected geography information ...'):
    # load datasets
    activity_df, demand_df, emission_df = load_datasets(ref_iso2=iso2, ref_year=year)
    country = load_country_data(
        ref_iso2=iso2, ref_year=year, demand_df=demand_df, activity_df=activity_df, emission_df=emission_df
    )

if country is not None:
    # derive fuel demand and total emissions

    st.write('##')
    # display metrics

    # load data
    total_final_demand = country.total_fuel_demand
    total_emissions = country.total_emissions

    _, col2, col3, _ = st.columns([2, 2, 2, 2])

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

    # fuel demand section broken down by fuel and by sub-sector
    st.write("#### Final energy demand ...")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.write('##### ... by fuel')
        df_fuel_demand = pd.DataFrame(country.get_total_fuel_demand())
        # generate text-
        text_card = generate_text(
            df_fuel_demand,
            country_name=country_name,
            year=year,
            category='fuel_demand'
        )
        st.info(text_card)
        # generate fig
        fig = generate_country_fuel_demand(df_fuel_demand)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.write('##### ... by sub-sector')
        df_fuel_demand_sub_sectors = pd.DataFrame(country.get_total_fuel_demand_all_sub_sectors())
        # generate text
        text_card = generate_text(
            df_fuel_demand_sub_sectors,
            country_name=country_name,
            year=year,
            category='sub_sector_demand'
        )
        st.warning(text_card)
        # generate fig
        fig = generate_country_demand_by_sub_sector(df_fuel_demand_sub_sectors)
        st.plotly_chart(fig, use_container_width=True)

    # emissions section broken down by sub-sector
    st.write("#### Sub-sector breakdown by ...")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.write('##### ... total emissions')
        df_emissions = pd.DataFrame(country.get_total_emissions())
        # generate text
        text_card = generate_text(
            df_emissions,
            country_name=country_name,
            year=year,
            category='sub_sector_emissions'
        )
        st.warning(text_card)
        # generate fig
        fig = generate_country_emissions_by_sub_sector(df_emissions)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.write('##### ... emission intensities')
        df_efs = pd.DataFrame(country.get_total_emission_intensity())
        # generate text
        text_card = generate_text(
            df_efs,
            country_name=country_name,
            year=year,
            category='sub_sector_emission_intensity'
        )
        st.info(text_card)
        # generate fig
        fig = generate_emission_intensities_by_sub_sector(df_efs)
        st.plotly_chart(fig, use_container_width=True)

    # sub-sector session
    st.markdown("""---""")
    _, col2, _ = st.columns([4, 3, 4])
    with col2:
        sub_sector_name = st.selectbox('Sub-sector:', options=sub_sector_names, key='sub-sector-select-assess')

    # load the sub-sector information
    sub_sector = country.get_sub_sector(sub_sector_name)
    df_sub_sector_summary = load_sub_sector_summary(sub_sector)

    col1, col2 = st.columns([1, 3])

    with col1:
        variable = st.radio('Variable:', options=df_sub_sector_summary['variable'].unique(),
                            key='variable-select-assess')

        st.write('##')

        # filter variable
        df_sub_sector_variable = df_sub_sector_summary[df_sub_sector_summary['variable'] == variable].copy()

        # generate text
        text_card = generate_text(
            df_sub_sector_variable,
            country_name=country_name,
            year=year,
            category='sub_sector_summary_variable',
            variable=variable
        )
        st.info(text_card)

    with col2:
        fig = generate_sub_sector_summary_plot(df_sub_sector_variable, variable)
        st.plotly_chart(fig, use_container_width=True)

    # display each process general information

    st.markdown("""---""")
    _, col2, _ = st.columns([4, 3, 4])
    with col2:
        process_name = st.selectbox('Process:', options=sorted(sub_sector.process_names),
                                    key='process-select-assess')

        process = sub_sector.get_process(process_name)

    col1, col2 = st.columns([1, 3])

    with col1:
        st.write('##')
        variable = st.selectbox(label='Variable:', options=['Energy consumption intensity', 'Emission intensity'],
                                key='variable-process-select-assess')

        # get process information
        data, _property, _unit, _rounding = get_process_information(process, variable)

        # generate text
        st.write('#')
        text_card = generate_text(
            pd.DataFrame(data),
            country_name=country_name,
            year=year,
            category='process_summary_variable',
            variable=variable
        )
        st.warning(text_card)

    with col2:
        fig = generate_process_details_graph(data, variable, rounding=_rounding, unit=_unit)
        st.plotly_chart(fig, use_container_width=True)

    with st.sidebar:
        st.write('Current selection:')
        st.text_input(label='Geography:', value=country_name, disabled=True)
        st.text_input(label='Reference year:', value=year, disabled=True)
        st.text_input(label='Industry sub-sector:', value=sub_sector_name, disabled=True)
        st.text_input(label='Industrial process:', value=process_name, disabled=True)
