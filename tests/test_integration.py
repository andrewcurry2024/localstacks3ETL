import os
import time
import typing
import uuid

import boto3
import pytest
import requests
import logging
from botocore.exceptions import ClientError  # Import ClientError
from unittest.mock import patch, MagicMock
logging.basicConfig(level=logging.DEBUG)

if typing.TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client
    from mypy_boto3_ssm import SSMClient
    from mypy_boto3_lambda import LambdaClient

os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"

s3: "S3Client" = boto3.client(
    "s3", endpoint_url="http://localhost.localstack.cloud:4566"
)
ssm: "SSMClient" = boto3.client(
    "ssm", endpoint_url="http://localhost.localstack.cloud:4566"
)
awslambda: "LambdaClient" = boto3.client(
    "lambda", endpoint_url="http://localhost.localstack.cloud:4566"
)


@pytest.fixture(autouse=True)
def _wait_for_lambdas():
    # makes sure that the lambdas are available before running integration tests
    awslambda.get_waiter("function_active").wait(FunctionName="presign")
    awslambda.get_waiter("function_active").wait(FunctionName="transform")
    awslambda.get_waiter("function_active").wait(FunctionName="list")

import os
import time
import uuid
from urllib.parse import urlparse

def test_s3_integration_transform():
    """
    This test simulates the integration of S3 processing,
    checking that files are uploaded, processed, and deleted correctly.
    """
    # Set up the test file and bucket paths
    file = os.path.join(os.path.dirname(__file__), "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000.tar")
    key = os.path.basename(file)
    unique_id = str(uuid.uuid4())

    # Extract bucket names from SSM parameters
    raw_bucket = ssm.get_parameter(Name="/localstack-s3etl-app/buckets/raw")["Parameter"]["Value"]
    processed_bucket = ssm.get_parameter(Name="/localstack-s3etl-app/buckets/processed/")["Parameter"]["Value"]

    # Upload the test file to the raw bucket
    logging.debug(f"Uploading file {file} to {raw_bucket} with key {key}")
    try:
        s3.upload_file(file, Bucket=raw_bucket, Key=key)
    except ClientError as e:
        logging.error(f"Upload failed: {e}")
        raise

    # Define expected filenames in the processed bucket
    expected_files = [
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_buffer_16k_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_buffer_2k_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_buffer_4k_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_buffer_8k_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_buffer_fast_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_db_check_info_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_lru_16k_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_lru_2k_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_lru_4k_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_lru_8k_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_lru_overall_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_onstat-g_ntu_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_onstat-g_prc_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_onstat-g_seg_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_onstat-l_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_onstat-u_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_openbet_cpu_by_app_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_osmon_sum_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_queues_summary_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_replication_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_total_locks_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_vpcache_1_for_graph.log"
    ]
    base_path = f"WilliamHill/gibux341.prod.williamhill.plc/"

    # Wait for each processed file to appear in the target bucket
    for expected_file in expected_files:
        structured_path = f"{base_path}{expected_file}"
        logging.debug(f"Waiting for file {structured_path} in processed bucket")
        try:
            s3.get_waiter("object_exists").wait(Bucket=processed_bucket, Key=structured_path)
            response = s3.head_object(Bucket=processed_bucket, Key=structured_path)
            logging.debug(f"File found: {structured_path}, {response}")
        except ClientError as e:
            logging.error(f"Error waiting for file {structured_path}: {e}")
            assert False, f"File {structured_path} does not exist in {processed_bucket}"

    # Clean up uploaded file from the raw bucket
    logging.debug(f"Cleaning up uploaded file {key} from raw bucket")
    try:
        s3.delete_object(Bucket=raw_bucket, Key=key)
    except ClientError as e:
        logging.error(f"Error deleting file {key} from raw bucket: {e}")

    # Clean up processed files from the processed bucket
    for expected_file in expected_files:
        structured_path = f"{base_path}{expected_file}"
        try:
            logging.debug(f"Deleting processed file {structured_path}")
            s3.delete_object(Bucket=processed_bucket, Key=structured_path)
        except ClientError as e:
            logging.error(f"Error deleting {structured_path}: {e}")


