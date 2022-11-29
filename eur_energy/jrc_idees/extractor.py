import copy
import json
import logging
import re
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from eur_energy import config
from eur_energy.jrc_idees.downloader import download_idees_zip_files

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


def load_properties_to_parse(sector: str, sub_sector: str, category: str) -> dict:
    """
    Loads the properties to be parsed from the .xlsx tables
    Args:
        sector (str): a sector (e.g. "Industry")
        sub_sector (str): a sub-sector (e.g. "Iron and steel")
        category (str): a category corresponding to a specific sheet, choice from  ['fec', 'ued', 'emi']
    Returns:
        dict: Dictionary with the properties to be parsed
    """

    path = config.SCHEMA_FOLDER / f'{sector}/{sub_sector}.json'

    # make sure file exists
    assert path.is_file(), AssertionError(f'file={path.name} not found!')

    with open(path, 'r') as f:
        data = json.load(f)

    if category == 'emi':
        # append process emissions
        for u, v in data.items():
            if u in [
                'Alumina production', 'Pharmaceutical products etc.', 'Pulp production', 'Paper production',
                'Printing and media reproduction'
            ]:
                #  some sub-sectors don't have reported process emissions, skipping
                continue
            v['Process emissions'] = None

    return data


def extract_table(path: Path, sheet_name: str, props_to_parse: dict, unit: dict) -> pd.DataFrame:
    """
    Extract values from a target table associated to a sheet in the .xlsx file
    Args:
        path (Path): path to the local .xlsx file
        sheet_name (str): the name of the sheet to extract data from
        props_to_parse (dict): the nested properties to parse
        unit (dict): a dictionary with the units of the values to parse

    Returns:
        pd.DataFrame: DataFrame with all the information from the table, reformatted
    """

    # TODO: quick a dirty implementation ... to be refacto for more readability ¯\_(ツ)_/¯ ?

    # get metadata
    file_version, sector, iso2 = path.name.replace('.xlsx', '').split('_')

    # load sheet
    df = pd.read_excel(path, sheet_name=sheet_name)

    # get the years and industry/value types
    cols = list(df.columns)
    country_industry_str, years = cols[0], cols[1:]
    sub_sector, var_type = [
        t.strip() for t in country_industry_str.replace(iso2, '').split(':')[-1].strip().split('/')
    ]

    def _parse_row(df_to_parse, start_idx, end_idx, proc_type, process, fuel, check_value, variable_type,
                   sub_category=None):

        value = None
        while value is None:
            # get the values for the specified indices
            _vals = df_to_parse.iloc[start_idx:end_idx].set_index(country_industry_str)

            try:
                # double check it's the correct process being parsed
                _check_process = _vals.index[0]
                assert _check_process == check_value, AssertionError(
                    f"expected `{check_value}`, got `{_check_process}` instead!"
                )

                value = _vals.to_dict('records')[0]
            except AssertionError:
                # lower increment
                start_idx += -1
                end_idx += -1

        # override fuel based on sub-category
        if sub_category == 'Chemicals: Process cooling - Natural gas (incl. biogas)' and (fuel is None):
            fuel = 'Natural gas (incl. biogas)'

        if process == 'Process emissions':
            fuel = '-'

        return pd.DataFrame(
            {
                'sector': sector,
                'sub_sector': sub_sector,
                'iso2': iso2,
                'process': proc_type,
                "variable": variable_type,
                'category': process,
                "sub_category": sub_category,
                "fuel": fuel,
                'value': value,
                'unit': unit[variable_type],
                'source': file_version
            }
        )

    out_df = pd.DataFrame()
    ct = 3  # initiate counter

    # iterate through the properties to parse from top to bottom of the page
    for j, (main_prop, main_values) in enumerate(props_to_parse.items()):
        for minor_prop, minor_val in main_values.items():
            ct += 1
            if minor_val is None:
                # parse row directly
                start = ct
                end = ct + 1
                new_entry = _parse_row(df, start_idx=start, end_idx=end, proc_type=main_prop, process=minor_prop,
                                       fuel=minor_val, check_value=minor_prop, variable_type=var_type)
                out_df = pd.concat([out_df, new_entry], axis=0)

            elif isinstance(minor_val, list):
                # loop through each element of indentation and parse data
                ct += 1  # first row is the total, skipping
                for i, val in enumerate(minor_val):
                    start = ct + i
                    end = ct + i + 1
                    new_entry = _parse_row(df, start_idx=start, end_idx=end, proc_type=main_prop,
                                           process=minor_prop,
                                           fuel=val, check_value=val, variable_type=var_type)
                    out_df = pd.concat([out_df, new_entry], axis=0)

                # increment all stored values
                ct += len(minor_val) - 1

            elif isinstance(minor_val, dict):
                # one more level of indentation to go
                for sub_prop, sub_val in minor_val.items():
                    ct += 1  # first row is the total, skipping
                    if sub_val is None:
                        # parse row directly
                        start = ct
                        end = ct + 1
                        new_entry = _parse_row(df, start_idx=start, end_idx=end, proc_type=main_prop,
                                               process=minor_prop, fuel=sub_val,
                                               check_value=sub_prop, variable_type=var_type)
                        out_df = pd.concat([out_df, new_entry], axis=0)

                    elif isinstance(sub_val, list):
                        # loop through each element of indentation and parse data
                        ct += 1  # row for subtotal by category, skipping
                        for i, val in enumerate(sub_val):
                            start = ct + i
                            end = ct + i + 1
                            new_entry = _parse_row(df, start_idx=start, end_idx=end, proc_type=main_prop,
                                                   process=minor_prop, fuel=val,
                                                   check_value=val, variable_type=var_type, sub_category=sub_prop)
                            out_df = pd.concat([out_df, new_entry], axis=0)
                        # increment all stored values
                        ct += len(sub_val) - 1
                    else:
                        raise NotImplementedError(f"{sub_val} not handled!")
            else:
                raise NotImplementedError(f"{minor_val} not handled!")

        # increment empty spaces
        ct += 3

    # all entries with nan fuel replaced by electricity
    out_df['fuel'] = out_df['fuel'].fillna('Electricity')

    out_df.index.name = 'year'
    out_df.reset_index(inplace=True)

    return out_df


