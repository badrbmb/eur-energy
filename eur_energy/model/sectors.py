import logging
from dataclasses import dataclass
from enum import Enum
from typing import Union, Optional

import numpy as np
import pandas as pd

from eur_energy.model.processes import Process

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


class SubSectorType(Enum):
    chemicals = 'Chemicals Industry'
    iron_and_steel = 'Iron and steel'
    non_ferrous_metals = 'Non Ferrous Metals'
    non_metallic_minerals = 'Non-metallic mineral products'
    pulp_and_paper = 'Pulp, paper and printing'


@dataclass
class SubSector:
    sub_sector_type: Union[str, SubSectorType]
    processes: list[Process]

    def __post_init__(self):
        # enforce type of sub sector name
        if isinstance(self.sub_sector_type, str):
            self.sub_sector_type = SubSectorType(self.sub_sector_type)

        # make sure process names are unique
        assert len(set(self.process_names)) == len(self.process_names), \
            AssertionError(f"Duplicated process names found for sub-sector=`{self.sub_sector_type.value}`!")

    @property
    def process_names(self) -> list:
        """
        List all process names
        Returns:
            - list:
        """
        return [t.process_name for t in self.processes]

    @property
    def total_emission_intensity(self) -> float:
        """
        Total sub-sector emission intensity, in kgCO2/tonne
        Returns:
            - float: weighted average emission intensity for the sub sector by physical output
        """

        _values_weight = [
            (u, v) for u, v in zip(
                [t.total_emission_intensity for t in self.processes],
                [t.production.physical_output for t in self.processes]
            ) if (u == u)
        ]
        try:
            return np.average(a=[t[0] for t in _values_weight], weights=[t[1] for t in _values_weight])
        except ZeroDivisionError:
            return np.nan

    @property
    def total_emissions(self) -> float:
        """
        Total sub-sector emissions, in kgCO2
        Returns:
            - float: total emissions
        """
        return np.nansum([t.total_emissions for t in self.processes])

    @property
    def total_production(self) -> float:
        """
        Total sub-sector physical output, in tonnes
        Returns:
            - float: total production
        """
        return np.nansum([t.production.physical_output for t in self.processes])

    def get_process(self, process: str) -> Optional[Process]:
        """
        Get a given process from the sub-sectors' processes list based on the process name
        Args:
            process (str): Process to fetch
        Returns:
            - Process: the matching process (returns `None` is no match is found)
        """
        _out = [t for t in self.processes if t.process_name == process]
        if len(_out) == 1:
            return _out[0]
        else:
            # case where more than 1 fuel is matched excluded from the __post_init__ unicity test
            logger.warning(f"No fuel found matching process=`{process}`!")
            return None

    def get_fuel_mixt_details(self, process: Optional[str] = None) -> list[dict]:
        """
        Get the fuel mixt for the process, with optional selection of a given process only
        Args:
            process (str): Optional process, if not specified aggregate across all processes
        Returns:
            - list[dict]: List of demand by fuel aggregated across all categories

        """
        if process is None:
            _out = [proc.get_fuel_mixt_details(method='absolute') for proc in self.processes]
        else:
            _out = [
                proc.get_fuel_mixt_details(method='absolute') for proc in self.processes if proc.process_name == process
            ]

        # flatten list
        _out = [u for v in _out for u in v]

        # aggregate by fuel across processes
        _out = pd.DataFrame(_out).groupby(['fuel', 'unit']).agg({'value': 'sum'}).reset_index()

        return _out.to_dict('records')

    def get_summary(self, rounding=2, add_fuels: bool = True) -> dict:
        """
        Summary of key properties of all processes within sub-sector
        Args:
            - rounding (int): round numbers to specified rounding decimal
            - add_fuels (bool): add details relative to fuels
        Returns:
            - dict: nested dictionary with main properties for each process
        """
        return {
            t.process_name: t.get_summary(rounding=rounding, add_fuels=add_fuels) for t in self.processes
        }
