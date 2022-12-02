import os
from pathlib import Path

import pkg_resources

"""
Local path to store/access files
"""
# ROOT_DIR = Path(__file__).parent.parent # not used when packaged
DATA_FOLDER = Path(pkg_resources.resource_filename("eur_energy", 'data'))
RAW_DATA_FOLDER = DATA_FOLDER / "raw"
FORMATTED_DATA_FOLDER = DATA_FOLDER / "formatted"
SCHEMA_FOLDER = DATA_FOLDER / "schema"
IMAGES_PATH = DATA_FOLDER / "images"
# make sure folders exist
os.makedirs(RAW_DATA_FOLDER, exist_ok=True)
os.makedirs(FORMATTED_DATA_FOLDER, exist_ok=True)

"""
URL to access/download the Integrated Database of the European Energy Sector (IDEES) from the JRC, European Commission
"""
jrc_idees_url = 'https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/JRC-IDEES/JRC-IDEES-2015_v1/'

"""
Variables specific to JRC files data extraction 
"""
units_dict = {
    'Industry': {
        'activity': 'kt',
        'final energy consumption': 'ktoe',
        'useful energy demand': 'ktoe',
        'CO2 emissions': 'kt of CO2'
    }
}
jrc_idees_industry_dict = {
    'Iron and steel': 'ISI',
    'Non Ferrous Metals': 'NFM',
    'Chemicals Industry': 'CHI',
    'Non-metallic mineral products': 'NMM',
    'Pulp, paper and printing': 'PPA'
}
jrc_idees_key_categories = [
    'Physical output', "Installed capacity",
    'Capacity investment', 'Decommissioned capacity',
    'Idle capacity'
]
jrc_idees_industry_subcategories = {
    "Iron and steel": ["Integrated steelworks", "Electric arc"],
    'Non Ferrous Metals': [
        'Alumina production',
        {'Aluminium production': ["Aluminium - primary production", "Aluminium - secondary production"]},
        "Other non-ferrous metals"
    ],
    'Chemicals Industry': [
        "Basic chemicals",  # "Basic chemicals",
        "Other chemicals",  # (kt ethylene eq.)
        "Pharmaceutical products etc."  # (kt ethylene eq.)
    ],
    "Non-metallic mineral products": [
        "Cement", "Ceramics & other NMM", "Glass production"
    ],
    "Pulp, paper and printing": [
        {"Paper and paper products": ["Pulp production", "Paper production"]},
        "Printing and media reproduction"
    ]
}
