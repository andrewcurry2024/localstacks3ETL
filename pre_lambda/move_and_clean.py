import csv
import time
import os
import re
import pandas as pd
import shutil
from datetime import datetime
from typing import List, Dict, Callable
import sys
import json  # For loading JSON files

# Load subroutines from the config file
def load_subroutines_config(filepath: str) -> Dict:
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"ERROR: Failed to load subroutines config: {e}")
        return {}

class Logger:
    def error(self, message):
        print(f"ERROR: {message}")
    def debug(self, message):
        print(f"INFO: {message}")

class Config:
    INDIR = "./in"
    OUTDIR = "./out"
    PROCESSED = "./processed"

def clean_data(df: pd.DataFrame, header: str, customer: str, server: str) -> pd.DataFrame:
    df = df.copy()
    for column in df.columns:
        if column not in ['datetime', 'customer', 'server']:
            condition_large_value = (df[column].apply(lambda x: isinstance(x, (int, float)) and x > 9023372036854775800))
            condition_nan = (df[column].apply(lambda x: isinstance(x, str) and x.lower() == 'nan'))
            df.loc[condition_large_value, column] = -1
            df.loc[condition_nan, column] = -1

    if 'datetime' in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'])
    else:
        if 'date' in df.columns and 'time' in df.columns:
            df['datetime'] = pd.to_datetime(df['date'].astype(str) + ' ' + df['time'].astype(str))
            df.drop(columns=['date', 'time'], inplace=True)
        else:
            print("ERROR: No 'datetime', 'date', or 'time' columns found!")

    if 'datetime' in df.columns:
        cols = ['datetime'] + [col for col in df.columns if col != 'datetime']
        df = df[cols]
    else:
        print("ERROR: 'datetime' column not found!")

    header_columns = header.split(',')

    if len(header_columns) < len(df.columns):
        df = df.iloc[:, :len(header_columns)]

    if len(header_columns) == len(df.columns):
        df.columns = header_columns
    else:
        print(f"ERROR: Column count mismatch: header has {len(header_columns)} columns, but dataframe has {len(df.columns)} columns.")

    df.loc[:, 'customer'] = customer
    df.loc[:, 'server'] = server

    print(f"Cleaned Data Overview for {customer}-{server}:")
    print(df.info())
    return df

def import_data(header, filename, customer, server, subroutine_key, file):
    try:
        records=[]
        df = pd.read_csv(filename, header=0)
        df.columns = df.columns.str.strip()
        df = clean_data(df, header, customer, server)
        print(f"DataFrame for {filename} with header: {header}")
        print(df)
        
        file_path = os.path.join(Config.PROCESSED, file)
        os.makedirs(Config.PROCESSED, exist_ok=True)
        df.to_csv(file_path, index=False)

    except Exception as e:
        print(f"ERROR: Failed to process {filename}: {e}")

# Modified to use subroutine_config loaded from file
def produce_import_files(subroutine_config, indir, config, log):
    try:
        files = os.listdir(indir)
    except Exception as e:
        log.error(f"Failed to read directory {indir}: {e}")
        return

    for file in files:
        file_path = os.path.join(indir, file)
        if not os.path.isfile(file_path):
            continue  # Skip if it's not a file

        match = re.match(r"^(\S+?)_(\S+?)_(\d{4}-\d{2}-\d{2})_(.*)", file) or \
                re.match(r"^(\S+?)_(\S+?)_(.*-\d{2}:\d{2}-\d{2}:\d{2})_(.*)", file) or \
                re.match(r"^(\S+?)_(\S+?)_([^\_]+)_(.*)", file)

        if match:
            customer, server, date, filename = match.groups()
            subroutine_key = filename

            subroutine_key = re.sub(r"_for_graph", "", subroutine_key)
            subroutine_key = re.sub(r"_\d+k", "_k", subroutine_key)
            subroutine_key = re.sub(r"_\d+$", "", subroutine_key)
            subroutine_key = re.sub(r"_\d+.log$", "", subroutine_key)
            subroutine_key = re.sub(r".log$", "", subroutine_key)
            print(subroutine_config)

            # Check if subroutine exists and call it
            if subroutine_key in subroutine_config:
                header = subroutine_config[subroutine_key]['VALUES']['IMPORT'][0][1]
                # Assuming subroutine_config contains the function names as strings
                func_name = subroutine_config[subroutine_key]['SUB']

                # Dynamically call the function using getattr
                func = globals().get(func_name)  # Use globals() if the function is globally defined
                print(func)
                if func:
                    func(header, file_path, customer, server, subroutine_key, file)
                else:
                    log.error(f"Function {func_name} not found.")

            else:
                log.error(f"No subroutine found for {file}")
                move_file(config.INDIR, config.OUTDIR, 'err', file, log)
        else:
            log.error(f"Errors for {file} no pattern found")
            move_file(config.INDIR, config.OUTDIR, 'err', file, log)

# Execution setup
log = Logger()
config = Config()

# Load subroutine configuration from JSON
subroutine_config = load_subroutines_config("subroutines_config.json")

# Process the files
produce_import_files(subroutine_config, config.INDIR, config, log)