def extract_activity_data(path: Path, sheet_name: str, unit: dict,
                          key_categories: list = config.jrc_idees_key_categories,
                          sub_categories: list = config.jrc_idees_industry_subcategories, ):
    """
    Extract values relative to production and installed capacities associated to a sheet in the .xlsx file
    Args:
        path (Path): path to the local .xlsx file
        sheet_name (str): the name of the sheet to extract data from
        unit (dict): a dictionary with the units of the values to parse
        key_categories: list of categories to parse
        sub_categories: list of sub-categories to parse
    Returns:

    """

    # get metadata
    file_version, sector, iso2 = path.name.replace('.xlsx', '').split('_')

    df = pd.read_excel(path, sheet_name=sheet_name)

    # get the years and industry/value types
    cols = list(df.columns)
    country_industry_str, years = cols[0], cols[1:]
    sub_sector = country_industry_str.replace(iso2, '').split(':')[-1].strip()

    # make sure to clean first column (remove words between parenthesis
    df[cols[0]] = df[cols[0]].apply(lambda x: re.sub('\((.*?)\)', '', x).strip() if isinstance(x, str) else x)

    # limit to relevant sub-sector
    if sub_sector == 'Iron and steel':
        key_categories = copy.deepcopy(key_categories)
    else:
        key_categories = [t.replace(' steel', "") for t in key_categories]

    sub_categories = sub_categories[sub_sector]

    df_out = pd.DataFrame()

    def _get_total_length(cat_list):
        ct = 0
        for cat in cat_list:
            if isinstance(cat, str):
                ct += 1
            elif isinstance(cat, dict):
                ct += len(cat.values()) + 1
        return ct

    for category in key_categories:
        # define lookup df
        _start = df[df[cols[0]] == category].index.values[0]  # get starting index
        _end = _start + _get_total_length(
            sub_categories) + 1  # end index is at max start index + len of all sub categories
        _df = df.iloc[_start:_end + 1].copy()

        # get index of desired sub-categories
        idx_subs = []
        for sub in sub_categories:
            if isinstance(sub, str):
                # get index directly from df
                idx_subs.append(_df[_df[cols[0]] == sub].index.values[0])
            elif isinstance(sub, dict):
                for u in list(sub.values())[0]:
                    idx_subs.append(_df[_df[cols[0]] == u].index.values[0])

        # extract corresponding values for subcategory
        _vals = _df[_df.index.isin(idx_subs)].copy()

        # reformat data
        _vals = _vals.set_index(cols[0]).T
        _vals = _vals.reset_index().melt(id_vars='index', value_name="value", var_name="process")
        _vals.rename(columns={'index': 'year'}, inplace=True)

        # add sector, sub-sector, iso2, category, unit, source
        _vals['sector'] = sector
        _vals['sub_sector'] = sub_sector
        _vals['iso2'] = iso2
        _vals['variable'] = category
        _vals['unit'] = unit["activity"]
        _vals['source'] = file_version

        df_out = pd.concat([df_out, _vals], axis=0)

    return df_out


