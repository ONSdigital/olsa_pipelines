from analysis.helper_functions.settings import CONFIG
from analysis.helper_functions.data_pipeline import *
from analysis.helper_functions.utils import extract_numeric_codes, return_area_codes


class SectorPipeline:
    industry_codes = None
    area_codes = None

    @classmethod
    def setup(cls):
        sector_code_df = pd.read_excel(f"analysis/data/{CONFIG['sector_file']}")
        cls.industry_codes = extract_numeric_codes(cls.clean_industry_df(sector_code_df))

        cls.area_codes = return_area_codes(f"analysis/data/{CONFIG['geography_file']}")

    @classmethod
    def clean_industry_df(cls, df):
        df = df.dropna(subset=['Code: Definitions'])  # Remove NaNs
        df = df[
            ~df['Code: Definitions'].str.contains('source', case=False, na=False)]  # Remove rows containing 'source'
        df.loc[:, 'Industry'] = df.loc[:, 'Industry'].ffill()

        if df['Removed'].notna().any():
            removed_rows = df[df['Removed'].notna()]

            print("\nRemoved rows:")
            for row in removed_rows.iterrows():
                print(f"{row[1]}\n")

        df = df[df['Removed'].isna()]

        industry_dict = {}

        # Make a dict combining each industry with each row, and search for subsectors
        for industry, industry_rows in df.groupby('Industry'):
            industry_dict[industry] = {}
            for code, row in industry_rows.groupby('Code: Definitions'):
                industry_dict[industry][code] = row['Subsectors'].to_list()

        return industry_dict

    def __init__(self, year, data_path):
        print(f'\nRunning dataset: {year}.')
        self.year = year
        self.data_df, self.meta_data = read_data(data_path)
        self.pwta_column = find_pwta_col(self.data_df)
        self.final_data: dict[str, dict[str: pd.DataFrame]] = {}
        self.variables_missing: List[str] = []

        print(f'Rows loaded: {self.data_df.shape[0]}')

    def run_data_pipeline(self) -> dict[str, pd.DataFrame]:
        format_column_headers(self.data_df)
        self.variables_missing = classify_demographic_info(self.data_df, self.year)
        self.data_df = trim_columns(self.data_df, self.pwta_column)

        self._concat_industry_labels()
        self.data_df = combine_main_and_secondary_variables(self.data_df)
        add_row_ids(self.data_df)
        handle_sampling_file(self.data_df, self.year, self.pwta_column)
        self.data_df = subset_rows(self.data_df)
        self._run_sector_breakdown_pipeline()

        return self.final_data

    def _concat_industry_labels(self):
        for industry in self.industry_codes:
            code_length = self._check_code_lengths(industry)
            sic_column = self.return_sic_column(code_length)
            self.assign_industry_labels(sic_column, industry)

    def _check_code_lengths(self, industry: str) -> int:
        length_of_code = len(str(list(self.industry_codes[industry])[0]))

        if not all(len(str(x)) == length_of_code for x in self.industry_codes[industry]):
            raise Exception(f"Codes in {industry} are not all of the same length.")

        return length_of_code

    def assign_industry_labels(self, sic_column, industry) -> None:
        """Assign industry labels using the designated sic column."""

        industry_data = self.industry_codes[industry]
        columns = {f'{industry}_main': f'{sic_column}M', f'{industry}_secondary': f'{sic_column}S'}

        for new_col, source_col in columns.items():
            self.data_df[new_col] = self.data_df[source_col].apply(
                lambda code: self.classify_industry(code, industry_data)
            )

    def classify_industry(self, individual_industry_code, industry_data):
        if pd.isna(individual_industry_code):
            return "Missing/Unknown"

        if individual_industry_code in industry_data.keys():
            return industry_data[individual_industry_code]

        return "All other industries"

    def _run_sector_breakdown_pipeline(self):
        for industry in self.industry_codes:
            print(f"\nCollating {industry} data")

            industry = industry.replace(" ", "_")
            self.final_data[industry] = {}

            for variable in CONFIG['variables']:
                print(f"    Running analysis of {variable}")

                variable_info = return_variable_info(variable, self.variables_missing)

                if variable_info is None:
                    continue

                final_df = analyse_variable(self.data_df, variable_info, self.area_codes,
                                            self.pwta_column, self.year, industry)

                final_df = self._set_industry_col_order(final_df, industry)

                self.final_data[industry][variable_info[0].replace('_', ' ')] = final_df

    def _set_industry_col_order(self, df, industry):
        df = df[df["industry"] != "Missing/Unknown"].copy()

        industry_codes = {k.replace(' ', '_'): v for k, v in self.industry_codes.items()}

        industry_order = [
            *sorted(set(industry_codes[industry].values())),
            "All other industries",
            "All industries total"
        ]

        df["industry"] = pd.Categorical(
            df["industry"],
            categories=industry_order,
            ordered=True
        )

        return df

    @staticmethod
    def return_sic_column(code_length):
        match code_length:
            case 2:
                return 'INDD07'
            case 3:
                return 'INDG07'
            case 4:
                return 'INDC07'
            case _:
                raise Exception("Unknown code length supplied.")
