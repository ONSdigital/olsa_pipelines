import re
from functools import reduce
from typing import List, Union, Tuple

import pandas as pd
from pandas import DataFrame

from . import sampling_file_handler
from analysis.helper_functions.settings import CONFIG
from .utils import read_data, get_variable_data, find_max_string, remap_tuple_ranges


def _remap_nans(data_df: pd.DataFrame, column_name: str, codes: dict) -> dict:
    """
    Remap nans to -1000 to allow fillna to work correctly.

    :param column_name:
    :param codes:
    :return:
    """
    nan_mask = data_df[column_name].isna()
    data_df.loc[nan_mask, column_name] = -1000

    # Make a new code for nans
    codes[-1000] = 'NA'

    return codes


def spss_metadata_extractor(variables):
    present_variables = [variable for variable in variables if variable in meta_data.column_names],
    absent_variables = [variable for variable in variables if variable not in meta_data.column_names]

    variable_dict = {
        variable: label if (label := meta_data.column_names_to_labels.get(variable)) not in [None, "none"]
        else variable for variable in present_variables
    }

    # TODO: extract codes (or keep option to make it manual)


def find_pwta_col(data_df: pd.DataFrame) -> List[str]:
    """
    Find columns that match the pattern 'PWTA' followed by digits.

    :return: List of PWTA columns
    """
    pwta_columns = [col for col in data_df.columns if re.match(r'PWTA\d+', col)]

    return find_max_string(pwta_columns)


def format_column_headers(data_df: pd.DataFrame) -> None:
    """
    Convert DataFrame column names to uppercase in place.

    :return:
    """

    data_df.columns = data_df.columns.str.upper()


def subset_rows(data_df: pd.DataFrame) -> pd.DataFrame:
    if CONFIG['analysis_type'] == 'business_ownership':
        data_df = data_df[(data_df['ILODEFR'] == 1) & (data_df['business_owner'])]

    elif CONFIG['analysis_type'] == 'sectors':
        # Filter rows where ILODEFR is 1 (in employment)
        data_df = data_df[data_df['ILODEFR'] == 1]

    # TODO add filter_by option

    return data_df


def find_matching_column(data_df: pd.DataFrame, candidates):
    """Find the maximum integer in a list of columns. This handles cases where there are multiple weighting options
    in one dataset. For example data for 2015 contains PWTA17 and PWTA18, and this function would return PWTA18. In
    cases where there is not more than one option, the column is simply returned."""

    if not isinstance(candidates, list):
        return candidates if candidates in data_df.columns else None
    else:
        return find_max_string([col for col in candidates if col in data_df.columns])


def _get_fillna_value(data_df, variable_dict, column_name, codes):
    if 'fillna' in variable_dict['info']:
        codes = _remap_nans(data_df, column_name, codes)
        fillna_value = variable_dict['info']['fillna']
    else:
        fillna_value = 'Missing'

    return fillna_value, codes


def _apply_mapped_column(data_df: pd.DataFrame, column_name, new_column_name, variable_dict) -> None:
    """
    Create a categorised column by mapping APS codes to labels.

    :param data_df:
    :param column_name:
    :param new_column_name:
    :param variable_dict:
    :return:
    """

    codes = _get_variable_codes(variable_dict, column_name)
    fillna_value, codes = _get_fillna_value(data_df, variable_dict, column_name, codes)

    if all(isinstance(key, tuple) for key in codes):
        codes = remap_tuple_ranges(codes)

    # Convert all dict values into str type
    codes = {key: str(val) for key, val in codes.items()}

    try:
        data_df[new_column_name] = (data_df[column_name].str.strip().map(codes)
                                    .fillna(fillna_value).astype('category'))
    except AttributeError:
        data_df[new_column_name] = (data_df[column_name].map(codes)
                                    .fillna(fillna_value).astype('category'))


def classify_demographic_info(data_df, year) -> List[str]:
    """
    Assign labels to demographic columns based on demographic_mappings.py file.
    :param data_df:
    :param year:
    :return: List of missing demographic variables.
    """

    variables_missing = []

    for variable in CONFIG['variables']:
        if variable == 'headline_totals':
            continue

        variable_dict = get_variable_data(variable)
        new_column = variable_dict['info']['new_column']

        # For variables where there are different APS columns for main and secondary jobs
        if 'main_column' in variable_dict['info']:
            main_column = find_matching_column(data_df, variable_dict['info']['main_column'])
            secondary_column = find_matching_column(data_df, variable_dict['info']['secondary_column'])

            if not main_column or not secondary_column:
                variables_missing.append(new_column)
                print(f"{new_column} data does not exist in {year} data "
                      f"({variable_dict['info']['main_column']}, {variable_dict['info']['secondary_column']})")
                continue

            _apply_mapped_column(data_df, main_column, f"{new_column}_main", variable_dict)
            _apply_mapped_column(data_df, secondary_column, f"{new_column}_secondary", variable_dict)

        # For variables where it is a single column for both main and secondary job
        else:
            old_column = find_matching_column(data_df, variable_dict['info']['old_column'])

            if not old_column:
                variables_missing.append(new_column)
                print(f"{new_column} data does not exist in {year} data "
                      f"({variable_dict['info']['old_column']})")
                continue

            _apply_mapped_column(data_df, old_column, new_column, variable_dict)

    return variables_missing