def extract_jrc_idees_tables(out_path: Path = config.FORMATTED_DATA_FOLDER):
    """
    Extracts JRC-IDEES tables for relevant sectors
    Args:
        out_path: path where to store dataframes scrapped
    Returns:

    """

    logger.info(f"Extracting JRC-IDEES tables ...")

    # get all excel files, excluding potential temp files
    all_xlsx_paths = set(config.RAW_DATA_FOLDER.glob("*/*.xlsx")) - set(config.RAW_DATA_FOLDER.glob("*/~$*.xlsx"))

    if len(all_xlsx_paths) == 0:
        # missing files, trigger download
        download_idees_zip_files()

    # init. dataframes to export
    activity_df = pd.DataFrame()
    demand_df = pd.DataFrame()
    emissions_df = pd.DataFrame()

    for path in tqdm(all_xlsx_paths):

        if 'Industry' in path.name:
            # parse the industry file
            for sub_sector, acronym in config.jrc_idees_industry_dict.items():

                # handle demand and emissions
                for category in ['fec', 'ued', 'emi']:
                    sheet_name = f"{acronym}_{category}"

                    # load props to parse
                    props_to_parse = load_properties_to_parse(sector='Industry', sub_sector=sub_sector,
                                                              category=category)
                    df = extract_table(path=path, sheet_name=sheet_name, props_to_parse=props_to_parse,
                                       unit=config.units_dict['Industry'])

                    if category in ['fec', 'ued']:
                        # append to demand df
                        demand_df = pd.concat([demand_df, df], axis=0)
                    elif category == 'emi':
                        # append to emissions df
                        emissions_df = pd.concat([emissions_df, df], axis=0)
                    else:
                        raise NotImplementedError(f'category={category} not implemented!')

                # handle activity/capacities
                df = extract_activity_data(path=path, sheet_name=acronym, unit=config.units_dict['Industry'])
                activity_df = pd.concat([activity_df, df], axis=0)
        else:
            # rest of scrapping not yet implemented, skipping
            continue

    # extra post-processing-steps
    logger.info(f"Post-processing tables ...")

    # conversion demand units from ktoe to GJ (1toe = 41.87GJ)
    demand_df['value'] *= 41.87 * 1e3
    demand_df['unit'] = 'GJ'

    # group by category as the sub_category gives little extra-information
    cols_to_group = [t for t in demand_df.columns if t not in ['sub_category', 'value']]
    demand_df = demand_df.groupby(cols_to_group).agg({'value': 'sum'}).reset_index()
    emissions_df = emissions_df.groupby(cols_to_group).agg({'value': 'sum'}).reset_index()

    # conversion activity units from kt to t (1kt = 1e3t)
    activity_df['value'] *= 1e3
    activity_df['unit'] = 'tonne'

    # clean columns
    activity_df['process'] = activity_df['process'].apply(lambda x: re.sub('\((.*?)\)', '', x).strip())
    activity_df['variable'] = activity_df['variable'].apply(lambda x: re.sub('\((.*?)\)', '', x).strip())

    # correct negative activity values (seen for iso2=LV, sub_sector=Iron & Steel)
    activity_df.loc[activity_df['value'] < 0, 'value'] = 0

    # convert emissions from kt CO2 to kg CO2
    emissions_df['value'] *= 1e6
    emissions_df['unit'] = "kgCO2"

    # add relative values by unit of production
    production_df = activity_df[activity_df['variable'] == 'Physical output'].copy()
    production_df.drop(columns=['variable', 'source'], inplace=True)

    # compute relative demand values
    for df, prop in zip([demand_df, emissions_df], ['demand', 'emissions']):
        rel_df = pd.merge(df.copy(), production_df,
                          on=['year', 'sector', 'sub_sector', 'iso2', 'process'],
                          suffixes=['_relative', '_production'], how='inner')

        rel_df['value'] = rel_df['value_relative'] / rel_df['value_production']
        rel_df['unit'] = rel_df['unit_relative'] + '/' + rel_df['unit_production']
        rel_df['variable'] = rel_df['variable'].apply(lambda x: f"{x} intensity")
        rel_df.drop(columns=['value_relative', 'value_production', 'unit_relative', 'unit_production'], inplace=True)

        # concatenate to reference dataframe
        if prop == 'demand':
            demand_df = pd.concat([demand_df, rel_df], axis=0)
        elif prop == 'emissions':
            emissions_df = pd.concat([emissions_df, rel_df], axis=0)

    logger.info(f"Writing outputs to {out_path}")

    # write output files
    activity_df.to_csv(out_path / 'activity_data.csv', index=False)
    demand_df.to_csv(out_path / 'demand_data.csv', index=False)
    emissions_df.to_csv(out_path / 'emission_data.csv', index=False)

    logger.info("All JRC-IDEES tables extracted successfully!")


if __name__ == '__main__':
    extract_jrc_idees_tables()
