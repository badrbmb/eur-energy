import functools
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Union, Optional

import numpy as np
import pandas as pd

from eur_energy import config

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=None)
def load_carbon_content(path: Path = None, convert_to_co2=True) -> dict:
    """
    Load carbon content for various fuels
    Args:
        path (Path):
        convert_to_co2 (bool): whether to convert to mass CO2 from carbon content
    Returns:
        - dict: Dictionary with keys = fuels and values = either carbon content or CO2 values,
        expressed in kg/GJ (or kgCO2/GJ if "convert_to_co2=True")
    """

    if path is None:
        path = config.DATA_FOLDER / 'IEA/carbon_content_fuel.csv'

    # load file
    df = pd.read_csv(path)

    if convert_to_co2:
        carbon_content_to_co2 = 44 / 12  # weight of a carbon atom is 12 and the atomic weight of oxygen is 16
        # convert to kgCO2
        df['value'] = df['carbon_content'] * carbon_content_to_co2
        # df['unit'] = 'kgCO2/GJ' # reminder - not used
    else:
        df['value'] = df['carbon_content']

    return df.set_index('fuel').to_dict()['value']


# Load emissions by fuel
FUEL_EMISSION_INTENSITIES = load_carbon_content()

# classification of fuel categories
FUEL_CATEGORIES = {
    'Electricity': 'Electricity',
    'Diesel oil': 'Fossil fuel',
    'LPG': 'Fossil fuel',
    'Naphtha': 'Fossil fuel',
    'Natural gas': 'Fossil fuel',
    'Other liquids': 'Fossil fuel',
    'Refinery gas': 'Other',
    'Residual fuel oil': 'Fossil fuel',
    'Solids': 'Fossil fuel',
    'Diesel oil (incl. biofuels)': '',
    'Natural gas (incl. biogas)': '',
    'Biomass': '',
    'Derived gases': '',
    'Steam distributed': '',
    'Solar and geothermal': '',
    'Coke': 'Fossil fuel'
}


class FuelType(Enum):
    electricity = 'Electricity'
    diesel_oil = 'Diesel oil'
    naphtha = 'Naphtha'
    lpgs = 'LPG'
    natural_gas = 'Natural gas'
    other_liquids = 'Other liquids'
    refinery_gas = 'Refinery gas'
    residual_fuel_oil = 'Residual fuel oil'
    solids = 'Solids'
    diesel_oil_incl_biofuels = 'Diesel oil (incl. biofuels)'
    natural_gas_incl_biogas = 'Natural gas (incl. biogas)'
    biomass = 'Biomass'
    derived_gases = 'Derived gases'
    steam_distributed = 'Steam distributed'
    solar_and_geothermal = 'Solar and geothermal'
    coke = 'Coke'

    @property
    def fuel_category(self):
        return FUEL_CATEGORIES.get(self.value)


@dataclass
class FuelConsumption:
    fuel: Union[str, FuelType]
    value: float
    unit: str  # expected in GJ/tonne
    _fuel_emission_intensity: float = None  # useful for setting custom values for Electricity or Steam

    # TODO replace value by _value + add setter
    # TODO add absolute values + option to compute relative values
    # TODO add fuel_cost (USD/unit-fuel), LHV/HHV, natural_unit (derived from HV), and cost (USD/t-product)

    def __post_init__(self):
        # make sure unit is GJ/tonne
        assert self.unit == 'GJ/tonne', AssertionError(
            f"Only 'GJ/tonne currently handled, got unit=`{self.unit}` instead!"
        )

        # convert fuel type if passes as str (enforcing types)
        if isinstance(self.fuel, str):
            self.fuel = FuelType(self.fuel)

        # assign emission intensity if missing
        if self._fuel_emission_intensity is None:
            # fetch default value for fuel
            self._fuel_emission_intensity = FUEL_EMISSION_INTENSITIES.get(self.fuel.value)

    def total_consumption(self, production: float) -> float:
        """
        Compute total consumption of fuel
        Args:
            production (float): total production expressed in tonnes
        Returns:
            - float: total consumption of given fuel, expressed in GJ

        """
        # TODO enforce units are compatible (GJ/tonne * tonne --> GJ)
        return self.value * production

    @property
    def fuel_emission_intensity(self) -> float:
        """
        Emission intensity of fuel
        Returns: Emission intensity expressed in kgCO2/GJ (fuel)
        """
        return self._fuel_emission_intensity

    @fuel_emission_intensity.setter
    def fuel_emission_intensity(self, value):
        # set the value of fuel emission intensity
        self._fuel_emission_intensity = value

    @property
    def emission_intensity(self) -> float:
        """
        Compute emission intensity of fuel
        Returns: Emission intensity expressed in kgCO2/t-product
        """
        return self.value * self.fuel_emission_intensity

    def total_emissions(self, production: float):
        """
        Total fuel emission for a given production level
        Args:
            production (float): total production associated with this fuel

        Returns:
            - float: total emission for given fuel, in kgCO2

        """
        # return total emission expressed in kgCO2
        return self.total_consumption(production) * self.fuel_emission_intensity


