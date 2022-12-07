import pandas as pd
import streamlit as st
from google.oauth2 import service_account
from streamlit.runtime.scriptrunner import RerunData, RerunException
from streamlit.source_util import get_pages

from eur_energy.model.composer import compose_country


def load_credentials():
    """
    Load service account credentials for Google cloud services
    Returns:

    """
    # Create API client.
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"]
    )
    return credentials


def hide_footer():
    """
    Hide streamlit footer (not used)
    Returns:
    """

    hide_streamlit_style = """
                <style>
                #MainMenu {visibility: hidden;}
                footer {visibility: hidden;}
                </style>
                """
    st.markdown(hide_streamlit_style, unsafe_allow_html=True)


def switch_page(page_name: str, main="🏠_Home.py"):
    """
    switch pages in multi-page app
    adapted from arnaudmiribel/streamlit-extras
    reference: https://github.com/arnaudmiribel/streamlit-extras/blob/main/src/streamlit_extras/switch_page_button/__init__.py
    Args:
        page_name: the target page name to witch to
        main: the basename of the file containing main streamlit app
    Returns:
    """

    def standardize_name(name: str) -> str:
        return name.lower().replace("_", " ")

    page_name = standardize_name(page_name)

    pages = get_pages(main)

    for page_hash, config in pages.items():
        if standardize_name(config["page_name"]) == page_name:
            raise RerunException(
                RerunData(
                    page_script_hash=page_hash,
                    page_name=page_name,
                )
            )

    page_names = [standardize_name(config["page_name"]) for config in pages.values()]

    raise ValueError(f"Could not find page {page_name}. Must be one of {page_names}")


def generate_card(wch_colour_box=(255, 255, 255), title_colour_font=(0, 0, 0), subtitle_colour_font=(0, 0, 0),
                  title_font_size=18, subtitle_font_size=14, opacity=1,
                  icon_name="fas fa-asterisk", icon_size='fa-2xl', title="Title", subtitle='Subtitle'):
    """
    Generate a box element in html with the specified CSS properties
    Args:
        wch_colour_box:
        title_colour_font:
        subtitle_colour_font:
        title_font_size:
        subtitle_font_size:
        opacity:
        icon_name:
        icon_size:
        title:
        subtitle:
    Returns:

    """
    # link pointing to font awesome icons
    lnk = '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.2.0/css/all.min.css" crossorigin="anonymous">'
    # populate html element
    htmlstr = f"""<p style='background-color: rgb({wch_colour_box[0]}, 
                                                  {wch_colour_box[1]}, 
                                                  {wch_colour_box[2]}, {opacity}); 
                            color: rgb({title_colour_font[0]}, 
                                       {title_colour_font[1]}, 
                                       {title_colour_font[2]}, {opacity}); 
                            font-size: {title_font_size}px; 
                            border-radius: 7px; 
                            padding-left: 12px; 
                            padding-top: 18px; 
                            padding-bottom: 18px; 
                            line-height:25px;'>
                            <i class='{icon_name} {icon_size}'; 
                            color: rgb({subtitle_colour_font[0]}, 
                                       {subtitle_colour_font[1]}, 
                                       {subtitle_colour_font[2]}, {opacity})></i>
                            </style>
                            <BR>
                            <BR>
                            <span style='color: rgb({title_colour_font[0]}, 
                                       {title_colour_font[1]}, 
                                       {title_colour_font[2]}, {opacity}); 
                            font-size: {title_font_size}px;'>{title}</span>
                            <BR>
                            <span style='font-size: {subtitle_font_size}px; 
                            margin-top: 0;
                            color: rgb({subtitle_colour_font[0]}, 
                                       {subtitle_colour_font[1]}, 
                                       {subtitle_colour_font[2]}, {opacity}); 
                            '>{subtitle}</span></p>"""

    return lnk + htmlstr


def generate_multiplier_prefixes(unit):
    """
    Generates suffixes for displaying pretty number using millify
    Args:
        unit:
    Returns:

    """
    if unit == 'GJ':
        multiplier = 1e9
        prefixes = [' kJ', ' MJ', ' GJ', ' TJ', ' PJ']
    elif unit == 'GJ/tonne':
        multiplier = 1e9
        prefixes = [' kJ/tonne', ' MJ/tonne', ' GJ/tonne', ' TJ/tonne', ' PJ/tonne']
    elif unit in ['tonne', 'tonnes']:
        multiplier = 1
        prefixes = [' kt', ' mt']
    elif unit == 'kgCO2':
        multiplier = 1
        prefixes = [' tCO2', ' ktCO2', ' mtCO2']
    elif unit == 'kgCO2/tonne':
        multiplier = 1
        prefixes = [' tCO2/tonne', ' ktCO2/tonne', ' mtCO2/tonne']
    else:
        raise NotImplementedError(f"unit={unit} not handled")

    return multiplier, prefixes


"""
Contact information
"""
CONTACT_EMAIL = 'badr.benb@gmail.com'

"""
Lottie animations
"""
LOTTIE_URL = "https://assets5.lottiefiles.com/packages/lf20_nbs5jzhd.json"


@st.experimental_memo(ttl=24 * 3600, max_entries=10)
def load_datasets(ref_iso2, ref_year):
    credentials = load_credentials()
    raw_query = f"""
        SELECT * FROM `eur-energy.JRC_IDEES.$TABLE`
        where iso2='{ref_iso2}' and year={ref_year}
        """
    activity_df = pd.read_gbq(query=raw_query.replace('$TABLE', 'activity_data'), credentials=credentials)
    demand_df = pd.read_gbq(query=raw_query.replace('$TABLE', 'demand_data'), credentials=credentials)
    emission_df = pd.read_gbq(query=raw_query.replace('$TABLE', 'emission_data'), credentials=credentials)

    return activity_df, demand_df, emission_df


@st.cache(allow_output_mutation=True, ttl=24 * 3600)
def load_country_data(ref_iso2, ref_year, demand_df, activity_df, emission_df):
    return compose_country(
        iso2=ref_iso2, year=ref_year, demand_df=demand_df, activity_df=activity_df, emission_df=emission_df
    )
