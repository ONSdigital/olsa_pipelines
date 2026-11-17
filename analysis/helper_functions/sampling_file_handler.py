from analysis.helper_functions.settings import CONFIG
from .utils import read_data
import os
import pandas as pd

# Note: rpy2 functions are lazily loaded to prevent repeated bridging to r when pyreadstat multiprocessing
# imports libraries

os.environ["RPY2_CFFI_MODE"] = "ABI"
os.environ["R_HOME"] = CONFIG['r_home_directory']


def load_r_packages_if_needed(datasets):
    # Check if sampling files and years match
    if not set(CONFIG["sampling_files"]) & {int(k) for k in datasets}:
        return

    print("\nLoading R packages")

    from rpy2.robjects import r

    for package in ["ReGenesees", "haven", "dplyr", "stringr"]:
        r(f"library({package})")


def combine_sampling_file_and_data(data, year):
    # Prevents circular import with data_pipeline.py
    from .data_pipeline import remove_zero_weight_rows

    if year == 2024:
        sampling_file_path = CONFIG['2024_sampling_file']
    elif year == 2025:
        sampling_file_path = CONFIG['2025_sampling_file']

    sampling_file, _ = read_data(sampling_file_path)

    sampling_file = sampling_file[['CASENO', 'p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'p7', 'dweight_adj']]

    sampling_file = remove_zero_weight_rows(sampling_file, 'dweight_adj')

    # Merge sampling file and data file
    data_with_sampling = data.merge(sampling_file, on="CASENO", how="left")

    # Ensure weight variables are numeric
    data_with_sampling['PWTA22'] = pd.to_numeric(data_with_sampling['PWTA22'], errors='coerce')
    data_with_sampling['dweight_adj'] = pd.to_numeric(data_with_sampling['dweight_adj'], errors='coerce')

    # Extract household ID from case number (remove last two characters)
    data_with_sampling['hhid'] = data_with_sampling['CASENO'].astype(str).str[:-2]

    # Add a column of ones for unweighted counts
    data_with_sampling['ones'] = 1

    return data_with_sampling


def r_setup(full_data, weight_column) -> None:
    print(f'\nConverting pandas dataframe to r dataframe')
    convert_python_to_r(full_data, 'full_data')
    print(f'\nCalibrating survey'
          f'\nMaybe have a cup of tea, this may take a while...')
    calibrate_survey(weight_column)


def get_counts_and_ci(subsetted_data, variable, pwta_column, groupby_col=None):
    subset_data(subsetted_data['df'])
    run_svystat(variable, groupby_col)
    results = clean_results(pwta_column, variable)

    if groupby_col is not None:
        results = calculate_totals(pwta_column, results, variable, groupby_col)
        results = results.rename(columns={groupby_col: 'industry'})

    return results


def calculate_totals(pwta_column, other_results, variable, groupby_col):
    run_svystat(variable=variable, groupby_col=groupby_col, all_industries=True)
    totals_results = clean_results(pwta_column, variable)
    totals_results[groupby_col] = 'All industries total'

    totals_results = totals_results[other_results.columns]

    return pd.concat([other_results, totals_results], ignore_index=True)


def clean_results(pwta_column, variable):
    from rpy2.robjects import r, pandas2ri

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


def run_svystat(variable=None, groupby_col=None, all_industries=False):
    from rpy2.robjects import r

    groupby = []

    if not all_industries and groupby_col:
        groupby.append(groupby_col)

    if variable != "headline_totals":
        groupby.append(variable)

    groupby_string = " + ".join(groupby) if groupby else "constant"

    r(f"""
    results <- svystatTM(
        design = cal_survey_subset,
        y = ~ones,
        by = ~{groupby_string},
        vartype = c("se"),
        conf.int = TRUE
    )
    """)


def subset_data(subsetted_data):
    from rpy2.robjects import r

    convert_python_to_r(subsetted_data, 'subsetted_data')

    # Subset calibrated survey df
    r('cal_survey_subset <- subset(cal_survey, ROW_ID %in% subsetted_data$ROW_ID)')


def convert_python_to_r(py_df, r_name):
    from rpy2.robjects import (
        pandas2ri,
        globalenv,
        default_converter,
        conversion,
    )

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
    from rpy2.robjects import r

    r('''
        # Identify available p-columns
        required <- paste0("p", 1:7)
        present <- intersect(required, names(full_data))
        missing <- setdiff(required, present)
        
        if (length(missing)) {
        message("    Partition columns missing and will be skipped: ",
        paste(missing, collapse = ", "))
        }
    ''')

    if 'simplify partitions' in CONFIG['debug_mode']:
        r('''
            # Compute simplified partitions only if present
            if ("p1" %in%present) full_data$p1 <- floor((full_data$p1 - 1) / 57) + 1
            if ("p2" %in%present) full_data$p2 <- (full_data$p2 - 1) %% 431 + 1
            if ("p3" %in%present) full_data$p3 <- floor((full_data$p3 - 1) / 12) + 1
            if ("p4" %in%present) full_data$p4 <- floor((full_data$p4 - 1) / 13) + 1
            if ("p6" %in%present) {
                COB_EU <- (full_data$p6 - 1) %% 3 + 1
                GOVTOF <- floor((full_data$p6 - 1) / 12) + 1
                full_data$p6 <- (GOVTOF - 1) * 3 + COB_EU}
        ''')

    # Speeds up running regenesees if debug mode is true
    if 'speed up calibration' not in CONFIG['debug_mode']:
        # Convert calibration groups into type factor
        r('''
            full_data[present] <- lapply(full_data[present], as.factor)
        ''')

    # Run calibration
    r(f'''
        cal_survey <- ext.calibrated(
            data = full_data,
            ids = ~hhid,
            weights = ~dweight_adj,
            calmodel = ~p1 + p2 + p3 + p4 + p5 + p6 + p7 -1,
            weights.cal = ~{weight_column}
        )
    ''')
