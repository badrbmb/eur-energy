from pathlib import Path

import pandas as pd

from eur_energy import config


def get_electricity_carbon_intensity(
        path: Path = config.DATA_FOLDER / 'EMBER/yearly_full_release_long_format.csv',
        convert_to_gj: bool = True
) -> pd.DataFrame:
    """
    Loads and process EMBER Yearly electricity data to derive yearly carbon intensity of electricity in by country
    Source: https://ember-climate.org/data-catalogue/yearly-electricity-data/
    Args:
        path (Path): path of local files downloaded
        convert_to_gj (bool): decide to convert from kWh to GJ
    Returns:
        - pd.DataFrame with power carbon intensity by country and year
    """
    df = pd.read_csv(path)

    # get list of former 28 EU countries
    eu28_list = list(df[df['EU'] == 1]['Country code'].unique()) + ['GBR']

    # get generation
    df_generation = df[
        (df['Category'] == 'Electricity demand') &
        (df['Subcategory'] == 'Demand') &
        (df['Ember region'] == 'Europe')
        ].copy()
    # add EU27 + UK entry
    _df_generation_28 = df_generation[df_generation['Country code'].isin(eu28_list)].copy()
    _df_generation_28 = _df_generation_28.groupby(['Year', 'Unit']).agg({'Value': 'sum'}).reset_index()
    _df_generation_28['Country code'] = 'EU27+UK'
    _df_generation_28['Area'] = 'EU27+UK'
    df_generation = pd.concat([df_generation, _df_generation_28], axis=0)

    # get emissions
    df_emissions = df[
        (df['Category'] == 'Power sector emissions') &
        (df['Subcategory'] == 'Aggregate fuel') &
        (df['Ember region'] == 'Europe')
        ].copy()
    # aggregate on country level
    df_emissions = df_emissions.groupby(['Area', 'Country code', 'Year', 'Unit']).agg({'Value': 'sum'}).reset_index()
    # add EU27 + UK entry
    _df_emissions_28 = df_emissions[df_emissions['Country code'].isin(eu28_list)].copy()
    _df_emissions_28 = _df_emissions_28.groupby(['Year', 'Unit']).agg({'Value': 'sum'}).reset_index()
    _df_emissions_28['Country code'] = 'EU27+UK'
    _df_emissions_28['Area'] = 'EU27+UK'
    df_emissions = pd.concat([df_emissions, _df_emissions_28], axis=0)

    # merge the two dfs and derive intensity
    df_intensity = pd.merge(df_generation, df_emissions, on=['Area', 'Country code', 'Year'],
                            suffixes=['_generation', '_emission'], how='left')
    df_intensity['Value'] = df_intensity['Value_emission'] / df_intensity['Value_generation']
    df_intensity['Unit'] = "kgCO2/kWh"  # mtCO2/TWh <-> kgCO2/kWh

    if convert_to_gj:
        df_intensity['Value'] *= 1 / 0.0036
        df_intensity['Unit'] = "kgCO2/GJ"  # 1kWh = 0.0036 GJ

    cols_to_keep = ['Area', 'Country code', 'Year', 'Value', 'Unit']
    return df_intensity[cols_to_keep].copy()