def _filter_by_geography(data_df: pd.DataFrame, column: str, geography: str, area_codes) -> pd.DataFrame:
    if geography == 'Rest of UK':
        specified_codes = [code for codes_list in area_codes.values() for code in codes_list]

        return data_df[~(
                data_df[column].isin(specified_codes)
                | data_df[column].isin([CONFIG['outside_uk_code']])
                | data_df[column].isna()
        )]

    else:
        return data_df[data_df[column].isin(area_codes[geography])]


def get_counts(agg_func, data, variable, groupby_col=None):
    groupby_list = []

    if groupby_col is not None:
        groupby_list.append(groupby_col)

    if variable != 'headline_totals':
        groupby_list.append(variable)

    if groupby_list:
        results = (
            data['df']
            .groupby(groupby_list, observed=True)
            .agg({data['agg_column']: agg_func})
            .reset_index()
        )
    else:
        # Handles cases where no grouping is necessary, such as headline totals for Business Ownership
        results = (
            data['df']
            .agg({data['agg_column']: agg_func})
            .to_frame()
            .T
        )

    if groupby_col is not None:
        results = results.rename(columns={groupby_col: 'industry'})
        results = concat_totals_to_df(results, variable, data['agg_column'])

    return results


def _get_variable_codes(variable_dict: dict, column_name: str) -> dict:
    """
    Extracts the matching code from variable_dict based on the column_name. Handles cases where codes change between
    years.

    :raise exception: If no or multiple matching codes are found.

    :param variable_dict:
    :param column_name:
    :return: The matched codes.
    """

    codes = variable_dict['codes']

    # Check if codes dict has nested dicts, indicating the codes change per year. If it doesn't, just return codes
    if not any(isinstance(value, dict) for value in codes.values()):
        return codes

    matching_codes = [substring for substring in codes.keys() if substring in column_name]

    match len(matching_codes):
        case 0:
            raise Exception(f"No codes matching {column_name} found.")
        case 1:
            return codes[matching_codes[0]]
        case _:
            raise Exception(f"Multiple codes: {matching_codes} found matching {column_name}.")


def _count_jobs(data_df, geography: str, variable: Union[dict, str],
                use_weights: bool, pwta_column, area_codes, year, groupby_col=None) -> pd.DataFrame:
    def _get_agg_column(default_column: str, use_weights: bool) -> str:
        return pwta_column if use_weights else default_column

    agg_func = 'sum' if use_weights else 'count'

    if isinstance(variable, dict):
        new_column = variable['info']['new_column']
    else:
        new_column = variable

    # Filter the DataFrame based on geography
    geography_filtered_df = {
        'df': _filter_by_geography(data_df, 'GORWKR', geography, area_codes),
        'agg_column': _get_agg_column('GORWKR', use_weights)
    }

    if int(year) in CONFIG['sampling_files'] and agg_func == 'sum':
        results = sampling_file_handler.get_counts_and_ci(geography_filtered_df, new_column, pwta_column, groupby_col)
    else:
        results = get_counts(agg_func, geography_filtered_df, new_column, groupby_col)

    results['Geography'] = geography

    return results


def add_row_ids(data_df: pd.DataFrame) -> None:
    """
    Adds a Row ID to each row, and a column of 'Total' if headline totals are to be calculated.

    :param data_df:
    :return:
    """
    data_df.reset_index(drop=True, inplace=True)
    data_df['ROW_ID'] = data_df.index

    if 'headline_totals' in CONFIG['variables']:
        data_df['constant'] = 'Total'


def handle_sampling_file(data_df: pd.DataFrame, year, pwta_column):
    if int(year) in CONFIG['sampling_files']:
        full_data_df = sampling_file_handler.combine_sampling_file_and_data(data_df, int(year))
        sampling_file_handler.r_setup(full_data_df, pwta_column)


