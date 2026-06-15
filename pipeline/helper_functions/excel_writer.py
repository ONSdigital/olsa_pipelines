import os
from functools import reduce
from pathlib import Path
from typing import List

import pandas as pd
from pandas import DataFrame

from .settings import CONFIG
from .utils import get_variable_data, reorder_columns


def create_sheets(yearly_dataframes: List[dict[str, pd.DataFrame]]) -> dict[str, dict[str, DataFrame]]:
    sheets: dict[str, dict[str, pd.DataFrame]] = {}

    industries = set().union(*[year.keys() for year in yearly_dataframes])

    for industry in industries:
        sheets[industry] = {}

        for variable in CONFIG['variables']:
            var_name = get_variable_data(variable)['info']['new_column'] if variable != 'headline_totals' \
                else 'Headline totals'

            # Extract the relevant DataFrames
            dfs = [entry[industry][var_name] for entry in yearly_dataframes if var_name in entry[industry]]

            groupby = ['industry', 'Geography']

            if var_name != "Headline totals":
                groupby.insert(1, var_name)

            # Merge them sequentially
            merged_df = reduce(lambda left, right: pd.merge(left, right, on=groupby, how='outer'), dfs)

            if var_name != "Headline totals":
                merged_df.sort_values(by=['Geography', 'industry', var_name], inplace=True)

            merged_df = reorder_columns(merged_df, groupby)

            numeric_columns = merged_df.select_dtypes(include=['number']).columns
            merged_df[numeric_columns] = merged_df[numeric_columns].fillna(0)

            sheets[industry][var_name] = merged_df

    return sheets


def write_to_xlsx(sheets: dict[str, dict[str, pd.DataFrame]], datasets: dict[Path]):
    year_range = f"{min(datasets.keys())} - {max(datasets.keys())}"  # Save year range for sheet name
    paths = []

    print("\nSaving files:")
    for industry, variables in sheets.items():
        path = os.path.join("pipeline/output", f"{industry} {year_range}.xlsx")

        with pd.ExcelWriter(path, engine='openpyxl') as writer:
            for variable, df in variables.items():
                df.to_excel(writer, sheet_name=variable, index=False)

        print(f"{path} has been created.")
        paths.append(path)

    return paths
