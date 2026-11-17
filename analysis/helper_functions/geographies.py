import re
from io import BytesIO
from zipfile import ZipFile

import pandas as pd
import requests

from requests import HTTPError

from analysis.helper_functions.settings import CONFIG
from analysis.helper_functions.utils import find_max_string

SEARCH_URL = "https://www.arcgis.com/sharing/rest/search"
SECONDS_PER_ROW = 0.00064

SEARCH_PARAMS = {
    "sortField": "modified",
    "sortOrder": "desc",
    "num": 1000,
    "f": "json"}

DATA_PARAMS = {"spatialRefId": "4326",
               "where": "1=1",
               "format": "csv"}

GEOG_COL_MAPPINGS = {
    "LA": "LAD",
    "CA": "CAUTH",
    "LSOA": "LSOA",
    "MSOA": "MSOA",
}

GORWKR_DICT = {
    1: "Tyne & Wear",
    2: "Rest of North East",
    3: "Greater Manchester",
    4: "Merseyside",
    5: "Rest of North West",
    6: "South Yorkshire",
    7: "West Yorkshire",
    8: "Rest of Yorkshire & Humberside",
    9: "East Midlands",
    10: "West Midlands (met county)",
    11: "Rest of West Midlands",
    12: "East of England",
    13: "Central London",
    14: "Inner London",
    15: "Outer London",
    16: "South East",
    17: "South West",
    18: "Wales",
    19: "Strathclyde",
    20: "Rest of Scotland",
    21: "Northern Ireland",
    22: "Workplace outside UK",
}

GOVTOR_DICT = {
    1: "Tyne & Wear",
    2: "Rest of North East",
    3: "Greater Manchester",
    4: "Merseyside",
    5: "Rest of North West",
    6: "South Yorkshire",
    7: "West Yorkshire",
    8: "Rest of Yorkshire & Humberside",
    9: "East Midlands",
    10: "West Midlands Metropolitan County",
    11: "Rest of West Midlands",
    12: "East of England",
    13: "Inner London",
    14: "Outer London",
    15: "South East",
    16: "South West",
    17: "Wales",
    18: "Strathclyde",
    19: "Rest of Scotland",
    20: "Northern Ireland",
}


def get_most_recent_data(data, title_search=None):
    for item in data["results"]:
        title = item["title"]

        if title_search is None or title_search in title:
            print(f"\nLoading {title}")
            return item

    raise ValueError(f"No dataset found matching title search: {title_search!r}")


def get_dataset(*tags, title_search=None, produce_geog_reference=True):
    # Construct tag list
    search_params = SEARCH_PARAMS | {"q": " AND ".join(f'tags:"{tag}"' for tag in tags)}

    file_list = get_open_geo_data(SEARCH_URL, search_params).json()
    current_file = get_most_recent_data(file_list, title_search)
    df = get_data_file(current_file)

    if not CONFIG['run_analysis'] and produce_geog_reference:
        create_geography_reference(df)

        return None

    return df


def create_geography_reference(df=None):
    geography_type = CONFIG['geography_type']

    match geography_type:
        case "Region_residence":
            available_geographies = pd.DataFrame(GOVTOR_DICT.items(),
                                                 columns=["Geography code", "Geography name"])
        case "Region_work":
            available_geographies = pd.DataFrame(GORWKR_DICT.items(),
                                                 columns=["Geography code", "Geography name"])
        case "LA" | "CA" | "LSOA" | "MSOA":
            available_geographies = create_code_name_reference(df, geog=GEOG_COL_MAPPINGS[CONFIG['geography_type']])

    path = f"analysis/data/{geography_type}_available_geographies.xlsx"

    available_geographies.to_excel(path, index=False)

    print(f"Saved list of geographies in: {path!r}")


def create_code_name_reference(df: pd.DataFrame, geog: str) -> pd.DataFrame:
    code_column = get_geog_column(df, rf"^{geog}\d+CD$")
    name_column = get_geog_column(df, rf"^{geog}\d+NM$")

    return (df[[code_column, name_column]]
            .dropna(subset=[code_column, name_column])
            .drop_duplicates()
            .sort_values(name_column)
            .rename(columns={code_column: "Geography code", name_column: "Geography name"})
            .reset_index(drop=True))


