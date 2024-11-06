import os
import uuid
import boto3
from urllib.parse import unquote_plus

# Initialize S3 client
endpoint_url = "https://localhost.localstack.cloud:4566"  # LocalStack URL
s3 = boto3.client("s3", endpoint_url=endpoint_url)

def get_bucket_name() -> str:
    # Simulate getting the bucket name for processed files
    return "localstack-s3etl-app-processed"

def extract_and_create_structure(tar_file_path: str, extracted_dir_path: str, file_key_prefix: str) -> None:
    """
    Extract files from tar and upload them to S3 with proper structure.
    """
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
            s3_key = f"{file_key_prefix}/{file_name}"
            print(f"Uploading {file_name} to s3://{get_bucket_name()}/{s3_key}")

            # Extract the file
            tar.extract(file_name, path=extracted_dir_path)

            # Upload to S3
            s3.upload_file(extracted_file_path, get_bucket_name(), s3_key)

            print(f"Successfully uploaded {file_name} to s3://{get_bucket_name()}/{s3_key}")

def handler(event, context):
    for record in event["Records"]:
        # Get the bucket and file key from event
        source_bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])

        # Download the tar file
        tmp_file_path = f"/tmp/{uuid.uuid4()}.tar"
        s3.download_file(source_bucket, key, tmp_file_path)

        # Extract and upload to processed bucket with the correct structure
        extracted_dir_path = f"/tmp/extracted/{uuid.uuid4()}"
        
        # Extract the file prefix (before the epoch) to form the correct directory structure
        file_key_prefix = key.split('_')[0]  # This will give 'WilliamHill/gibux341.prod.williamhill.plc'
        
        # Call the function to extract the tar and upload with the correct structure
        extract_and_create_structure(tmp_file_path, extracted_dir_path, file_key_prefix)
