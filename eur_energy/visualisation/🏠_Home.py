import streamlit as st
from PIL import Image

from eur_energy import config
from eur_energy.visualisation.utils import switch_page, CONTACT_EMAIL

st.set_page_config(
    page_title="EUR-energy",
    page_icon=Image.open(config.IMAGES_PATH / 'icons8-power-plant-48.png'),
    layout="wide"
)

st.write("# Welcome to EUR-energy")

st.write('#')

with st.sidebar:
    st.write('# Questions or comments?')

    st.markdown(f'Feel free to drop me an email at <{CONTACT_EMAIL}>')

    st.write('#')

# explore description card
scenario_form = st.form(key='explore-card')
scenario_form.markdown(
    """
    ### Explore the dynamics of energy demand from the European industry
    
    From historical national data on physical outputs, to fuel consumption and emissions intensities, dive into 
    the specifics of major European industrial sectors covering iron & steel, non-metallic mineral products, 
    non-ferrous metals, pulp & paper, and the chemicals industry.   
    """
)
scenario_view = scenario_form.form_submit_button("🔍 Explore")
if scenario_view:
    switch_page("Explore")

# deep-dive description card
scenario_form = st.form(key='deep-dive-card')
scenario_form.markdown(
    """
    ### Derive insights from granular data on industrial sectors 
    
    Curious about which processing stage in the cement production is responsible for the most emissions? 
    Or how much gas is consumed at the iron reduction stage in the iron & steel sector in Germany? 
    
    Assess emission intensities and demand by fuel for each process within the major industrial sectors.    
    """
)
scenario_view = scenario_form.form_submit_button("🎯 Assess")
if scenario_view:
    switch_page("Assess")

# scenario card
scenario_form = st.form(key='scenario-card')
scenario_form.markdown(
    """
    ### Evaluate alternative scenarios for fuel demand 

    Ever wondered what is the fuel-switching potential for the chemical industry? 
    Or what would be the impact of low carbon electricity on the total emissions of aluminium smelters? 

    Simulate alternative fuel demand options for major industrial sectors and analyse the associated impacts 
    on emissions.  
    """
)
scenario_view = scenario_form.form_submit_button("🎥 Simulate")
if scenario_view:
    switch_page("Simulate")

st.markdown(
    """
     ### Attribution

    This app leverages data from multiple sources: 

    - [The JRC Integrated Database of the European Energy System](https://publications.jrc.ec.europa.eu/repository/handle/JRC112474), published by the European Commission
    - [Yearly electricity data](https://ember-climate.org/data-catalogue/yearly-electricity-data/), published by EMBER
    - [The Nomenclature of territorial units for statistics](https://ec.europa.eu/eurostat/web/gisco/geodata/reference-data/administrative-units-statistical-units/nuts), published by eurostat
    - [Greenhouse Gas Emissions from Energy](https://iea.blob.core.windows.net/assets/78ca213f-171e-40ed-bf7e-c053d4376e79/WORLD_GHG_Documentation.pdf), published by the IEA
    - favicon by [icon8](https://icons8.com/)
"""
)
