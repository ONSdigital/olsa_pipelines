from analysis.helper_functions.geographies import create_geog_lookup, add_geography_columns
from analysis.helper_functions.settings import CONFIG
from analysis.helper_functions.data_pipeline import *
from analysis.helper_functions.utils import return_area_codes


class BusinessOwnershipPipeline:
    area_codes = None
    geog_lookup = None

    @classmethod
    def setup(cls):
        cls.area_codes = return_area_codes(f"analysis/data/{CONFIG['geography_file']}")
        cls.geog_lookup = create_geog_lookup()

    def __init__(self, year, data_path):
        print(f'\nRunning dataset: {year}.')
        self.year = year
        self.data_df, self.meta_data = read_data(data_path)
        self.pwta_column = find_pwta_col(self.data_df)
        self.final_data: dict[str, dict[str: pd.DataFrame]] = {}
        self.variables_missing: List[str] = []

        print(f'Rows loaded: {self.data_df.shape[0]}')

    def run_data_pipeline(self) -> dict[str, pd.DataFrame]:
        self.data_df = add_geography_columns(self.data_df, self.geog_lookup)
        format_column_headers(self.data_df)
        self.variables_missing = classify_demographic_info(self.data_df, self.year)
        self.count_businesses()
        self.data_df = trim_columns(self.data_df, self.pwta_column)

        self.data_df = combine_main_and_secondary_variables(self.data_df)
        self.data_df = remove_zero_weight_rows(self.data_df, self.pwta_column)
        add_row_ids(self.data_df)
        handle_sampling_file(self.data_df, self.year, self.pwta_column)
        self.data_df = subset_rows(self.data_df)
        self._run_analysis_pipeline()

        return self.final_data

    def _run_analysis_pipeline(self):
        self.final_data = {}

        for variable in CONFIG['variables']:
            print(f"    Running analysis of {variable}")

            variable_info = return_variable_info(variable, self.variables_missing)

            if variable_info is None:
                continue

            final_df = analyse_variable(self.data_df, variable_info, self.area_codes,
                                        self.pwta_column, self.year)

            self.final_data[variable_info[0].replace('_', ' ')] = final_df

    def count_businesses(self):
        # Need to specify exact columns as the SELF columns are not ordered
        self.data_df['business_owner_main'] = self.data_df[["SELF1", "SELF2", "SELF3", "SELF4"]].isin([2, 3, 4]).any(axis=1)
        self.data_df['business_owner_secondary'] = self.data_df[["SELF21", "SELF22", "SELF23", "SELF24"]].isin([2, 3, 4]).any(axis=1)
