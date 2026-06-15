age_data = {
    'info': {'old_column': 'AAGE', 'new_column': 'Age brackets'},
    'codes': {
        1: "Under 16",
        2: "16-29",
        3: "16-29",
        4: "16-29",
        5: "16-29",
        6: "30-49",
        7: "30-49",
        8: "30-49",
        9: "30-49",
        10: "50 and above",
        11: "50 and above",
        12: "50 and above",
        13: "50 and above"}
}

sex_data = {
    'info': {'old_column': 'SEX', 'new_column': 'Sex'},
    'codes': {
        1: "Male",
        2: "Female"
    }
}

ethnicity_data = {
    'info': {'old_column': 'ETHUKEUL', 'new_column': 'Ethnicity'},
    'codes': {
        1: "White",
        2: "Mixed/Multiple ethnic groups",
        3: "Indian",
        4: "Pakistani",
        5: "Bangladeshi",
        6: "Chinese",
        7: "Any other Asian background",
        8: "Black/African/Caribbean/Black British",
        9: "Other ethnic group"
    }
}

cob_data = {
    'info': {'old_column': 'CRYOX7', 'new_column': 'Country of Birth', 'fillna': 'Rest of the world'},
    'codes': {
        926: "UK",
        9: "Missing",
        40: "EU",
        56: "EU",
        100: "EU",
        191: "EU",
        203: "EU",
        208: "EU",
        233: "EU",
        246: "EU",
        250: "EU",
        276: "EU",
        300: "EU",
        348: "EU",
        372: "EU",
        380: "EU",
        428: "EU",
        440: "EU",
        442: "EU",
        470: "EU",
        528: "EU",
        616: "EU",
        620: "EU",
        642: "EU",
        703: "EU",
        705: "EU",
        752: "EU",
        901: "EU",
        911: "EU",
    }
}

disability_data = {
    'info': {'old_column': 'DISEA', 'new_column': 'Disability'},
    'codes': {
        1: "Disabled",
        2: "Not disabled"
    }
}

qualification_data = {
    'info': {'old_column': ['HIQUAL8D',  # 2010
                            'HIQUL11D',  # 2011 - 2014
                            'HIQUL15D',  # 2015 - 2021
                            'HIQUL22D',  # 2022
                            ],
             'new_column': 'Highest qualification'},
    'codes': {
        1: "Degree or equivalent",
        2: "Higher education",
        3: "GCE, A-level or equivalent",
        4: "GCSE grades A*-C or equivalent",
        5: "Other qualifications",
        6: "No qualification",
        7: "Don't know"
    }
}

employment_data = {
    'info': {'main_column': 'STATR',
             'secondary_column': 'SECJMBR',
             'new_column': 'Employment'},

    'codes': {
        1: "Employee",
        2: "Self employed"
    }
}

subregional_partnerships_data = {
    'info': {
        'main_column': 'UALDWK',
        'secondary_column': 'UALDWK2',
        'new_column': 'Subregional partnerships',
    },
    'codes': {
        "AA": "Central London Forward",  # City of London
        "AB": "Local London",  # Barking and Dagenham
        "AC": "West London Alliance",  # Barnet
        "AD": "Local London",  # Bexley
        "AE": "West London Alliance",  # Brent
        "AF": "Local London",  # Bromley
        "AG": "Central London Forward",  # Camden
        "AH": "South London Partnership",  # Croydon
        "AJ": "West London Alliance",  # Ealing
        "AK": "Local London",  # Enfield
        "AL": "Local London",  # Greenwich
        "AM": "Central London Forward",  # Hackney
        "AN": "West London Alliance",  # Hammersmith and Fulham
        "AP": "Central London Forward",  # Haringey
        "AQ": "West London Alliance",  # Harrow
        "AR": "Local London",  # Havering
        "AS": "West London Alliance",  # Hillingdon
        "AT": "West London Alliance",  # Hounslow
        "AU": "Central London Forward",  # Islington
        "AW": "Central London Forward",  # Kensington and Chelsea
        "AX": "South London Partnership",  # Kingston upon Thames
        "AY": "Central London Forward",  # Lambeth
        "AZ": "Central London Forward",  # Lewisham
        "BA": "South London Partnership",  # Merton
        "BB": "Local London",  # Newham
        "BC": "Local London",  # Redbridge
        "BD": "South London Partnership",  # Richmond upon Thames
        "BE": "Central London Forward",  # Southwark
        "BF": "South London Partnership",  # Sutton
        "BG": "Central London Forward",  # Tower Hamlets
        "BH": "Local London",  # Waltham Forest
        "BJ": "Central London Forward",  # Wandsworth
        "BK": "Central London Forward",  # Westminster
    }
}

occupation_data = {
    'info':
        {
            'main_column':
                ['SC10MMJ',
                 'SC20MMJ'],
            'secondary_column':
                ['SC10SMJ',
                 'SC20SMJ'],
            'new_column': 'SOC',
        },

    'codes': {
        1: "Managers, Directors and Senior Officials",
        2: "Professional Occupations",
        3: "Associate Professional and Technical Occupations",
        4: "Administrative and Secretarial Occupations",
        5: "Skilled Trades Occupations",
        6: "Caring, Leisure and Other Service Occupations",
        7: "Sales and Customer Service Occupations",
        8: "Process, Plant and Machine Operatives",
        9: "Elementary Occupations"
    }
}

skill_data = {
    'info':
        {'main_column':
             ['SOC10M',
              'SOC20M'],
         'secondary_column':
             ['SOC10S',
              'SOC20S'],
         'new_column': 'Skill',
         },

    'codes': {
        'SOC10': {
            (9100, 9299): 1,
            (4100, 4299): 2,
            (6100, 6299): 2,
            (7100, 7299): 2,
            (8100, 8299): 2,
            (1200, 1299): 3,
            (3100, 3599): 3,
            (5100, 5499): 3,
            (1100, 1199): 4,
            (2100, 2499): 4
        },
        'SOC20': {
            (9100, 9299): 1,
            (4100, 4299): 2,
            (6100, 6399): 2,
            (7100, 7299): 2,
            (8100, 8299): 2,
            (1200, 1299): 3,
            (3100, 3599): 3,
            (5100, 5499): 3,
            (1100, 1199): 4,
            (2100, 2499): 4,
        }
    }
}
