import streamlit as st

from eur_energy.model.countries import Country
from eur_energy.model.processes import VALID_SUBSECTOR_PROCESSES
from eur_energy.visualisation.figure_factory import COLOR_DICT_ISO2

st.set_page_config(
    page_title="Assess",
    page_icon="🎯",
    layout="wide"
)

# get dropdown options
sub_sector_names = sorted(VALID_SUBSECTOR_PROCESSES.keys())

# define page layout
st.write('# Assess')

st.write("Choose a `sub-sector`, an industrial `process`, a `geography` and a `year` from the dropdown options below, "
         "and derive insights from granular data on each stage of the manufacturing process.")

st.markdown("""---""")

# organise layout in columns
col1, col2, col3, col4 = st.columns([2, 2, 2, 1])

with col1:
    sub_sector = st.selectbox('Sub-sector:', options=sub_sector_names, key='sub-sector-select')

with col2:
    process = st.selectbox('Process:', options=VALID_SUBSECTOR_PROCESSES[sub_sector], key='process-select')

with col3:
    countries = sorted(list(set([Country(t).country_name for t in COLOR_DICT_ISO2.keys()])))
    geography = st.selectbox('Geography:', options=countries, key='geography-select')

with col4:
    years = list(range(2000, 2016))
    year = st.selectbox('Year:', options=years, index=len(years) - 1, key='year-select')

with st.sidebar:
    st.write('Current selection:')
    st.text_input(label='Industry sub-sector:', value=sub_sector, disabled=True)
    st.text_input(label='Industrial process:', value=process, disabled=True)
    st.text_input(label='Geography:', value=geography, disabled=True)
    st.text_input(label='Reference year:', value=year, disabled=True)
