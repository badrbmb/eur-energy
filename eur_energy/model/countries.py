import logging
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Optional, Union

import numpy as np
import pandas as pd
import pycountry

from eur_energy.model.sectors import SubSector

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


@dataclass
class Country:
    iso2: str
    _sub_sectors: list[SubSector] = None

    def __post_init__(self):
        # assign country name
        self._country = self.get_country_from_iso2(self.iso2)

        if self._sub_sectors is not None:
            self.check_valid()

    def check_valid(self):
        # make sure process names are unique
        assert len(set(self.sub_sector_names)) == len(self.sub_sector_names), \
            AssertionError(f"Duplicated sub-sectors names found for country=`{self.country_name}`!")

    @staticmethod
    def get_country_from_iso2(iso2):
        # fallback country to some ISO2-codes
        _fall_back = {
            'EL': 'GR',
            'UK': 'GB'
        }
        if iso2 in ['EU27+UK', 'EU28']:
            # custom namespace for aggregated EU27 + UK data
            return SimpleNamespace(**{'alpha_2': 'EU27+UK', 'alpha_3': 'EU27+UK', 'name': 'EU27 + UK'})
        else:
            return pycountry.countries.get(alpha_2=_fall_back.get(iso2, iso2))

    @property
    def country_name(self):
        return self._country.name

    @property
    def iso3(self):
        return self._country.alpha_3

    @property
    def sub_sectors(self):
        return self._sub_sectors

    @sub_sectors.setter
    def sub_sectors(self, sub_sectors: list[SubSector]):
        self._sub_sectors = sub_sectors
        # check valid sub-sector names
        self.check_valid()

    @property
    def sub_sector_names(self):
        return [t.sub_sector_type.value for t in self.sub_sectors]

    @property
    def grid_carbon_intensity(self):
        """
        Get the average grid carbon intensity of all sub-sectors
        Returns:
            - float: carbon intensity electricity in kgCO2/GJ
        """
        return np.nanmean([sub_sector.grid_carbon_intensity for sub_sector in self.sub_sectors])

    def set_grid_carbon_intensity(self, value):
        """
        Set the same grid carbon intensity for all sub-sectors
        Args:
            value: carbon intensity of electricity (from grid) in kgCO2/GJ
        Returns:
        """
        for sub_sector in self.sub_sectors:
            sub_sector.set_grid_carbon_intensity(value)

    @property
    def total_emissions(self) -> float:
        """
        Total emissions across all sub sectors in kgCO2
        Returns:
            - float: absolute emissions in kgCO2
        """
        return np.nansum([t.total_emissions for t in self.sub_sectors])

    def get_sub_sector(self, sub_sector: str) -> Optional[SubSector]:
        """
        Get a given sub-sector from the country' sub-sectors list based on the sub-sector name
        Args:
            sub_sector (str): sub-sector to fetch
        Returns:
            - ConsumptionCategory: the matching sub-sector (returns `None` is no match is found)
        """
        _out = [t for t in self.sub_sectors if t.sub_sector_type.value == sub_sector]
        if len(_out) == 1:
            return _out[0]
        else:
            # case where more than 1 match excluded from the __post_init__ unicity test
            logger.warning(f"No match found for sub-sector=`{sub_sector}`!")
            return None

    def get_total_emissions(self, sub_sector: Optional[str] = None, process: Optional[str] = None) \
            -> Optional[Union[list, float]]:
        """
        Emissions for a given sub-sector
        Args:
            sub_sector (str):
            process (str): optional, if None, returns all sub-sector emission intensities
        Returns:
            - float: emission intensity expressed in kgCO2/tonne
        """
        if sub_sector is not None:
            _match = self.get_sub_sector(sub_sector)
            if _match is not None:
                if process is not None:
                    _match = _match.get_process(process)
                    if _match is not None:
                        return _match.total_emissions
                else:
                    return _match.total_emissions
            else:
                return None
        else:
            # return all sub-sectors with recursive call
            return [
                {
                    'sub_sector': t,
                    'value': self.get_total_emissions(sub_sector=t),
                    'unit': "kgCO2"  # TODO replace hard-coded by inferred
                }
                for t in self.sub_sector_names
            ]

    def get_total_emission_intensity(self, sub_sector: Optional[str] = None, process: Optional[str] = None) \
            -> Optional[Union[list, float]]:
        """
        Emission intensity for a given sub-sector
        Args:
            sub_sector (str):
            process (str): optional, if None, returns all sub-sector emission intensities
        Returns:
            - float: emission intensity expressed in kgCO2/tonne
        """
        if sub_sector is not None:
            _match = self.get_sub_sector(sub_sector)
            if _match is not None:
                if process is not None:
                    _match = _match.get_process(process)
                    if _match is not None:
                        return _match.total_emission_intensity
                else:
                    return _match.total_emission_intensity
            else:
                return None
        else:
            # return all sub-sectors with recursive call
            return [
                {
                    'sub_sector': t,
                    'value': self.get_total_emission_intensity(sub_sector=t),
                    'unit': "kgCO2/tonne"  # TODO replace hard-coded by inferred
                }
                for t in self.sub_sector_names
            ]

    @property
    def emission_intensity_by_sub_sector(self) -> dict:
        """
        Emission intensity for each sub sector
        Returns:
            - dict:
        """
        return {
            sub_sector.sub_sector_type.value: sub_sector.total_emission_intensity for sub_sector in self.sub_sectors
        }

    def get_total_fuel_demand(self, sub_sector: str = None) -> list:
        """
        Total fuel consumed for the sector
        Args:
            - sub_sector (str): specific sub-sector to return associated fuel demand
        Returns:
            - dict: dictionary with key=fuel and value the associated absolute consumption for the fuel
        """
        if sub_sector is None:
            _out = [sub.get_fuel_mixt_details() for sub in self.sub_sectors]
        else:
            _out = [
                sub.get_fuel_mixt_details() for sub in self.sub_sectors if sub.sub_sector_type.value == sub_sector
            ]

        # flatten list
        _out = [u for v in _out for u in v]

        # aggregate by fuel across processes/sub-sectors
        _out = pd.DataFrame(_out).groupby(['fuel_class', 'fuel', 'unit']).agg({'value': 'sum'}).reset_index()

        return _out.to_dict('records')

    def get_total_fuel_demand_all_sub_sectors(self) -> list:
        """
        Returns:
            - list: total fuel demand in GJ for each sub-sector in the country
        """
        _out = []
        for sub in self.sub_sector_names:
            _tmp = self.get_total_fuel_demand(sub_sector=sub)
            # aggregate
            _value = np.nansum([t['value'] for t in _tmp])
            _unit = _tmp[0]['unit']  # get first unit from list
            _out.append({'sub_sector': sub, 'value': _value, 'unit': _unit})

        return _out

    @property
    def total_fuel_demand(self) -> float:
        """
        Total fuel demand across all sub sectors in GJ
        Returns:
            - float: fuel demand in GJ
        """
        return np.nansum([t['value'] for t in self.get_total_fuel_demand()])