@dataclass
class ConsumptionCategory:
    category_name: str
    fuels: List[FuelConsumption]

    def __post_init__(self):
        # make sure fuels have a single entry by fuel type
        assert len(set(self.fuel_types)) == len(self.fuel_types), \
            AssertionError(f"Duplicated fuels found for category=`{self.category_name}`!")

    def get_fuel(self, fuel_type: str, verbose: bool = True) -> Optional[FuelConsumption]:
        """
        Get a given fuel from the category's fuels list based on the fuel type
        Args:
            fuel_type (str): Type of fuel to fetch
            verbose (bool): display or not the log
        Returns:
            - FuelConsumption: the matching fuel (returns `None` is no match is found)
        """
        _out = [t for t in self.fuels if t.fuel.value == fuel_type]
        if len(_out) == 1:
            return _out[0]
        else:
            # case where more than 1 fuel is matched excluded from the __post_init__ unicity test
            if verbose:
                logger.warning(f"No fuel found matching fuel_type=`{fuel_type}` for category={self.category_name}!")
            return None

    @property
    def fuel_types(self) -> List[str]:
        """
        List all fuel types in category
        Returns:
            - List[str]: list of fuel types
        """
        return [t.fuel.value for t in self.fuels]

    def set_fuel_emission_intensities(self, fuel_dict: dict):
        """
        Set the emission intensities of fuel within the category
        Args:
            fuel_dict (dict): A dictionary with the key='fuel_type' and the value
            corresponding emission intensity of fuel to be set
        Returns:
        """
        for fuel_type, value in fuel_dict.items():
            _fuel = self.get_fuel(fuel_type, verbose=False)
            if _fuel is not None:
                _fuel.fuel_emission_intensity = value

    @property
    def total_emission_intensity(self) -> float:
        """
        Sum of all fuels emission intensities of each fuel in the category
        Returns (float): Emission intensity of category  expressed in kgCO2/t-product
        """
        return np.nansum([t.emission_intensity for t in self.fuels])

    def total_emissions(self, production) -> float:
        """
        Sum all emissions for fuels in category
        Args:
             production (float): total production expressed in tonnes
        Returns:
            - float: total emissions of all fuels, expressed in kgCO2
        """
        return np.nansum([t.total_emissions(production) for t in self.fuels])

    @property
    def total_fuel_demand_intensity(self) -> float:
        """
        Total fuel demand for category
        Returns:
            - float: expressed in GJ/tonne

        """
        assert len(set([t.unit for t in self.fuels])) == 1, AssertionError(
            f'Multiple unit founds of fuel demand value for category={self.category_name}'
        )
        return np.nansum([t.value for t in self.fuels])

    @property
    def fuel_demand_details(self) -> list[dict]:
        """
        Returns:
            - list[dict]: List of demand by fuel for the category
        """
        return [
            {
                'category': self.category_name,
                'fuel': t.fuel.value,
                'value': t.value,
                'unit': t.unit
            }
            for t in self.fuels
        ]
