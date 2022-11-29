import pandas as pd

from eur_energy.ember.processor import get_electricity_carbon_intensity
from eur_energy.model.categories import ConsumptionCategory, FuelConsumption
from eur_energy.model.countries import Country
from eur_energy.model.processes import Process, Production
from eur_energy.model.sectors import SubSector

df_electricity_data = get_electricity_carbon_intensity()


def compose_country(
        iso2: str, year: str,
        demand_df: pd.DataFrame, activity_df: pd.DataFrame, emission_df: pd.DataFrame
) -> Country:
    """
    Creates a country object using demand, activity and emission_df information
    Args:
        iso2:
        year:
        demand_df:
        activity_df:
        emission_df:
    Returns:

    """

    ref_variable = 'final energy consumption intensity'
    df = demand_df[
        (demand_df['year'] == year) & (demand_df['variable'] == ref_variable) &
        (demand_df['iso2'] == iso2)
        ].copy()

    # get carbon intensity grid
    country = Country(iso2)
    grid_carbon_intensity = df_electricity_data[
        (df_electricity_data['Country code'] == country.iso3) &
        (df_electricity_data['Year'] == year)
        ]['Value'].values[0]  # expressed in kgCO2/GJ

    sub_sectors = []

    for sub_sector, df_sub_sector in df.groupby('sub_sector'):

        processes = []

        for process, df_process in df_sub_sector.groupby('process'):

            # get production
            df_production = activity_df[
                (activity_df['year'] == year) &
                (activity_df['iso2'] == iso2) &
                (activity_df['sub_sector'] == sub_sector) &
                (activity_df['process'] == process)
                ].copy()
            # assign key
            df_production['key'] = df_production['variable'].apply(lambda x: x.replace(' ', '_').lower())
            activity_data = df_production.pivot('unit', 'key', 'value').reset_index().to_dict('records')[0]
            production = Production(**activity_data)

            # get process emissions
            df_emission = emission_df[
                (emission_df['year'] == year) &
                (emission_df['iso2'] == iso2) &
                (emission_df['sub_sector'] == sub_sector) &
                (emission_df['process'] == process) &
                (emission_df['category'] == 'Process emissions') &
                (emission_df['variable'] == 'CO2 emissions intensity')
                ].copy()

            if len(df_emission) == 1:
                process_emissions_value = df_emission['value'].values[0]
            else:
                process_emissions_value = 0  # if not available consider no process emissions

            # get fuels
            categories = []
            for category_name, df_c in df_process.groupby('category'):
                fuels = []
                for idx, row in df_c.iterrows():
                    fuel_data = row[['fuel', 'value', 'unit']].to_dict()
                    fuels.append(FuelConsumption(**fuel_data))

                category = ConsumptionCategory(category_name=category_name, fuels=fuels)
                categories.append(category)

            # define the process
            process = Process(process_name=process,
                              production=production,
                              process_emission_intensity=process_emissions_value,
                              categories=categories,
                              _grid_carbon_intensity=grid_carbon_intensity)

            # store process for sub-sector
            processes.append(process)

        # define sub_sector
        sub_sector = SubSector(sub_sector_type=sub_sector, processes=processes)

        sub_sectors.append(sub_sector)

    # assign sub sectors
    country.sub_sectors = sub_sectors

    return country