def create_geog_lookup() -> pd.DataFrame | None:
    print(f"\nGeography:")

    geography_type = CONFIG["geography_type"]

    if geography_type not in ("Region_work", "Region_residence"):
        print(f"Getting most recent {geography_type} lookup from Open Geography")

    match geography_type:
        case 'Region_residence' | 'Region_work':
            if not CONFIG['run_analysis']:
                create_geography_reference()
            return None
        case 'LA':
            return get_dataset("OA", "WD", "LAD", title_search='Best Fit')
        case 'LSOA':
            return get_dataset("OA", "LSOA", title_search='Best Fit')
        case 'MSOA':
            return get_dataset("OA", "MSOA", title_search='Best Fit')
        case 'CA':
            return create_ca_lookup()
        case _:
            raise ValueError(f"Geography type {CONFIG['geography_type']} not supported.")


def create_ca_lookup():
    if not CONFIG["run_analysis"]:
        # Skips loading LA dataset to produce a file containing the list of available CAs
        get_dataset("LAD", "CAUTH")
        return None

    oa_lookup_df = get_dataset("OA", "WD", "LAD", title_search='Best Fit', produce_geog_reference=False)
    ca_lookup_df = get_dataset("LAD", "CAUTH", produce_geog_reference=False)

    return oa_lookup_df.merge(ca_lookup_df,
                              left_on=get_geog_column(oa_lookup_df, r"^LAD\d+CD$"),
                              right_on=get_geog_column(ca_lookup_df, r"^LAD\d+CD$"),
                              how="left")


def get_geog_column(df: pd.DataFrame, pattern: str) -> str:
    matches = df.columns[df.columns.str.match(pattern, flags=re.IGNORECASE)]

    if len(matches) != 1:
        print(f"Expected exactly one column matching {pattern!r}, found: {matches.tolist()}")
        max_string = find_max_string(list(matches))
        print(f"Using {max_string}")

        return max_string

    return matches[0]


def add_geography_columns(df, geog_lookup) -> pd.DataFrame:
    match CONFIG['geography_type']:
        case 'Region_work':
            return df.rename(columns={"GORWKR": "geography", "GORWK2R": "geography_2"})
        case 'Region_residence':
            df = df.rename(columns={"GOVTOR": "geography"})
        case "LA" | "CA" | "LSOA" | "MSOA":
            geog_col = get_geog_column(geog_lookup, rf"^{GEOG_COL_MAPPINGS[CONFIG['geography_type']]}\d+CD$")
            df = merge_based_on_oa(df, geog_col, geog_lookup)
        case _:
            raise ValueError(f"Unsupported geography type: {CONFIG['geography_type']}")

    # Copy geography into a column called geography_2 if it is not already present. Necessary for stacking.
    df["geography_2"] = df["geography"]

    return df


def merge_based_on_oa(df, geog_col, geog_lookup):
    df_oa_col = get_geog_column(df, r"^OA\d+$")
    lookup_oa_col = get_geog_column(geog_lookup, r"^OA\d+CD$")

    geog_lookup_filtered = geog_lookup[[lookup_oa_col, geog_col]].rename(columns={geog_col: "geography"})
    data_geog_df = df.merge(geog_lookup_filtered,
                            left_on=df_oa_col,
                            right_on=lookup_oa_col,
                            how="left")
    return data_geog_df


def get_data_file(current_file: dict) -> pd.DataFrame:
    item_id = current_file["id"]
    hub_url = (f"https://hub.arcgis.com/api/v3/datasets/{item_id}"
               f"_0/downloads/data")
    item_url = f"https://www.arcgis.com/sharing/rest/content/items/{item_id}/data"

    try:
        return download_file(hub_url, DATA_PARAMS)
    except HTTPError:
        return download_file(item_url)


def get_open_geo_data(url: str, query_params: dict | None):
    response = requests.get(url, params=query_params, timeout=60)
    response.raise_for_status()
    return response


def download_file(url: str, params: str | None = None):
    response = get_open_geo_data(url, query_params=params)

    file_content = BytesIO(response.content)

    if response.content.startswith(b"PK"):
        return read_csvs_from_zip(file_content)

    return pd.read_csv(file_content, low_memory=False)


def read_csvs_from_zip(file_content: BytesIO) -> pd.DataFrame:
    with ZipFile(file_content) as zip_file:
        csv_files = [filename for filename in zip_file.namelist() if filename.lower().endswith(".csv")]

        if not csv_files:
            raise ValueError("No CSV files found in downloaded ZIP file.")

        dataframes = []

        for filename in csv_files:
            with zip_file.open(filename) as csv_file:
                df = pd.read_csv(csv_file, low_memory=False)

            dataframes.append(df)

    return pd.concat(dataframes, ignore_index=True)
