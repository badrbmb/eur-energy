import logging
from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import pandas as pd
from eur_energy.model.categories import ConsumptionCategory

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

VALID_SUBSECTOR_PROCESSES = {
    'Chemicals Industry': ['Basic chemicals',
                           'Other chemicals',
                           'Pharmaceutical products etc.'],
    'Iron and steel': ['Integrated steelworks', 'Electric arc'],
    'Non Ferrous Metals': ['Alumina production',
                           'Aluminium - primary production',
                           'Aluminium - secondary production',
                           'Other non-ferrous metals'],
    'Non-metallic mineral products': ['Cement',
                                      'Ceramics & other NMM',
                                      'Glass production'],
    'Pulp, paper and printing': ['Pulp production',
                                 'Paper production',
                                 'Printing and media reproduction']
}


@dataclass
class Production:
    physical_output: float
    installed_capacity: float
    capacity_investment: float
    decommissioned_capacity: float
    idle_capacity: float
    unit: str

    @property
    def capacity(self):
        return self.installed_capacity + self.capacity_investment - self.decommissioned_capacity - self.idle_capacity


@dataclass
class Process:
    process_name: str
    production: Production
    process_emission_intensity: float  # expressed in kgCO2/tonne
    categories: List[ConsumptionCategory]
    _grid_carbon_intensity: Optional[float] = None  # expressed in kgCO2/GJ

    def __post_init__(self):
        # make sure categories have a single entry by category type
        assert len(set(self.category_names)) == len(self.category_names), \
            AssertionError(f"Duplicated categories found for process=`{self.process_name}`!")

        if self._grid_carbon_intensity is not None:
            # set carbon intensity electricity for all categories
            self.set_carbon_intensity_electricity()

    def set_carbon_intensity_electricity(self):
        """
        Assign relevant emission intensities for power/steam across all categories
        Returns:
        """
        for category in self.categories:
            category.set_fuel_emission_intensities(
                {
                    'Electricity': self.grid_carbon_intensity,
                    'Steam distributed': self.grid_carbon_intensity  # assume steam is equivalent to grid
                }
            )

    @property
    def grid_carbon_intensity(self) -> float:
        """
        Carbon intensity of grid electricity expressed in kgCO2/GJ
        Returns:
            - float: grid carbon intensity
        """
        return self._grid_carbon_intensity

    @grid_carbon_intensity.setter
    def grid_carbon_intensity(self, value):
        self._grid_carbon_intensity = value
        # re-assign relevant carbon intensities across categories
        self.set_carbon_intensity_electricity()

    @property
    def category_names(self) -> List[str]:
        """
        All names of categories in process
        Returns:
            - List[str]: category names
        """
        return [t.category_name for t in self.categories]

    def get_category(self, category: str) -> Optional[ConsumptionCategory]:
        """
        Get a given category from the process' categories list based on the category name
        Args:
            category (str): Category to fetch
        Returns:
            - ConsumptionCategory: the matching category (returns `None` is no match is found)
        """
        _out = [t for t in self.categories if t.category_name == category]
        if len(_out) == 1:
            return _out[0]
        else:
            # case where more than 1 fuel is matched excluded from the __post_init__ unicity test
            logger.warning(f"No fuel found matching category=`{category}`!")
            return None

    def set_fuel_emission_intensities(self, category_fuel_dict: dict):
        """
        Set the emission intensities of fuel for each category within the process' categories
        Args:
            category_fuel_dict (dict): A nested dictionary with the primary key=`category_name`,
             secondary key=`fuel_type` and the value corresponding emission intensity of fuel to be set
        Returns:
        """
        for category_name, fuel_dict in category_fuel_dict.items():
            _category = self.get_category(category_name)
            if _category is not None:
                _category.set_fuel_emission_intensities(fuel_dict)

    @property
    def total_fuel_emission_intensity(self) -> float:
        """
        Sum of all fuels emission intensities of each fuel across all categories
        Returns (float): Emission intensity of category  expressed in kgCO2/t-product
        """
        return np.nansum([t.total_emission_intensity for t in self.categories])

    @property
    def total_emission_intensity(self) -> float:
        """
        Returns:
            - float: fuel + process emission intensity in kgCO2/t-product
        """
        return self.total_fuel_emission_intensity + self.process_emission_intensity

    @property
    def total_fuel_emissions(self) -> float:
        """
        Sum all emissions for fuels across all categories associated with the physical output of the given process
        Returns:
            - float: total emissions of all fuels, expressed in kgCO2
        """
        return np.nansum([t.total_emissions(self.production.physical_output) for t in self.categories])

    @property
    def total_fuel_demand_intensity(self) -> float:
        """
        Total fuel demand intensity across all categories
        Returns:
            - float: expressed in GJ/tonne
        """
        return np.nansum([t.total_fuel_demand_intensity for t in self.categories])

    @property
    def total_fuel_demand(self) -> float:
        """
        Total fuel demand across all categories
        Returns:
            - float: expressed in GJ
        """
        return self.total_fuel_demand_intensity * self.production.physical_output

    @property
    def total_process_emissions(self) -> float:
        """
        Returns:
            - float: total emissions from process expressed in kgCO2
        """
        return self.process_emission_intensity * self.production.physical_output

    @property
    def total_emissions(self) -> float:
        """
        Returns:
            - float: total emissions fuels and process expressed in kgCO2
        """
        return self.total_fuel_emissions + self.total_process_emissions

    @property
    def emission_intensity_details(self) -> list[dict]:
        """
        Returns:
            - list[dict]: list of emissions intensities broken-down by category
        """
        _out = [
            {
                'category': t.category_name,
                'value': t.total_emission_intensity,
                'unit': 'kgCO2/tonne'
            } for t in self.categories
        ]
        # add process emissions
        _out.append(
            {
                'category': 'Process emissions',
                'value': self.process_emission_intensity,
                'unit': 'kgCO2/tonne'
            }
        )
        return _out

    def get_fuel_mixt_details(self, category: Optional[str] = None, method: str = 'relative') -> list[dict]:
        """
        Get the fuel mixt for the process, with optional selection of a given category only
        Args:
            category (str): Optional category, if not specified aggregate across all categories
            method (str): Either `relative` for intensity values or `absolute` for total
        Returns:
            - list[dict]: List of demand by fuel aggregated across all categories

        """
        if category is None:
            _out = [cat.fuel_demand_details for cat in self.categories]
        else:
            _out = [cat.fuel_demand_details for cat in self.categories if cat.category_name == category]

        # flatten list
        _out = [u for v in _out for u in v]

        # aggregate by fuel across categories
        _out = pd.DataFrame(_out).groupby(['fuel', 'unit']).agg({'value': 'sum'}).reset_index()

        if method == 'absolute':
            _out['value'] *= self.production.physical_output
            _out['unit'] = 'GJ'

        return _out.to_dict('records')

    @property
    def electricity_share_of_demand(self) -> float:
        """
        Get the electricity demand as a share of total fuel demand
        Returns:
            - float: ratio of electricity between 0 and 1
        """
        _total = self.get_fuel_mixt_details()
        _electricity = [t for t in _total if t['fuel'] == 'Electricity']
        if len(_electricity) == 1:
            _value = _electricity[0]['value']
        else:
            _value = 0

        return _value / self.total_fuel_demand_intensity

    def get_summary(self, rounding=2, add_fuels: bool = True) -> dict:
        """
        Summary of key properties of given process
        Args:
            - rounding (int): round numbers to specified rounding decimal
            - add_fuels (bool): add details relative to fuels
        Returns:
            - dict: with main properties
        """
        _out = {
            'Physical output (tonnes)': round(self.production.physical_output, rounding),
            'Total fuel demand intensity (GJ)': round(self.total_fuel_demand, rounding),
            'Electricity share of total demand (%)': round(self.electricity_share_of_demand * 100, rounding),
            'Total fuel demand intensity (GJ/tonne)': round(self.total_fuel_demand_intensity, rounding),
            'Total emissions (kgCO2)': round(self.total_emissions, rounding),
            'Total emission intensity (kgCO2/tonne)': round(self.total_emission_intensity, rounding),
        }

        if add_fuels:
            # add fuel details
            _relative_values = self.get_fuel_mixt_details()
            # relative values
            _out['Fuel demand intensity (GJ/tonne)'] = {
                u['fuel']: round(u['value'], rounding) for u in _relative_values
            }
            # absolute values
            _out['Fuel demand intensity (GJ)'] = {
                u['fuel']: round(u['value'] * self.production.physical_output, rounding) for u in _relative_values
            }

        return _out
