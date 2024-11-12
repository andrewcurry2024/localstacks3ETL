import os
import uuid
import boto3
import re
from urllib.parse import unquote_plus
from typing import List, Dict
import json
import pandas as pd
from influxdb_client import InfluxDBClient, WriteOptions, Point, WritePrecision
from influxdb_client.client.exceptions import InfluxDBError
from influxdb_client.client.write_api import SYNCHRONOUS

# Initialize S3 client
endpoint_url = "https://localhost.localstack.cloud:4566"  # LocalStack URL
s3 = boto3.client("s3", endpoint_url=endpoint_url)

def get_bucket_name() -> str:
    return "localstack-s3etl-app-processed"

def get_raw_bucket_name() -> str:
    return "localstack-s3etl-app-raw"

class Logger:
    def error(self, message):
        print(f"ERROR: {message}")
    def debug(self, message):
        print(f"INFO: {message}")

# Execution setup
log = Logger()

# Load subroutines from the config file
def load_subroutines_config(filepath: str) -> Dict:
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"ERROR: Failed to load subroutines config: {e}")
        return {}

subroutine_config = load_subroutines_config("./subroutines_config.json")

def extract_and_create_structure(tar_file_path: str, extracted_dir_path: str, file_key_prefix: str, file_key_server: str) -> None:
    import tarfile

    # Ensure target directory structure exists
    if not os.path.exists(extracted_dir_path):
        os.makedirs(extracted_dir_path)

    # Open the tar file and extract the contents
    with tarfile.open(tar_file_path, "r") as tar:
        extracted_files = tar.getnames()
        print(f"Extracted files: {extracted_files}")

        # Iterate through extracted files and upload to S3
        for file_name in extracted_files:
            extracted_file_path = os.path.join(extracted_dir_path, file_name)

            # Build the S3 key with the full directory structure
            s3_key = f"extracted/{file_name}"
            print(f"Uploading {file_name} to s3://{get_raw_bucket_name()}/extracted")

            # Extract the file
            tar.extract(file_name, path=extracted_dir_path)

            # Upload to S3
            s3.upload_file(extracted_file_path, get_raw_bucket_name(), s3_key)

            produce_import_files(subroutine_config, get_raw_bucket_name(), extracted_file_path, file_name, log)

            print(f"Successfully uploaded {file_name} to s3://{get_raw_bucket_name()}/{s3_key}")

def clean_data(df: pd.DataFrame, header: str, customer: str, server: str, sub_key: str) -> pd.DataFrame:
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
    df.loc[:, '_measurement'] = sub_key

    print(f"Cleaned Data Overview for {customer}-{server}:")
    print(df.info())
    return df

def import_data(header, filename, customer, server, subroutine_key, file):
    try:
        records = []
        df = pd.read_csv(filename, header=0)
        df.columns = df.columns.str.strip()
        df = clean_data(df, header, customer, server, subroutine_key)
        print(f"DataFrame for {filename} with header: {header}")
        print(df)
        uuid_tmp=uuid.uuid4()
        # Create a dynamic filename
        filename_new = f"{customer}_{server}_{subroutine_key}_{uuid_tmp}.csv"
        filename_s3 = f"{customer}_{server}_{subroutine_key}_{uuid_tmp}.csv"
        tmp_file_path = os.path.join('/tmp', filename_new)
        df.to_csv(tmp_file_path, index=False)

        s3_key = f"to_ingest/{filename_s3}"
        print(f"My S3 {s3_key}")
        print(f"My tmp {filename_new}")
        s3.upload_file(tmp_file_path, get_raw_bucket_name(), s3_key)
        print(f"Hopefully uploaded {filename_new} to s3://{get_raw_bucket_name()}/{s3_key}")

    except Exception as e:
        print(f"ERROR: Failed to process {filename}: {e}")

def produce_import_files(subroutine_config, bucket_name, extracted_file_path, file_name, log):
    """
    Process a file from S3 after it has been uploaded.
    """
    s3_key = f"extracted/{file_name}"
    try:
        match = re.match(r"^(\S+?)_(\S+?)_(\d{4}-\d{2}-\d{2})_(.*)", s3_key) or \
                re.match(r"^(\S+?)_(\S+?)_(.*-\d{2}:\d{2}-\d{2}:\d{2})_(.*)", s3_key) or \
                re.match(r"^(\S+?)_(\S+?)_([^\_]+)_(.*)", extracted_file_path)

        if match:
            customer, server, date, filename = match.groups()
            customer = re.match(r".*/([^/]+)$", customer).group(1)
            subroutine_key = filename
            
            print(f"CUSTOMER{customer}")

            # Modify the subroutine key as needed
            subroutine_key = re.sub(r"_for_graph", "", subroutine_key)
            subroutine_key = re.sub(r"_\d+k", "_k", subroutine_key)
            subroutine_key = re.sub(r"_\d+$", "", subroutine_key)
            subroutine_key = re.sub(r"_\d+.log$", "", subroutine_key)
            subroutine_key = re.sub(r".log$", "", subroutine_key)


            # Check if subroutine exists and call it
            if subroutine_key in subroutine_config:
                header = subroutine_config[subroutine_key]['VALUES']['IMPORT'][0][1]
                func_name = subroutine_config[subroutine_key]['SUB']

                # Dynamically call the function using globals()
                func = globals().get(func_name)
                if func:
                    func(header, extracted_file_path, customer, server, subroutine_key, file_name)
                else:
                    log.error(f"Function {func_name} not found.")
            else:
                log.error(f"No subroutine found for {subroutine_key}")
        else:
            log.error(f"Errors for {file_name} no pattern found")

    except Exception as e:
        log.error(f"Failed to process S3 file {s3_key}: {e}")

def handler(event, context):
    for record in event["Records"]:
        source_bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])

        tmp_file_path = f"/tmp/{uuid.uuid4()}.tar"
        s3.download_file(source_bucket, key, tmp_file_path)

        extracted_dir_path = f"/tmp/extracted/{uuid.uuid4()}"
        file_key_prefix = key.split('_')[0]
        file_key_server = key.split('_')[1]

        extract_and_create_structure(tmp_file_path, extracted_dir_path, file_key_prefix, file_key_server)
        s3.delete_object(Bucket=source_bucket, Key=key)
