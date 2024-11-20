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

def get_processed_bucket_name() -> str:
    return "localstack-s3etl-app-processed"

def get_raw_bucket_name() -> str:
    return "localstack-s3etl-app-raw"

class Logger:
    def error(self, message):
        print(f"ERROR: {message}")
    def debug(self, message):
        print(f"INFO: {message}")

log = Logger()

class Database:
    def __init__(self):
        self.token = "my-super-secret-auth-token"
        self.org = "myorg"
        self.bucket = "mydb"
        self.url = "http://influxdb:8086"

    def write(self, data, file):
        """Write data to InfluxDB using batching with context management"""
        try:
            # Open the client and write_api in a 'with' statement to ensure proper management
            with InfluxDBClient(url=self.url, token=self.token) as client:
                # Set write options: batch size, flush interval, jitter, etc.
                write_options = WriteOptions(batch_size=1000, flush_interval=100, jitter_interval=100)

                # Use write_api within the context
                with client.write_api(write_options=write_options) as write_api:
                    # Loop through each record and write it to InfluxDB
                    for record in data:
                        # Prepare the record for writing
                        if 'datetime' in record:
                            record['_time'] = record.pop('datetime')
                            if isinstance(record['_time'], str):
                                record['_time'] = datetime.strptime(record['_time'], '%Y-%m-%dT%H:%M:%S')
                            record['_time'] = record['_time'].replace(tzinfo=None)
                            record['_time'] = record['_time'].strftime('%Y-%m-%dT%H:%M:%SZ')

                        point = Point(record['_measurement'])

                        # Add tags and fields dynamically
                        if "customer" in record:
                            point.tag("customer", record["customer"])
                        if "server" in record:
                            point.tag("server", record["server"])
                        if "digits" in record:
                            point.tag("pagesize", record["digits"])
                        if "name" in record:
                            point.tag("metric", record["name"])
                        if "area" in record:
                            point.tag("metric", record["area"])

                        for field, value in record.items():
                            if field not in ['_measurement', 'customer', 'server', '_time']:
                                point.field(field, value)

                        point.time(record['_time'], WritePrecision.S)

                        # Write the point to InfluxDB asynchronously (handled by batching)
                        #print(f"Writing record for {file}")
                        write_api.write(bucket=self.bucket, org=self.org, record=point)

                    # Flush data to ensure all points are written before closing
                    write_api.flush()

            print(f"All data for {file} successfully written to InfluxDB")
        except Exception as e:
            print(f"An unexpected error occurred while writing data for {file}: {e}")

# Execution setup
db = Database()

def move_s3_object(source_bucket: str, destination_bucket: str, object_key: str, destination_key: str = None):
    """
    Moves an object from one S3 bucket to another by copying it to the destination and deleting it from the source.
    
    Args:
        source_bucket (str): The name of the source S3 bucket.
        destination_bucket (str): The name of the destination S3 bucket.
        object_key (str): The key (path) of the object in the source bucket.
        destination_key (str, optional): The key (path) for the object in the destination bucket.
                                         If not provided, will use the same key as in the source.
    """
    if destination_key is None:
        destination_key = object_key

    try:
        # Copy the object to the destination bucket
        s3.copy_object(
            CopySource={'Bucket': source_bucket, 'Key': object_key},
            Bucket=destination_bucket,
            Key=destination_key
        )
        print(f"Copied {object_key} to s3://{destination_bucket}/{destination_key}")

        # Delete the object from the source bucket
        s3.delete_object(Bucket=source_bucket, Key=object_key)
        print(f"Deleted {object_key} from s3://{source_bucket}/{object_key}")
        
        print(f"Successfully moved {object_key} from {source_bucket} to {destination_bucket}")

    except Exception as e:
        print(f"Error moving {object_key} from {source_bucket} to {destination_bucket}: {e}")


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

            produce_import_files(subroutine_config, get_raw_bucket_name(), extracted_file_path, file_name, log)
            
            move_s3_object(get_raw_bucket_name(), get_processed_bucket_name(), s3_key)

            print(f"Successfully uploaded {file_name} to s3://{get_raw_bucket_name()}/{s3_key}")

def clean_data(df: pd.DataFrame, header: str, customer: str, server: str, sub_key: str, digits) -> pd.DataFrame:
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
    df.loc[:, 'digits'] = digits

    print(f"Cleaned Data Overview for {customer}-{server}:")
    print(df.info())
    return df

def import_data(header, filename, customer, server, subroutine_key, file, digits):
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
        db.write(records,s3_key)  # Send to InfluxD
        move_s3_object(get_raw_bucket_name(), get_processed_bucket_name(), s3_key)
        print(f"Hopefully uploaded {filename_new} to s3://{get_processed_bucket_name()}/{s3_key}")

    except Exception as e:
        print(f"ERROR: Failed to process {filename}: {e}")

def import_partitions(header, filename, customer, server, subroutine_key, file, digits):
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
        db.write(records,s3_key)  # Send to InfluxD
        move_s3_object(get_raw_bucket_name(), get_processed_bucket_name(), s3_key)
        print(f"Hopefully uploaded {filename_new} to s3://{get_processed_bucket_name()}/{s3_key}")

    except Exception as e:
        print(f"ERROR: Failed to process {filename}: {e}")

def cpu_by_app(header, filename, customer, server, subroutine_key, file, digits):
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
        db.write(records,s3_key)  # Send to InfluxD
        move_s3_object(get_raw_bucket_name(), get_processed_bucket_name(), s3_key)
        print(f"Hopefully uploaded {filename_new} to s3://{get_processed_bucket_name()}/{s3_key}")

    except Exception as e:
        print(f"ERROR: Failed to process {filename}: {e}")

def import_data_onstat_l(header, filename, customer, server, subroutine_key, file, digits):
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
        db.write(records,s3_key)  # Send to InfluxD
        move_s3_object(get_raw_bucket_name(), get_processed_bucket_name(), s3_key)
        print(f"Hopefully uploaded {filename_new} to s3://{get_processed_bucket_name()}/{s3_key}")

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
                    func(header, extracted_file_path, customer, server, subroutine_key, file_name, digits)
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
