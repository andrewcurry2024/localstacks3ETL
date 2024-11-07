import os
import time
import typing
import uuid

import boto3
import pytest
import requests

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

def test_s3_integration_with_new_processing():
    # Set up test file
    file = os.path.join(os.path.dirname(__file__), "WilliamHill_gibux341.prod.williamhill.plc_1728569682-110000-133000.tar")
    key = os.path.basename(file)
    unique_id = str(uuid.uuid4())

    # Extract bucket names from SSM parameters
    raw_bucket = ssm.get_parameter(Name="/localstack-s3etl-app/buckets/raw")["Parameter"]["Value"]
    processed_bucket = ssm.get_parameter(Name="/localstack-s3etl-app/buckets/processed")["Parameter"]["Value"]

    # Upload the test file to the raw bucket
    s3.upload_file(file, Bucket=raw_bucket, Key=key)

    # Generate expected structured path for processed file
    # Assuming structure is "processed/Category/Identifier/Epoch/File"
    structured_path = f"processed/WilliamHill/gibux341.prod.williamhill.plc/{unique_id}/{key}"

    # Wait for the processed file to appear
    s3.get_waiter("object_exists").wait(Bucket=processed_bucket, Key=structured_path)

    # Validate processed file is present and download it for comparison
    s3.head_object(Bucket=processed_bucket, Key=structured_path)
    resized_file_path = "/tmp/nyan-cat-resized.png"
    s3.download_file(Bucket=processed_bucket, Key=structured_path, Filename=resized_file_path)

    # Assert the processed file size is reduced (indicating resizing or processing)
    assert os.stat(resized_file_path).st_size < os.stat(file).st_size

    # Optional: Validate log entries if logs are captured
    logs = get_lambda_logs()  # Assuming you have a function to capture logs
    assert "Uploading" in logs
    assert "Extracting" in logs

    # Clean up uploaded files from S3
    s3.delete_object(Bucket=raw_bucket, Key=key)
    s3.delete_object(Bucket=processed_bucket, Key=structured_path)

    # Clean up local files
    if os.path.exists(resized_file_path):
        os.remove(resized_file_path)


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
