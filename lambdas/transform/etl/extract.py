import os
import boto3
import tarfile
import re
from urllib.parse import unquote_plus
from typing import List, Dict
from utils.s3 import move_s3_object,get_processed_bucket_name, get_raw_bucket_name
from etl.load import *

def extract_and_create_structure(tar_file_path: str, extracted_dir_path: str, file_key_prefix: str, file_key_server: str,s3,log,db,subroutine_config) -> None:

    # Debugging: Print objects
    print("S3 Object:", s3)
    print("Log Object:", log)
    print("DB Object:", db)

    # Ensure target directory structure exists
    if not os.path.exists(extracted_dir_path):
        os.makedirs(extracted_dir_path)

    # Open the tar file and extract the contents
    with tarfile.open(tar_file_path, "r") as tar:
        extracted_files = tar.getnames()
        print(f"Extracted files: {extracted_files}")

        # Iterate through extracted files and upload to S3
        for file_name in extracted_files:
            if file_name.startswith('._'):
                    print(f"Skipping Apple Double file: {file_name}")
                    continue
            extracted_file_path = os.path.join(extracted_dir_path, file_name)

            # Build the S3 key with the full directory structure
            s3_key = f"extracted/{file_name}"
            print(f"Uploading {file_name} to s3://{get_raw_bucket_name()}/extracted")

            # Extract the file
            tar.extract(file_name, path=extracted_dir_path)

            # Upload to S3
            s3.upload_file(extracted_file_path, get_raw_bucket_name(), s3_key)
            try:
                produce_import_files(subroutine_config, get_raw_bucket_name(), extracted_file_path, file_name, log, db,s3)
            except Exception as e:
                print(f"Error in produce_import_files: {e}")
                log.error(f"Error in produce_import_files: {e}")

            try:
                move_s3_object(get_raw_bucket_name(), get_processed_bucket_name(), s3_key)
                print(f"Successfully uploaded {file_name} to s3://{get_raw_bucket_name()}/{s3_key}")
            except Exception as e:
                print(f"Error move produce_import_files: {e}")
                log.error(f"Error move produce_import_files: {e}")


def produce_import_files(subroutine_config, bucket_name, extracted_file_path, file_name, log, db, s3):
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
            subroutine_key = re.sub(r"_\d+$", "", subroutine_key)
            subroutine_key = re.sub(r"_\d+.log$", "", subroutine_key)
            subroutine_key = re.sub(r".log$", "", subroutine_key)

            match = re.search(r"_(\d+)k", subroutine_key)

            if match:
                # Save the digits into a separate variable
                digits = int(match.group(1))

                # Modify the subroutine_key to remove the digits but keep '_k'
                subroutine_key = re.sub(r"_\d+k", "_k", subroutine_key)
            else:
                # Set digits to None if no match is found
                digits = 0

            # Check if subroutine exists and call it
            if subroutine_key in subroutine_config:
                header = subroutine_config[subroutine_key]['VALUES']['IMPORT'][0][1]
                func_name = subroutine_config[subroutine_key]['SUB']

                # Dynamically call the function using globals()
                func = globals().get(func_name)
                if func:
                    func(header, extracted_file_path, customer, server, subroutine_key, file_name, digits,s3,db)
                else:
                    log.error(f"Function {func_name} not found.")
            else:
                log.error(f"No subroutine found for {subroutine_key}")
        else:
            log.error(f"Errors for {file_name} no pattern found")

    except Exception as e:
        log.error(f"Failed to process S3 file {s3_key}: {e}")
