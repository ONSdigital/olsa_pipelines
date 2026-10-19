import os
from functools import reduce
from pathlib import Path
from typing import List, TypeAlias

import pandas as pd
from pandas import DataFrame

from analysis.helper_functions.settings import CONFIG
from .utils import get_variable_data, reorder_columns

VariableFrames: TypeAlias = dict[str, DataFrame]
GroupedFrames: TypeAlias = dict[str, VariableFrames]


def save_data(yearly_dataframes, analysis_type, datasets):
    sheets = create_sheets(yearly_dataframes, analysis_type)
    return write_to_xlsx(sheets, datasets)


def normalise_yearly_df(yearly_df: VariableFrames | GroupedFrames, analysis_type: str) -> GroupedFrames:
    """Convert a flat yearly result into the standard nested structure."""

    if all(isinstance(value, DataFrame) for value in yearly_df.values()):
        return {analysis_type: yearly_df}

    if all(isinstance(value, dict) for value in yearly_df.values()):
        return yearly_df


def create_sheets(yearly_dataframes: list[VariableFrames | GroupedFrames], analysis_type: str) -> GroupedFrames:
    sheets: GroupedFrames = {}

    normalised_dataframes = [normalise_yearly_df(yearly_df, analysis_type) for yearly_df in yearly_dataframes]

    group_variables = set().union(*(yearly_df.keys() for yearly_df in normalised_dataframes))

    for group_variable in group_variables:
        sheets[group_variable] = {}

        for variable in CONFIG["variables"]:
            if variable == "headline_totals":
                var_name = "Headline totals"
            else:
                var_name = (get_variable_data(variable)["info"]["new_column"].replace("_", " "))

            dfs = [
                yearly_df[group_variable][var_name]
                for yearly_df in normalised_dataframes
                if group_variable in yearly_df
                and var_name in yearly_df[group_variable]
            ]

            # The variable may not be available for any year
            if not dfs:
                continue

            row_order, column_order = get_sort_orders(dfs, var_name)

            # Merge years into one df
            merged_df = reduce(
                lambda left, right: pd.merge(
                    left,
                    right,
                    on=row_order,
                    how="outer",
                ),
                dfs,
            )

            # Sort rows into the correct order
            merged_df.sort_values(by=row_order, inplace=True)

            # Sort columns into the correct order
            merged_df = reorder_columns(merged_df, column_order)

            numeric_columns = merged_df.select_dtypes(include="number").columns

            merged_df[numeric_columns] = (merged_df[numeric_columns].fillna(0))

            sheets[group_variable][var_name] = merged_df

    return sheets


def get_sort_orders(dfs, var_name):
    has_industry = all("industry" in df.columns for df in dfs)
    has_variable = var_name != "Headline totals"

    row_order = ["Geography"]
    column_order = []

    if has_industry:
        row_order.append("industry")
    if has_variable:
        row_order.append(var_name)

    if has_industry:
        column_order.append("industry")
    if has_variable:
        column_order.append(var_name)

    column_order.append("Geography")

    return row_order, column_order


def write_to_xlsx(sheets: dict[str, dict[str, DataFrame]], datasets: dict[Path]):
    year_range = f"{min(datasets.keys())} - {max(datasets.keys())}"  # Save year range for sheet name
    paths = []

    print("\nSaving files:")
    for industry, variables in sheets.items():
        path = os.path.join("analysis/output", f"{industry} {year_range}.xlsx")

        with pd.ExcelWriter(path, engine='openpyxl') as writer:
            for variable, df in variables.items():
                df.to_excel(writer, sheet_name=variable, index=False)

        print(f"{path} has been created.")
        paths.append(path)

    return paths
