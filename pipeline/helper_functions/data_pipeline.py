import re
from functools import reduce
from typing import List, Union

import pandas as pd

from . import sampling_file_handler
from .settings import CONFIG
from .utils import read_data, get_variable_data, return_sic_column, find_max_string, remap_tuple_ranges


class Data:
    def __init__(self, year, data_path, area_codes, industry_codes):
        print(f'\nRunning dataset: {year}.')
        self.year = year
        self.data_df, self.meta_data = read_data(data_path)
        self.area_codes = area_codes
        self.industry_codes = industry_codes
        self.pwta_column = self.find_pwta_col()
        self.final_data: dict[str, dict[str: pd.DataFrame]] = {}
        self.variables_missing: List[str] = []

        print(f'Rows loaded: {self.data_df.shape[0]}')

    def remap_nans(self, column_name: str, codes: dict) -> dict:
        """
        Remap nans to -1000 to allow fillna to work correctly.

        :param column_name:
        :param codes:
        :return:
        """
        nan_mask = self.data_df[column_name].isna()
        self.data_df.loc[nan_mask, column_name] = -1000

        # Make a new code for nans
        codes[-1000] = 'NA'

        return codes

    def spss_metadata_extractor(self, variables):
        present_variables = [variable for variable in variables if variable in self.meta_data.column_names],
        absent_variables = [variable for variable in variables if variable not in self.meta_data.column_names]

        variable_dict = {
            variable: label if (label := self.meta_data.column_names_to_labels.get(variable)) not in [None, "none"]
            else variable for variable in present_variables
        }

        # TODO: extract codes (or keep option to make it manual)

    def find_pwta_col(self) -> List[str]:
        """
        Find columns that match the pattern 'PWTA' followed by digits.

        :return: List of PWTA columns
        """
        pwta_columns = [col for col in self.data_df.columns if re.match(r'PWTA\d+', col)]

        return find_max_string(pwta_columns)

    def _format_column_headers(self) -> None:
        """
        Convert columns to uppercase.

        :return:
        """
        self.data_df.columns = self.data_df.columns.str.upper()

    def _subset_rows(self) -> None:
        if 'ILODEFR' in CONFIG['filter_by']:
            # Filter rows where ILODEFR is 1 (in employment)
            self.data_df = self.data_df[self.data_df['ILODEFR'] == 1]

    def classify_industry(self, individual_industry_code, industry_data):
        if pd.isna(individual_industry_code):
            return "Missing/Unknown"

        if individual_industry_code in industry_data.keys():
            return industry_data[individual_industry_code]

        return "All other industries"

    def find_matching_column(self, candidates):
        """Find the maximum integer in a list of columns. This handles cases where there are multiple weighting options
        in one dataset. For example data for 2015 contains PWTA17 and PWTA18, and this function would return PWTA18. In
        cases where there is not more than one option, the column is simply returned."""

        if not isinstance(candidates, list):
            return candidates if candidates in self.data_df.columns else None
        else:
            return find_max_string([col for col in candidates if col in self.data_df.columns])

    def get_fillna_value(self, variable_dict, column_name, codes):
        if 'fillna' in variable_dict['info']:
            codes = self.remap_nans(column_name, codes)
            fillna_value = variable_dict['info']['fillna']
        else:
            fillna_value = 'Missing'

        return fillna_value, codes

    def apply_mapped_column(self, column_name, new_column_name, variable_dict) -> None:
        codes = self.get_variable_codes(variable_dict, column_name)
        fillna_value, codes = self.get_fillna_value(variable_dict, column_name, codes)

        if all(isinstance(key, tuple) for key in codes):
            codes = remap_tuple_ranges(codes)

        # Convert all dict values into str type
        codes = {key: str(val) for key, val in codes.items()}

        try:
            self.data_df[new_column_name] = (self.data_df[column_name].str.strip().map(codes)
                                             .fillna(fillna_value).astype('category'))
        except AttributeError:
            self.data_df[new_column_name] = (self.data_df[column_name].map(codes)
                                             .fillna(fillna_value).astype('category'))

    def _classify_demographic_info(self) -> None:
        """
        Assign labels to demographic columns based on demographic_mappings.py file.
        """
        for variable in CONFIG['variables']:
            if variable == 'headline_totals':
                continue

            variable_dict = get_variable_data(variable)
            new_column = variable_dict['info']['new_column']

            # For variables where there are different APS columns for main and secondary jobs
            if 'main_column' in variable_dict['info']:
                main_column = self.find_matching_column(variable_dict['info']['main_column'])
                secondary_column = self.find_matching_column(variable_dict['info']['secondary_column'])

                if not main_column or not secondary_column:
                    self.variables_missing.append(new_column)
                    print(f"{new_column} data does not exist in {self.year} data "
                          f"({variable_dict['info']['main_column']}, {variable_dict['info']['secondary_column']})")
                    continue

                self.apply_mapped_column(main_column, f"{new_column}_main", variable_dict)
                self.apply_mapped_column(secondary_column, f"{new_column}_secondary", variable_dict)

            # For variables where it is a single column for both main and secondary job
            else:
                old_column = self.find_matching_column(variable_dict['info']['old_column'])

                if not old_column:
                    self.variables_missing.append(new_column)
                    print(f"{new_column} data does not exist in {self.year} data "
                          f"({variable_dict['info']['old_column']})")
                    continue

                self.apply_mapped_column(old_column, new_column, variable_dict)

    def assign_industry_labels(self, sic_column, industry) -> None:
        """Assign industry labels using the designated sic column."""

        industry_data = self.industry_codes[industry]
        columns = {f'{industry}_main': f'{sic_column}M', f'{industry}_secondary': f'{sic_column}S'}

        for new_col, source_col in columns.items():
            self.data_df[new_col] = self.data_df[source_col].apply(
                lambda code: self.classify_industry(code, industry_data)
            )

    def filter_by_geography(self, column: str, geography: str) -> pd.DataFrame:
        if geography == 'Rest of UK':
            specified_codes = [code for codes_list in self.area_codes.values() for code in codes_list]

            return self.data_df[~(
                    self.data_df[column].isin(specified_codes)
                    | self.data_df[column].isin([CONFIG['outside_uk_code']])
                    | self.data_df[column].isna()
            )]

        else:
            return self.data_df[self.data_df[column].isin(self.area_codes[geography])]

    def aggregate_job_data(self, data: dict, industry_col: str, variable: str, agg_func: str) -> pd.DataFrame:
        rename_dict = {industry_col: 'industry'}

        if int(self.year) in CONFIG['sampling_files'] and agg_func == 'sum':
            return sampling_file_handler.get_counts_and_ci(data, industry_col, variable, self.pwta_column).rename(columns=rename_dict)
        else:
            return self.get_counts(agg_func, data, industry_col, rename_dict, variable)

    def get_counts(self, agg_func, data, industry_col, rename_dict, variable):
        groupby_list = [industry_col]
        if variable != 'headline_totals':
            groupby_list.append(variable)

        results = (data['df'].groupby(groupby_list, observed=True)
                   .agg({data['agg_column']: agg_func})
                   .reset_index()
                   .rename(columns=rename_dict))

        results = self.concat_totals_to_df(results, variable, data['agg_column'])

        return results

    @staticmethod
    def get_variable_codes(variable_dict: dict, column_name: str) -> dict:
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

    def _count_jobs(self, geography: str, variable: Union[dict, str], industry: str,
                    use_weights: bool) -> pd.DataFrame:

        def _get_agg_column(default_column: str, use_weights: bool) -> str:
            return self.pwta_column if use_weights else default_column

        agg_func = 'sum' if use_weights else 'count'

        if isinstance(variable, dict):
            new_column = variable['info']['new_column']
        else:
            new_column = variable

        new_column = new_column.replace(" ", "_")

        # Filter the DataFrame based on geography
        geography_filtered_df = {
            'df': self.filter_by_geography('GORWKR', geography),
            'agg_column': _get_agg_column('GORWKR', use_weights)
        }

        results = self.aggregate_job_data(geography_filtered_df, industry, new_column, agg_func)
        results['Geography'] = geography

        return results

    def check_code_lengths(self, industry: str) -> int:
        length_of_code = len(str(list(self.industry_codes[industry])[0]))

        if not all(len(str(x)) == length_of_code for x in self.industry_codes[industry]):
            raise Exception(f"Codes in {industry} are not all of the same length.")

        return length_of_code

    def run_data_pipeline(self) -> dict[str, pd.DataFrame]:
        self._format_column_headers()
        self._classify_demographic_info()
        self._trim_columns()
        self._concat_industry_labels()
        self._remove_df_column_whitespace()
        self._combine_main_and_secondary_variables()
        self._add_necessary_columns()
        self._handle_sampling_file()
        self._subset_rows()
        self._run_sector_breakdown_pipeline()

        return self.final_data

    def _add_necessary_columns(self):
        self.data_df.reset_index(drop=True, inplace=True)
        self.data_df['ROW_ID'] = self.data_df.index

        if 'headline_totals' in CONFIG['variables']:
            self.data_df['constant'] = 'Total'

    def _combine_main_and_secondary_variables(self):
        def _extract_and_rename_columns(strings: dict) -> pd.DataFrame:
            search_string = strings['search_string']
            replacement_string = strings['replacement_string']

            return self.data_df[[col for col in columns_to_merge if col.endswith(search_string)]].rename(
                columns=lambda x: x.replace(search_string, replacement_string)
            )

        column_type_rules = [{'search_string': '_main', 'replacement_string': ''},
                             {'search_string': '_secondary', 'replacement_string': ''}]

        region_type_rules = [{'search_string': 'GORWKR', 'replacement_string': 'GORWKR', 'joint_col': '_main'},
                             {'search_string': 'GORWK2R', 'replacement_string': 'GORWKR', 'joint_col': '_secondary'}]

        columns_to_match = [entry['search_string'] for entry in column_type_rules + region_type_rules]

        # Find all columns with repeats defined in column_type_rules
        columns_to_merge = [col for col in self.data_df.columns if any(key in col for key in columns_to_match)]

        # Return data that is not repeated
        base_df = self.data_df.drop(columns=columns_to_merge)

        region_merged_dfs = []
        for rename_rule in region_type_rules:
            matching_column_type_rule = next((entry for entry in column_type_rules
                                              if entry['search_string'] == rename_rule['joint_col']),
                                             None)

            region_df = _extract_and_rename_columns(rename_rule)
            rest_of_df = _extract_and_rename_columns(matching_column_type_rule)

            region_merged_dfs.append(pd.concat([base_df, region_df, rest_of_df], axis=1))

        self.data_df = pd.concat(region_merged_dfs, axis=0).reset_index(drop=True)

    def _remove_df_column_whitespace(self):
        self.data_df.columns = self.data_df.columns.str.replace(' ', '_', regex=False)

    def _run_sector_breakdown_pipeline(self):
        for industry in self.industry_codes:
            print(f"\nCollating {industry} data")

            industry = industry.replace(" ", "_")

            for variable in CONFIG['variables']:
                print(f"    Running analysis of {variable}")
                self.process_variable_for_industry(industry, variable)

    def _handle_sampling_file(self):
        if int(self.year) in CONFIG['sampling_files']:
            full_data_df = sampling_file_handler.combine_sampling_file_and_data(self.data_df, int(self.year))
            sampling_file_handler.r_setup(full_data_df, self.pwta_column)

    def _concat_industry_labels(self):
        for industry in self.industry_codes:
            code_length = self.check_code_lengths(industry)
            sic_column = return_sic_column(code_length)
            self.assign_industry_labels(sic_column, industry)

    def _trim_columns(self) -> None:
        def get_col_locs(columns: List[str]):
            col_locs = []
            for column in columns:
                col_locs.append(self.data_df.columns.get_loc(column))

            return col_locs

        variable_range = []
        if CONFIG['variables'][0] != 'headline_totals':
            # Check if it is a dual coded column
            if 'secondary_column' in get_variable_data(CONFIG['variables'][0])['info']:
                first_variable = f"{get_variable_data(CONFIG['variables'][0])['info']['new_column']}_main"
            else:
                first_variable = get_variable_data(CONFIG['variables'][0])['info']['new_column']

            first_varcol_loc = self.data_df.columns.get_loc(first_variable)
            variable_range = list(range(first_varcol_loc, self.data_df.shape[1]))

        caseno_col_loc = self.data_df.columns.get_loc('CASENO')
        pwta_col_loc = self.data_df.columns.get_loc(self.pwta_column)

        industry_col_locs = get_col_locs(['INDC07M', 'INDC07S', 'INDG07M', 'INDG07S', 'INDD07M', 'INDD07S'])
        region_col_locs = get_col_locs(['GORWKR', 'GORWK2R'])
        filter_col_locs = get_col_locs(CONFIG['filter_by'])

        self.data_df = self.data_df.iloc[:, [caseno_col_loc, pwta_col_loc]
                                            + variable_range + region_col_locs + filter_col_locs + industry_col_locs]

    def concat_totals_to_df(self, df, variable, agg_column):
        if variable == 'headline_totals':
            df_totals = pd.DataFrame({agg_column: [df[agg_column].sum()], 'industry': ['All industries total']})
        else:
            df_totals = df.groupby(variable, observed=True).sum().reset_index()
            df_totals['industry'] = 'All industries total'

        # Concat original df and df with totals
        df = pd.concat([df, df_totals])

        return df

    def clean_dataframe(self, df, industry, variable):
        groupby = ["Geography", "industry"]

        if not variable == 'Headline totals':
            groupby.append(variable)

        # Remove missing rows
        df = df[df["industry"] != "Missing/Unknown"].copy()

        self.industry_codes = {k.replace(' ', '_'): v for k, v in self.industry_codes.items()}

        # Define a custom order for the 'industry' column
        industry_order = [*sorted(list(set(self.industry_codes[industry].values()))),
                          "All other industries",
                          "All industries total"]

        # Convert 'industry' column to a categorical type with the custom order
        df["industry"] = pd.Categorical(df["industry"], categories=industry_order, ordered=True)

        # Reorder columns
        df = df.sort_values(by=groupby)

        # Rename columns
        df.columns = df.columns.str.replace('_', ' ')

        df = df.rename(columns={self.pwta_column: f'{self.year}',
                                'GORWKR': f'Raw_{self.year}'})

        try:
            df = df.rename(columns={'Confidence Interval lower': f'{self.year} Confidence Interval lower',
                                    'Confidence Interval upper': f'{self.year} Confidence Interval upper'})
        except TypeError:
            pass

        return df

    def process_variable_for_industry(self, industry: str, variable: str) -> None:
        groupby = ['industry', 'Geography']

        if not variable == 'headline_totals':
            variable_codes = get_variable_data(variable)
            new_column = variable_codes['info']['new_column'].replace(' ', '_')
            groupby.insert(1, new_column)

            if variable_codes['info']['new_column'] in self.variables_missing:
                return
        else:
            variable_codes = variable
            new_column = 'Headline totals'

        results = []
        for use_weights in [False, True]:
            temp_results = []

            for geography in [*self.area_codes.keys(), 'Rest of UK']:
                temp_results.append(self._count_jobs(geography, variable_codes,
                                                     industry, use_weights))

            # Merge the two geographies
            results.append(pd.concat(temp_results))

        # Merge all results together
        merged_df = reduce(lambda left, right: pd.merge(left, right, on=groupby), results)

        final_df = self.clean_dataframe(merged_df, industry, new_column)

        if industry not in self.final_data:
            self.final_data[industry] = {}

        self.final_data[industry][new_column.replace('_', ' ')] = final_df