@dataclass
class CountryCollection:
    countries: list[Country]

    def __post_init__(self):
        # make sure countries are unique
        assert len(set(self.iso2s)) == len(self.iso2s), \
            AssertionError(f"Duplicated country ISO2 found!")

    @property
    def iso2s(self):
        return [t.iso2 for t in self.countries]

    @property
    def country_names(self):
        return [t.country_name for t in self.countries]

    @property
    def sub_sector_names(self):
        return list(set([t.sub_sector_names for t in self.countries]))

    @property
    def process_names(self):
        # use first country as reference
        _ref = self.countries[0]
        return {
            u.sub_sector_type.value: u.process_names for u in _ref.sub_sectors
        }

    @property
    def emission_intensity_details(self) -> list[dict]:
        """
        Breakdown of emission intensities for each country by sub-sector and process
        Returns:
            - list[dict]
        """
        return [
            {
                "iso2": country.iso2,
                'country': country.country_name,
                'values': country.emission_intensity_by_sub_sector
            } for country in self.countries
        ]


class DeltaCountry:
    country1: Country
    country2: Country

    @property
    def delta_emissions(self) -> float:
        """
        Get absolute difference between total emissions of two countries
        Returns:
            - float: country2.total_emissions - country1.total_emissions
        """
        return self.country2.total_emissions - self.country1.total_emissions

    @property
    def delta_emissions_by_sub_sector(self) -> dict:
        """
        Get the absolute difference between total emissions by sub-sector of each country
        Returns:
            -dict: country1 - country2 for sector (expressed in kgCO2)
        """
        df1 = pd.DataFrame([self.country1.get_total_emissions()])
        df2 = pd.DataFrame([self.country1.get_total_emissions()])

        df = pd.merge(df1, df2, on=['sub_sector', 'unit'], suffixes=['_1', '_2'])
        df['value'] = df['value_2'] - df['value_1']
        df.drop(columns=['value_2', 'value_1'], inplace=True)

        return df.to_dict('records')

    @property
    def delta_emission_intensity_by_sub_sector(self) -> dict:
        """
        Get the absolute difference between the emission intensities by sub-sector of each country
        Returns:
            -dict: country1 - country2 for each EFs by sector (expressed in kgCO2/tonne)
        """
        df1 = pd.DataFrame([self.country1.emission_intensity_by_sub_sector])
        df2 = pd.DataFrame([self.country1.emission_intensity_by_sub_sector])
        return (df2 - df1).T.to_dict()[0]

    @property
    def delta_fuel_demand_by_sub_sector(self) -> dict:
        """
        Get the absolute difference between the fuel demand by sub-sector of each country
        Returns:
            -dict: country1 - country2 for each fuel (expressed in GJ)
        """
        df1 = pd.DataFrame([self.country1.get_total_fuel_demand()])
        df2 = pd.DataFrame([self.country1.get_total_fuel_demand()])

        df = pd.merge(df1, df2, on=['fuel_class', 'fuel', 'unit'], suffixes=['_1', '_2'])
        df['value'] = df['value_2'] - df['value_1']
        df.drop(columns=['value_2', 'value_1'], inplace=True)

        return df.to_dict('records')
