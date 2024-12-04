import os
import uuid
from datetime import datetime
import boto3
import re
from urllib.parse import unquote_plus
from typing import List, Dict
import json
import pandas as pd
from database.influx_writer import Database
from utils.log_writer import Logger
from etl.clean import clean_data
from etl.extract import extract_and_create_structure 
from utils.s3 import move_s3_object,get_processed_bucket_name, get_raw_bucket_name

# Initialize S3 client
endpoint_url = "https://localhost.localstack.cloud:4566"  # LocalStack URL
s3 = boto3.client("s3", endpoint_url=endpoint_url)

log = Logger(log_file="/tmp/lambda_logs.log")

# Execution setup
db = Database()

# Load subroutines from the config file
def load_subroutines_config(filepath: str) -> Dict:
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"ERROR: Failed to load subroutines config: {e}")
        return {}

subroutine_config = load_subroutines_config("./subroutines_config.json")

def handler(event, context):
    for record in event["Records"]:
        source_bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])

        tmp_file_path = f"/tmp/{uuid.uuid4()}.tar"
        s3.download_file(source_bucket, key, tmp_file_path)

        extracted_dir_path = f"/tmp/extracted/{uuid.uuid4()}"
        file_key_prefix = key.split('_')[0]
        file_key_server = key.split('_')[1]

        extract_and_create_structure(tmp_file_path, extracted_dir_path, file_key_prefix, file_key_server,s3,log,db,subroutine_config)
        s3.delete_object(Bucket=source_bucket, Key=key)
