import requests
import streamlit as st
from streamlit_lottie import st_lottie

from eur_energy.visualisation.utils import LOTTIE_URL

st.set_page_config(
    page_title="Simulate",
    page_icon="🎥",
    layout="wide"
)

# define page layout
st.write('# Simulate')

st.write("")

st.markdown("""---""")


@st.cache
def load_lottie_url(url: str):
    r = requests.get(url)
    if r.status_code != 200:
        return None
    return r.json()


_, col2, _ = st.columns([1, 2, 1])

with col2:
    lottie_json = load_lottie_url(LOTTIE_URL)
    st_lottie(lottie_json, speed=40)
