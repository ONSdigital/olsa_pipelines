from .settings import CONFIG
from .utils import read_data
import os
import pandas as pd

os.environ["R_HOME"] = CONFIG['r_home_directory']
os.environ['R_SHELL'] = 'cmd'

import contextlib

with open(os.devnull, 'w') as devnull:
    with contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
        from rpy2.robjects import r
        from rpy2.robjects import pandas2ri, globalenv, default_converter, conversion

# Suppress R console output
r('sink("nul")')


def combine_sampling_file_and_data(data, year):
    if year == 2024:
        sampling_file_path = CONFIG['2024_sampling_file']
    elif year == 2025:
        sampling_file_path = CONFIG['2025_sampling_file']

    sampling_file, _ = read_data(sampling_file_path)

    sampling_file = sampling_file[['CASENO', 'p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'p7', 'dwt_adjusted']]

    # Merge sampling file and data file
    data_with_sampling = data.merge(sampling_file, on="CASENO", how="left")

    # Ensure weight variables are numeric
    data_with_sampling['PWTA22'] = pd.to_numeric(data_with_sampling['PWTA22'], errors='coerce')
    data_with_sampling['dwt_adjusted'] = pd.to_numeric(data_with_sampling['dwt_adjusted'], errors='coerce')

    # Keep only rows where weights are positive
    data_with_sampling = data_with_sampling[
        (data_with_sampling['dwt_adjusted'] > 0) & (data_with_sampling['PWTA22'] > 0)
        ]

    # Extract household ID from case number (remove last two characters)
    data_with_sampling['hhid'] = data_with_sampling['CASENO'].astype(str).str[:-2]

    # Add a column of ones for unweighted counts
    data_with_sampling['ones'] = 1

    return data_with_sampling


def load_r_packages_if_needed(datasets):
    common_elements = set(CONFIG['sampling_files']) & set([int(k) for k in datasets.keys()])

    if common_elements:
        load_r_packages()


def r_setup(full_data, weight_column) -> None:
    print(f'\nConverting pandas dataframe to r dataframe')
    convert_python_to_r(full_data, 'full_data')
    print(f'\nCalibrating survey'
          f'\nMaybe have a cup of tea, this may take a while...')
    calibrate_survey(weight_column)


def load_r_packages() -> None:
    print(f'\nLoading r packages')
    packages = ['ReGenesees', 'haven', 'dplyr', 'stringr']

    for pkg in packages:
        r(f'library({pkg})')


def get_counts_and_ci(subsetted_data, industry_col, variable, pwta_column):
    subset_data(subsetted_data['df'])
    run_svystat(industry_col, variable)
    results = clean_results(pwta_column, variable)
    results = calculate_totals(industry_col, pwta_column, results, variable)

    return results


def calculate_totals(industry_col, pwta_column, other_results, variable):
    run_svystat(variable=variable, all_industries=True)
    totals_results = clean_results(pwta_column, variable)
    totals_results[industry_col] = 'All industries total'

    totals_results = totals_results[other_results.columns]

    return pd.concat([other_results, totals_results], ignore_index=True)


def clean_results(pwta_column, variable):
    rename_dict = {'Total.ones': pwta_column,
                   'CI.l(95%).Total.ones': 'Confidence Interval lower',
                   'CI.u(95%).Total.ones': 'Confidence Interval upper'}

    results = (pandas2ri.rpy2py(r['results'])
               .reset_index(drop=True)
               .drop(columns='SE.Total.ones')
               .rename(columns=rename_dict))

    # Set negative CIs to 0
    if CONFIG['set_negative_values_to_zero']:
        results[['Confidence Interval lower', 'Confidence Interval upper']] = results[
            ['Confidence Interval lower', 'Confidence Interval upper']].clip(lower=0)

    results = results.round()

    if variable != 'headline_totals':
        # Return variable labels
        results[variable] = list(r(f'as.character(results${variable})'))

    return results


def run_svystat(industry_col=None, variable=None, all_industries=False):
    if all_industries and variable == 'headline_totals':
        groupby_string = 'constant'
    elif all_industries and variable != 'headline_totals':
        groupby_string = variable
    elif variable == 'headline_totals':
        groupby_string = industry_col
    else:
        groupby_string = f'{industry_col} + {variable}'

    # Run survey design and analysis
    r(f'''
    results <- svystatTM(
        design = cal_survey_subset, 
        y = ~ones, 
        by = ~{groupby_string},
        vartype = c("se"),
        conf.int = TRUE)
    ''')


def subset_data(subsetted_data):
    convert_python_to_r(subsetted_data, 'subsetted_data')

    # Subset calibrated survey df
    r('cal_survey_subset <- subset(cal_survey, ROW_ID %in% subsetted_data$ROW_ID)')


def convert_python_to_r(py_df, r_name):
    with (default_converter + pandas2ri.converter).context():
        r_df = conversion.get_conversion().py2rpy(py_df)

    globalenv[r_name] = r_df


def calibrate_survey(weight_column):
    """
    ids = what we're clustering on - takes average across the hh, treating hh as a unit
    weights = weights before calibration
    calmodel = calibration groups
    weights.cal = weights after calibration

    :return:
    """

    if not CONFIG['debug_mode']:
        # Convert calibration groups into type factor
        r('''
        for (i in 1:7) {
            full_data[[paste0("p", i)]] = as.factor(full_data[[paste0("p", i)]])
        }
        ''')

    # Run calibration
    r(f'''
        cal_survey <- ext.calibrated(
            data = full_data,
            ids = ~hhid,
            weights = ~dwt_adjusted,
            calmodel = ~p1 + p2 + p3 + p4 + p5 + p6 + p7 -1,
            weights.cal = ~{weight_column}
        )
    ''')
