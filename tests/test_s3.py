import os
import uuid
import logging
import pytest
from botocore.exceptions import ClientError
import boto3
from unittest.mock import patch, MagicMock
import time

logging.basicConfig(level=logging.DEBUG)

# Set AWS environment variables for LocalStack
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"

# Create clients for LocalStack services
s3 = boto3.client("s3", endpoint_url="http://localhost.localstack.cloud:4566")
ssm = boto3.client("ssm", endpoint_url="http://localhost.localstack.cloud:4566")
awslambda = boto3.client("lambda", endpoint_url="http://localhost.localstack.cloud:4566")


@pytest.fixture(scope="module")
def raw_and_processed_buckets():
    """
    This fixture will set up and provide the S3 raw and processed buckets.
    """
    # Extract bucket names from SSM parameters
    raw_bucket = ssm.get_parameter(Name="/localstack-s3etl-app/buckets/raw")["Parameter"]["Value"]
    processed_bucket = ssm.get_parameter(Name="/localstack-s3etl-app/buckets/processed/")["Parameter"]["Value"]
    
    return raw_bucket, processed_bucket


@pytest.fixture
def file_to_upload():
    """
    Fixture that provides a test file to upload.
    """
    file_path = os.path.join(os.path.dirname(__file__), "test_files/test_customer.plc_1728569682-110000-133000.tar")
    return file_path


@pytest.fixture
def unique_key(file_to_upload):
    """
    Fixture that provides a unique key for each test run.
    """
    return f"{uuid.uuid4()}-{os.path.basename(file_to_upload)}"


@pytest.fixture(autouse=True)
def wait_for_lambdas():
    """
    This fixture ensures that Lambda functions are active before the tests run.
    """
    awslambda.get_waiter("function_active").wait(FunctionName="presign")
    awslambda.get_waiter("function_active").wait(FunctionName="transform")
    awslambda.get_waiter("function_active").wait(FunctionName="list")


def wait_for_file_in_s3(bucket, prefix, retries=60, wait_time=5):
    """
    Helper function to wait for a file to appear in S3.
    It retries the check for a given number of times, with a specified delay between each attempt.
    """
    for attempt in range(retries):
        objects = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        if 'Contents' in objects and objects['Contents']:
            logging.debug(f"Found files with prefix {prefix}")
            return objects['Contents']
        else:
            logging.debug(f"No files found with prefix {prefix}, attempt {attempt + 1}/{retries}")
            time.sleep(wait_time)
    
    raise AssertionError(f"No files found with prefix {prefix} after {retries} attempts")


def test_s3_integration_transform(raw_and_processed_buckets, file_to_upload, unique_key):
    """
    This test simulates the integration of S3 processing:
    checking that files are uploaded, processed, and deleted correctly.
    """
    raw_bucket, processed_bucket = raw_and_processed_buckets
    
    # Upload the test file to the raw bucket
    logging.debug(f"Uploading file {file_to_upload} to {raw_bucket} with key {unique_key}")
    try:
        s3.upload_file(file_to_upload, Bucket=raw_bucket, Key=unique_key)
    except ClientError as e:
        logging.error(f"Upload failed: {e}")
        raise

    # List of expected files in the processed bucket, without UUID
    expected_files = [
        "test_customer.plc_buffer_fast",
        "test_customer.plc_db_check_info",
        "test_customer.plc_lru_overall",
        "test_customer.plc_onstat-u",
        "test_customer.plc_openbet_cpu_by_app",
        "test_customer.plc_osmon_sum",
        "test_customer.plc_queues_summary",
        "test_customer.plc_replication",
        "test_customer.plc_total_locks",
        "test_customer.plc_vpcache"
    ]
    
    # Wait for each processed file to appear in the target bucket
    for base_filename in expected_files:
        try:
            # Match all processed files based on a pattern, using the prefix (filename without UUID)
            structured_path_prefix = f"to_ingest/{base_filename}"
            logging.debug(f"Waiting for files with prefix {structured_path_prefix} in processed bucket")
            files = wait_for_file_in_s3(processed_bucket, structured_path_prefix)

            # Validate the expected files exist, even with different UUIDs
            for obj in files:
                key = obj['Key']
                logging.debug(f"Found file {key}")
                assert base_filename in key, f"File {key} doesn't match expected pattern"

        except ClientError as e:
            logging.error(f"Error checking files for {base_filename}: {e}")
            assert False, f"File(s) with prefix {base_filename} do not exist in {processed_bucket}"

    # Clean up uploaded file from raw bucket
    try:
        s3.delete_object(Bucket=raw_bucket, Key=unique_key)
        logging.debug(f"Deleted {unique_key} from raw bucket")
    except ClientError as e:
        logging.error(f"Error deleting file {unique_key} from raw bucket: {e}")

    # Clean up processed files from the processed bucket
    for base_filename in expected_files:
        try:
            # Clean up the processed files by matching base name and UUID
            objects = s3.list_objects_v2(Bucket=processed_bucket, Prefix=f"to_ingest/{base_filename}")
            for obj in objects.get('Contents', []):
                s3.delete_object(Bucket=processed_bucket, Key=obj['Key'])
                logging.debug(f"Deleted {obj['Key']} from processed bucket")
        except ClientError as e:
            logging.error(f"Error deleting {base_filename} from processed bucket: {e}")
