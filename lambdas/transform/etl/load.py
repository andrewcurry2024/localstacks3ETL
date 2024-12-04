import os
import uuid
from datetime import datetime
import boto3
import re
import pandas as pd
from utils.s3 import move_s3_object,get_processed_bucket_name, get_raw_bucket_name
from etl.clean import clean_data

def import_data(header, filename, customer, server, subroutine_key, file, digits,s3,db):
    try:
        records = []
        df = pd.read_csv(filename, header=0)
        df.columns = df.columns.str.strip()
        df = clean_data(df, header, customer, server, subroutine_key,digits)
        print(f"DataFrame for {filename} with header: {header}")
        print(df)
        uuid_tmp=uuid.uuid4()
        # Create a dynamic filename
        filename_new = f"{customer}_{server}_{subroutine_key}_{uuid_tmp}.csv"
        filename_s3 = f"{customer}_{server}_{subroutine_key}_{uuid_tmp}_{digits}.csv"
        tmp_file_path = os.path.join('/tmp', filename_new)
        df.to_csv(tmp_file_path, index=False)
        s3_key = f"to_ingest/{filename_s3}"
        s3.upload_file(tmp_file_path, get_raw_bucket_name(), s3_key)
        print(f"My S3 {s3_key}")
        print(f"My tmp {filename_new}")
        records = df.to_dict(orient="records")
        db.write(records,s3_key,customer,server)  # Send to InfluxD
        move_s3_object(get_raw_bucket_name(), get_processed_bucket_name(), s3_key)
        print(f"Hopefully uploaded {filename_new} to s3://{get_processed_bucket_name()}/{s3_key}")

    except Exception as e:
        print(f"ERROR: Failed to process {filename}: {e}")

def import_partitions(header, filename, customer, server, subroutine_key, file, digits,s3,db):
    try:
        records = []
        columns = [
            "date","time","partnum", "npages", "nused", "npdata", "nrows", "flgs", "seqsc", "lkrqs", "lkwts",
            "ucnt", "touts", "isrd", "iswrt", "isrwt", "isdel", "dlks", "bfrd", "bfwrt", "nextns", "area"
        ]

        # Load the file with specified columns
        df = pd.read_csv(
            filename,
            header=None,
            names=columns,
            sep=","
        )
        df.columns = df.columns.str.strip()
        print(df)
        df = clean_data(df, header, customer, server, subroutine_key,digits)
        print(f"DataFrame for {filename} with header: {header}")
        uuid_tmp=uuid.uuid4()
        # Create a dynamic filename
        filename_new = f"{customer}_{server}_{subroutine_key}_{uuid_tmp}.csv"
        filename_s3 = f"{customer}_{server}_{subroutine_key}_{uuid_tmp}_{digits}.csv"
        tmp_file_path = os.path.join('/tmp', filename_new)
        df.to_csv(tmp_file_path, index=False)
        s3_key = f"to_ingest/{filename_s3}"
        s3.upload_file(tmp_file_path, get_raw_bucket_name(), s3_key)
        print(f"My S3 {s3_key}")
        print(f"My tmp {filename_new}")
        records = df.to_dict(orient="records")
        db.write(records,s3_key,customer,server)  # Send to InfluxD
        move_s3_object(get_raw_bucket_name(), get_processed_bucket_name(), s3_key)
        print(f"Hopefully uploaded {filename_new} to s3://{get_processed_bucket_name()}/{s3_key}")

    except Exception as e:
        print(f"ERROR: Failed to process {filename}: {e}")

def cpu_by_app(header, filename, customer, server, subroutine_key, file, digits, s3,db):
    try:
        records = []
        df = pd.read_csv(filename, header=0)
        # have to split up the record into seperate rows
        data = []
        for _, row in df.iterrows():
            timestamp = row[0]  # DateTime column
            for i in range(1, len(row), 2):
                metric_name = df.columns[i].replace(" core", "")  # Remove " core" suffix for metric name
                cores = row[i]
                percentage = row[i + 1]

                # Append the structured row
                data.append({
                    "datetime": timestamp,
                    "metric": metric_name,
                    "cores": round(cores, 2),
                    "percentage": round(percentage, 2),
                })

        # Create the structured DataFrame
        df = pd.DataFrame(data)

        df.columns = df.columns.str.strip()
        df = clean_data(df, header, customer, server, 'cpu_by_app',digits)
        print(f"DataFrame for {filename} with header: {header}")
        print(df)
        uuid_tmp=uuid.uuid4()
        # Create a dynamic filename
        filename_new = f"{customer}_{server}_{subroutine_key}_{uuid_tmp}.csv"
        filename_s3 = f"{customer}_{server}_{subroutine_key}_{uuid_tmp}_{digits}.csv"
        tmp_file_path = os.path.join('/tmp', filename_new)
        df.to_csv(tmp_file_path, index=False)
        s3_key = f"to_ingest/{filename_s3}"
        s3.upload_file(tmp_file_path, get_raw_bucket_name(), s3_key)
        print(f"My S3 {s3_key}")
        print(f"My tmp {filename_new}")
        records = df.to_dict(orient="records")
        db.write(records,s3_key,customer,server)  # Send to InfluxD
        move_s3_object(get_raw_bucket_name(), get_processed_bucket_name(), s3_key)
        print(f"Hopefully uploaded {filename_new} to s3://{get_processed_bucket_name()}/{s3_key}")

    except Exception as e:
        print(f"ERROR: Failed to process {filename}: {e}")

def import_data_onstat_l(header, filename, customer, server, subroutine_key, file, digits, s3,db):
    try:
        records = []
        column_names = ['date', 'time', 'epoch', 'pbuffer', 'pbufused', 'pbufsize', 'ppct_io', 'lbuffer', 'lbufused', 'lbufsize', 'physused']

# Load the CSV file with custom headers
        df = pd.read_csv(
            filename,
            names=column_names,  # Use custom column names
            header=0,  # The first row will be skipped (since you are providing column names)
            encoding='utf-8',  # Ensure the encoding is correct
            skip_blank_lines=True,  # Skip blank lines if any
            on_bad_lines='skip',  # Skip any problematic lines
            delimiter=','  # Specify comma as delimiter
        )
        
        df.columns = df.columns.str.strip()
        df = clean_data(df, header, customer, server, subroutine_key, digits)
        print(f"DataFrame for {filename} with header: {header}")
        print(df)
        uuid_tmp=uuid.uuid4()
        # Create a dynamic filename
        filename_new = f"{customer}_{server}_{subroutine_key}_{uuid_tmp}.csv"
        filename_s3 = f"{customer}_{server}_{subroutine_key}_{uuid_tmp}.csv"
        tmp_file_path = os.path.join('/tmp', filename_new)
        df.to_csv(tmp_file_path, index=False)
        s3_key = f"to_ingest/{filename_s3}"
        s3.upload_file(tmp_file_path, get_raw_bucket_name(), s3_key)
        print(f"My S3 {s3_key}")
        print(f"My tmp {filename_new}")
        records = df.to_dict(orient="records")
        db.write(records,s3_key,customer,server)  # Send to InfluxD
        move_s3_object(get_raw_bucket_name(), get_processed_bucket_name(), s3_key)
        print(f"Hopefully uploaded {filename_new} to s3://{get_processed_bucket_name()}/{s3_key}")

    except Exception as e:
        print(f"ERROR: Failed to process {filename}: {e}")