def trim_columns(data_df: pd.DataFrame, pwta_column) -> pd.DataFrame:
    def get_col_locs(columns: List[str]):
        col_locs = []
        for column in columns:
            col_locs.append(data_df.columns.get_loc(column))

        return col_locs

    variable_range = []
    if CONFIG['variables'][0] != 'headline_totals':
        # Check if it is a dual coded column
        if 'secondary_column' in get_variable_data(CONFIG['variables'][0])['info']:
            first_variable = f"{get_variable_data(CONFIG['variables'][0])['info']['new_column']}_main"
        else:
            first_variable = get_variable_data(CONFIG['variables'][0])['info']['new_column']

        first_varcol_loc = data_df.columns.get_loc(first_variable)
        variable_range = list(range(first_varcol_loc, data_df.shape[1]))

    caseno_col_loc = data_df.columns.get_loc('CASENO')
    pwta_col_loc = data_df.columns.get_loc(pwta_column)

    industry_col_locs = get_col_locs(['INDC07M', 'INDC07S', 'INDG07M', 'INDG07S', 'INDD07M', 'INDD07S'])
    region_col_locs = get_col_locs(['GORWKR', 'GORWK2R'])
    filter_col_locs = get_col_locs(CONFIG['filter_by'])

    data_df = data_df.iloc[:, [caseno_col_loc, pwta_col_loc]
                              + variable_range + region_col_locs + filter_col_locs + industry_col_locs]

    return data_df


def concat_totals_to_df(data_df: pd.DataFrame, variable, agg_column):
    if variable == 'headline_totals':
        df_totals = pd.DataFrame({agg_column: [data_df[agg_column].sum()], 'industry': ['All industries total']})
    else:
        df_totals = data_df.groupby(variable, observed=True).sum().reset_index()
        df_totals['industry'] = 'All industries total'

    # Concat original df and df with totals
    data_df = pd.concat([data_df, df_totals])

    return data_df


def clean_dataframe(data_df: pd.DataFrame, variable, year, pwta_column) -> pd.DataFrame:
    groupby = ["Geography"]

    if variable != 'Headline totals':
        groupby.append(variable)

    data_df = data_df.sort_values(by=groupby)

    data_df.columns = data_df.columns.str.replace('_', ' ')

    data_df = data_df.rename(
        columns={
            pwta_column: f'{year}',
            'GORWKR': f'Raw_{year}',
            'Confidence Interval lower': f'{year} Confidence Interval lower',
            'Confidence Interval upper': f'{year} Confidence Interval upper'
        }
    )

    return data_df


def return_variable_info(variable, variables_missing):
    if not variable == 'headline_totals':
        variable_codes = get_variable_data(variable)
        variable_name = variable_codes['info']['new_column']

        if variable_codes['info']['new_column'] in variables_missing:
            return None
    else:
        variable_codes = variable
        variable_name = 'Headline totals'

    return variable_name, variable_codes


def analyse_variable(data_df, variable_info: Tuple, area_codes, pwta_column,
                     year, groupby_col=None) -> DataFrame | None:
    groupby = []

    if groupby_col:
        groupby.append('industry')

    if variable_info[0] != 'Headline totals':
        groupby.append(variable_info[0])

    groupby.append('Geography')

    results = []
    for use_weights in [False, True]:
        temp_results = []

        for geography in [*area_codes.keys(), 'Rest of UK']:
            temp_results.append(_count_jobs(data_df, geography, variable_info[1],
                                            use_weights, pwta_column, area_codes, year, groupby_col))

        # Merge the two geographies
        results.append(pd.concat(temp_results))

    # Merge all results together
    merged_df = reduce(lambda left, right: pd.merge(left, right, on=groupby), results)

    final_df = clean_dataframe(merged_df, variable_info[0], year, pwta_column)

    return final_df


def combine_main_and_secondary_variables(data_df) -> pd.DataFrame:
    def _extract_and_rename_columns(df: pd.DataFrame, strings: dict) -> pd.DataFrame:
        search_string = strings['search_string']
        replacement_string = strings['replacement_string']

        return df[[col for col in columns_to_merge if col.endswith(search_string)]].rename(
            columns=lambda x: x.replace(search_string, replacement_string)
        )

    column_type_rules = [{'search_string': '_main', 'replacement_string': ''},
                         {'search_string': '_secondary', 'replacement_string': ''}]

    region_type_rules = [{'search_string': 'GORWKR', 'replacement_string': 'GORWKR', 'joint_col': '_main'},
                         {'search_string': 'GORWK2R', 'replacement_string': 'GORWKR', 'joint_col': '_secondary'}]

    columns_to_match = [entry['search_string'] for entry in column_type_rules + region_type_rules]

    # Find all columns with repeats defined in column_type_rules
    columns_to_merge = [col for col in data_df.columns if any(key in col for key in columns_to_match)]

    # Return data that is not repeated
    base_df = data_df.drop(columns=columns_to_merge)

    region_merged_dfs = []
    for rename_rule in region_type_rules:
        matching_column_type_rule = next((entry for entry in column_type_rules
                                          if entry['search_string'] == rename_rule['joint_col']),
                                         None)

        region_df = _extract_and_rename_columns(data_df, rename_rule)
        rest_of_df = _extract_and_rename_columns(data_df, matching_column_type_rule)

        region_merged_dfs.append(pd.concat([base_df, region_df, rest_of_df], axis=1))

    data_df = pd.concat(region_merged_dfs, axis=0).reset_index(drop=True)

    return data_df
