import warnings
import os
from pathlib import Path

import pandas as pd

from typing import List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)

from helper_functions.excel_writer import save_data
from helper_functions.sampling_file_handler import load_r_packages_if_needed

from helper_functions.suppression import run_suppression_pipeline
from helper_functions.utils import find_datasets
from analysis.helper_functions.settings import CONFIG

from pipelines.business_ownership import BusinessOwnershipPipeline
from pipelines.sectors import SectorPipeline

PIPELINES = {
    "business_ownership": BusinessOwnershipPipeline,
    "sectors": SectorPipeline,
}


def setup_pipeline():
    pipeline = CONFIG["analysis_type"]
    pipeline_class = PIPELINES[pipeline]

    pipeline_class.setup()

    return pipeline, pipeline_class


def main() -> None:
    """Runs the full data processing helper_functions and writes results to Excel."""

    if CONFIG['debug_mode']:
        warnings.warn("\n\n DEBUG mode is on. \n Final outputs should not be generated with this mode enabled. "
                      "\n This mode enables a simplified Regenesees helper_functions to speed up program runtime.\n")

    datasets = find_datasets()
    pipeline, pipeline_class = setup_pipeline()

    if not CONFIG['run_analysis']:
        exit()

    load_r_packages_if_needed(datasets)

    yearly_dataframes: List[dict[str, pd.DataFrame]] = []
    for year, path in datasets.items():
        dataset = pipeline_class(year, path)
        yearly_dataframes.append(dataset.run_data_pipeline())

    paths = save_data(yearly_dataframes, pipeline, datasets)
    run_suppression_pipeline(paths)
    print('Done!')


if __name__ == '__main__':
    main()