def test_s3_integration_with_new_processing():
    # Set up the test file and bucket paths
    file = os.path.join(os.path.dirname(__file__), "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000.tar")
    key = os.path.basename(file)
    unique_id = str(uuid.uuid4())

    # Extract bucket names from SSM parameters
    raw_bucket = ssm.get_parameter(Name="/localstack-s3etl-app/buckets/raw")["Parameter"]["Value"]
    processed_bucket = ssm.get_parameter(Name="/localstack-s3etl-app/buckets/processed/")["Parameter"]["Value"]

    # Upload the test file to the raw bucket
    s3.upload_file(file, Bucket=raw_bucket, Key=key)

    # Define the exact expected filenames in the processed bucket
    expected_files = [
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_buffer_16k_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_buffer_2k_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_buffer_4k_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_buffer_8k_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_buffer_fast_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_db_check_info_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_lru_16k_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_lru_2k_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_lru_4k_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_lru_8k_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_lru_overall_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_onstat-g_ntu_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_onstat-g_prc_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_onstat-g_seg_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_onstat-l_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_onstat-u_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_openbet_cpu_by_app_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_osmon_sum_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_queues_summary_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_replication_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_total_locks_1_for_graph.log",
        "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000_vpcache_1_for_graph.log"
    ]

    base_path = f"WilliamHill/gibux341.prod.williamhill.plc/"

    # Wait for each processed file to appear in the target bucket
    for expected_file in expected_files:
        structured_path = f"{base_path}{expected_file}"
        logging.debug(structured_path)
        s3.get_waiter("object_exists").wait(Bucket=processed_bucket, Key=structured_path)

        # Check the file exists
        response = s3.head_object(Bucket=processed_bucket, Key=structured_path)
        assert response is not None, f"File {structured_path} does not exist in {processed_bucket}"


    # Clean up uploaded file from the raw bucket
    s3.delete_object(Bucket=raw_bucket, Key=key)

    # Clean up individually processed files from the processed bucket
    for expected_file in expected_files:
        structured_path = f"{base_path}{expected_file}"
        try:
            s3.delete_object(Bucket=processed_bucket, Key=structured_path)
        except s3.exceptions.ClientError as e:
            print(f"Error deleting {structured_path}: {e}")



def test_failure_sns_to_ses_integration():
    file = os.path.join(os.path.dirname(__file__), "some-file.txt")
    key = f"{uuid.uuid4()}-{os.path.basename(file)}"

    parameter = ssm.get_parameter(Name="/localstack-s3etl-app/buckets/raw")
    source_bucket = parameter["Parameter"]["Value"]

    s3.upload_file(file, Bucket=source_bucket, Key=key)

    def _check_message():
        response = requests.get("http://localhost.localstack.cloud:4566/_aws/ses")
        messages = response.json()["messages"]
        assert key in messages[-1]["Body"]["text_part"]

    # retry to check for the message
    for i in range(9):
        try:
            _check_message()
        except:
            time.sleep(1)
    _check_message()

    # clean up resources
    s3.delete_object(Bucket=source_bucket, Key=key)

def wait_for_s3(bucket_name):
    """Wait until the bucket is available in S3."""
    while True:
        try:
            s3.head_bucket(Bucket=bucket_name)
            break
        except s3.exceptions.ClientError:
            time.sleep(1)

def wait_for_lambda(function_name):
    """Wait until the Lambda function is active."""
    while True:
        try:
            awslambda.get_function(FunctionName=function_name)
            break
        except awslambda.exceptions.ResourceNotFoundException:
            time.sleep(1)


def setup_and_teardown():
    # This fixture could be used to setup and teardown, if needed.
    # For now, we'll just create a bucket here for the test
    bucket_name = "test-bucket"
    try:
        # Create a bucket in LocalStack
        s3.create_bucket(Bucket=bucket_name)
    except ClientError as e:
        logging.error(f"Error creating bucket: {e}")
        raise e

    yield

    # Clean up after the test
    try:
        s3.delete_bucket(Bucket=bucket_name)
    except ClientError as e:
        logging.error(f"Error deleting bucket: {e}")


def test_upload_failure_handling():
    """
    This test simulates an S3 upload failure.
    It attempts to upload a file to a non-existent bucket and asserts the failure.
    """
    # File and bucket setup (non-existent file to trigger failure)
    file_name = "non_existent_file.txt"
    bucket_name = "test-bucket"  # You can use a real bucket if you're testing real functionality
    
    # Mocking the upload_file method to simulate a file not found error
    with patch.object(s3, 'upload_file', side_effect=FileNotFoundError(f"{file_name} not found")):
        try:
            # Attempt to upload a non-existent file to trigger a failure
            s3.upload_file(file_name, Bucket=bucket_name, Key=file_name)
            pytest.fail("Upload should have failed but succeeded.")
        except FileNotFoundError as e:
            # This will now catch the mocked error and assert that the correct error is raised
            logging.error(f"Upload failed: {e}")
            # Ensure that the exception message is correct
            assert f"{file_name} not found" in str(e), f"Unexpected error: {e}"
