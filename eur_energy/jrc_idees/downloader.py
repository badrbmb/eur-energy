import logging
import os
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from eur_energy import config

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


def download_idees_zip_files(url: str = config.jrc_idees_url, out_folder: Path = config.RAW_DATA_FOLDER,
                             update: bool = False):
    """
    Downloads and unzips files from the JRC-opendata website.
    For more information on the data source, refer to the methodological note:
    https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/JRC-IDEES/JRC-IDEES-2015_v1/2017%20JRC-IDEES%20Integrated%20Database%20of%20the%20European%20Energy%20Sector%20Methodological%20note.pdf
    Args:
        url (str): url where the JRC-IDEES data is hosted
        out_folder (str): local path where to store the unzipped files
        update (bool): decide whether to override local files if existing or not

    Returns:

    """

    logger.info(f"Downloading zip files from {url}...")

    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, "html.parser")

        # get all zip file links
        zip_files = [t.attrs['href'] for t in soup.select('a') if t.attrs['href'].endswith('.zip')]

        for zip_file in tqdm(zip_files):
            # get zip url
            zip_url = config.jrc_idees_url + zip_file
            # specify local target folder
            target_folder = os.path.join(out_folder, zip_file.replace('.zip', ''))
            if os.path.isdir(target_folder) and (not update):
                # already available and don't want to update, skipping...
                logger.warning(f"{zip_file} already stored (update={update})")
                continue

            # download the unzipped files
            r = requests.get(zip_url)
            z = ZipFile(BytesIO(r.content))
            z.extractall(path=target_folder)

        logger.info("All JRC-IDEES downloaded successfully!")
    except Exception as e:
        logger.error(f"Failed downloading JRC-IDEES files with error={e}")


if __name__ == '__main__':
    download_idees_zip_files()
