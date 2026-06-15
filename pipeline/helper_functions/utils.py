import os
import re
import tempfile
import zipfile
from collections import defaultdict

import pyreadstat

import pandas as pd

from pipeline import demographic_mappings
from .settings import CONFIG


def clean_industry_df(df):
    df = df.dropna(subset=['Code: Definitions'])  # Remove NaNs
    df = df[~df['Code: Definitions'].str.contains('source', case=False, na=False)]  # Remove rows containing 'source'
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


def format_subsector(subsector: str, industry: str) -> str:
    if pd.isna(subsector):
        return industry
    else:
        return subsector


def extract_numeric_codes(data: dict) -> dict:
    number_pattern = r'\d+\.\d+|\d+'

    codes_dict: dict = {}
    for industry, sector_codes in data.items():
        new_values = {}
        for value in sector_codes.items():
            code_list = re.findall(number_pattern, value[0])

            if len(code_list) == 2:
                start, end = map(float, code_list)
                # Convert to integers and create a list of the range
                code_list = list(range(int(start * 10), int(end * 10) + 1))

            else:
                code_list = [int(code_list[0].replace('.', ''))]

            for code in code_list:
                new_values[code] = format_subsector(value[1][0], industry)

        codes_dict[industry] = new_values

    print("Extracted codes:")
    for industry, value in codes_dict.items():
        print(f"{industry} codes: {sorted(value)}")

    return codes_dict


def get_variable_data(variable):
    return getattr(demographic_mappings, f'{variable}_data')


def find_max_string(strings: list):
    if strings:
        return max(strings, key=lambda string: max(map(int, re.findall(r'\d+', string))))
    else:
        return None


def read_data(data_path):
    print(f'Loading file: "{data_path}"')

    if ".zip" in data_path:
        data = read_zipped_sav(data_path)

    else:
        data = read_sav_file(data_path)

    return data


def read_zipped_sav(data_path):
    zip_path, sav_file = os.path.split(data_path)
    # Open the zip and read the .sav file
    with zipfile.ZipFile(zip_path, 'r') as z:
        with z.open(sav_file) as f:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".sav") as temp_sav:
                temp_sav.write(f.read())
    data = read_sav_file(temp_sav.name)
    os.remove(temp_sav.name)
    return data


def read_sav_file(data_path):
    try:
        data = pyreadstat.read_file_multiprocessing(pyreadstat.read_sav, data_path,
                                                    encoding="utf-8")
    except pyreadstat._readstat_parser.ReadstatError:
        data = pyreadstat.read_file_multiprocessing(pyreadstat.read_sav, data_path,
                                                    encoding="latin1")
    return data


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


def reorder_columns(merged_df: pd.DataFrame, first_columns: list) -> pd.DataFrame:
    # Combine with remaining columns
    new_column_order = first_columns + [col for col in merged_df.columns if col not in first_columns]

    # Reorder columns
    reordered_df = merged_df[new_column_order]

    return reordered_df


def find_datasets() -> dict[str, str]:
    years = create_date_range()

    year_folders_dict = {}
    for dirpath, dirnames, filenames in os.walk(CONFIG['base_file_path']):
        for dirname in dirnames:
            if dirname in years:
                full_path = os.path.join(dirpath, dirname)
                if dirname in year_folders_dict:
                    year_folders_dict[dirname].append(full_path)
                else:
                    year_folders_dict[dirname] = [full_path]

    if not year_folders_dict:
        raise Exception("No data found. Make sure you are connected to the VPN!")

    for year in year_folders_dict:
        files = [file for file in year_folders_dict[year] if 'APS Household' not in file]
        latest_path = find_max_string(files)  # Find latest re-weighting

        matched_files = get_matched_files(latest_path)
        matched_files = prefer_inclusive_files(matched_files)

        grouped = group_by_extension(matched_files)

        # Prefer .sav files, fallback to .zip
        matched_files = grouped[".sav"] if grouped[".sav"] else grouped[".zip"]

        if not grouped[".sav"] and grouped[".zip"]:
            matched_files = extract_sav_from_zip(grouped[".zip"], latest_path)

        if len(matched_files) == 0:
            raise ValueError(f"Could not find .sav files in {latest_path}")
        if len(matched_files) > 1:
            raise ValueError(f"More than one .sav file found in {latest_path}:\n" + "\n".join(matched_files))

        year_folders_dict[year] = os.path.join(latest_path, matched_files[0])

    print('\nData paths:')
    for year in year_folders_dict:
        print(year_folders_dict[year])

    return year_folders_dict


def create_date_range():
    years = [str(year) for year in range(CONFIG['date_range'][0], CONFIG['date_range'][1] + 1)]
    return years


def extract_sav_from_zip(zip_files, path):
    files = []
    pattern = re.compile(r'.*\.sav$', re.IGNORECASE)
    for file in zip_files:
        with zipfile.ZipFile(os.path.join(path, file), 'r') as zip_ref:
            files.extend([os.path.join(file, name) for name in zip_ref.namelist() if pattern.match(name)])

    return files


def group_by_extension(files):
    grouped = defaultdict(list)
    for f in files:
        ext = os.path.splitext(f)[1]
        grouped[ext].append(f)
    return grouped


def get_matched_files(path):
    files = [f for f in os.listdir(path) if re.search(r'JD|Jan.*Dec.*', f, re.IGNORECASE)]
    return [f for f in files if os.path.getsize(os.path.join(path, f)) > 0]


def prefer_inclusive_files(files):
    preferred = [f for f in files if 'Inclu' in f]
    return preferred or files


def return_area_codes(file_name):
    df = pd.read_excel(file_name)
    return df.groupby('Area')['Codes'].apply(list).to_dict()


def remap_tuple_ranges(code_dict: dict):
    flattened_dict = {}
    for key, value in code_dict.items():
        for k in range(key[0], key[1] + 1):
            flattened_dict[k] = value

    return flattened_dict
