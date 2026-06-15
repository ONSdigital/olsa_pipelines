import warnings
import pandas as pd

from typing import List

from helper_functions.data_pipeline import Data
from helper_functions.excel_writer import create_sheets, write_to_xlsx
from helper_functions.sampling_file_handler import load_r_packages_if_needed

from helper_functions.suppression import run_suppression_pipeline
from helper_functions.utils import clean_industry_df, extract_numeric_codes, find_datasets, return_area_codes
from helper_functions.settings import CONFIG


def main() -> None:
    """Runs the full data processing helper_functions and writes results to Excel."""

    if CONFIG['debug_mode']:
        warnings.warn("\n\n DEBUG mode is on. \n Final outputs should not be generated with this mode enabled. "
                      "\n This mode enables a simplified Regenesees helper_functions to speed up program runtime.\n")

    sector_code_df = pd.read_excel(f"pipeline/data/{CONFIG['sector_file']}")
    industry_codes = extract_numeric_codes(clean_industry_df(sector_code_df))
    datasets = find_datasets()
    area_codes = return_area_codes(f"pipeline/data/{CONFIG['geography_file']}")

    if not CONFIG['run_analysis']:
        exit()

    load_r_packages_if_needed(datasets)

    yearly_dataframes: List[dict[str, pd.DataFrame]] = []
    for year, path in datasets.items():
        dataset = Data(year, path,
                       area_codes,
                       industry_codes)
        yearly_dataframes.append(dataset.run_data_pipeline())

    sheets = create_sheets(yearly_dataframes)
    paths = write_to_xlsx(sheets, datasets)
    run_suppression_pipeline(paths)
    print('Done!')


if __name__ == '__main__':
    main()
