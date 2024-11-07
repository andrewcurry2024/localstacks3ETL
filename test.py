import os
import typing
import boto3
import datetime
import datetime
from zoneinfo import ZoneInfo

if typing.TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client
    from mypy_boto3_ssm import SSMClient

os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"

if os.getenv("STAGE") == "local":
    endpoint_url = "https://localhost.localstack.cloud:4566"

s3: "S3Client" = boto3.client(
    "s3", endpoint_url="http://localhost.localstack.cloud:4566"
)
ssm: "SSMClient" = boto3.client(
    "ssm", endpoint_url="http://localhost.localstack.cloud:4566"
)


def get_bucket_name_files() -> str:
    parameter = ssm.get_parameter(Name="/localstack-s3etl-app/buckets/raw")
    return parameter["Parameter"]["Value"]


def get_bucket_name_processed() -> str:
    parameter = ssm.get_parameter(Name="/localstack-s3etl-app/buckets/processed")
    return parameter["Parameter"]["Value"]

def list_all_files(bucket_name: str) -> typing.List[dict]:
    """Lists all files in the specified bucket."""
    result = []
    continuation_token = None

    while True:
        list_params = {"Bucket": bucket_name}
        if continuation_token:
            list_params["ContinuationToken"] = continuation_token

        response = s3.list_objects_v2(**list_params)

        if "Contents" in response:
            result.extend(response["Contents"])

        if response.get("IsTruncated"):
            continuation_token = response.get("NextContinuationToken")
        else:
            break

    return result


def handler(event, context):
    # Get raw bucket name
    raw_bucket = get_bucket_name_files()

    # Recursively list all files in the raw bucket
    raw_files = list_all_files(raw_bucket)

    if not raw_files:
        print(f"Bucket {raw_bucket} is empty")
        return []

    result = {}
    # Collect the original files from the raw bucket
    for obj in raw_files:
        result[obj["Key"]] = {
            "Name": obj["Key"],
            "Timestamp": obj["LastModified"].isoformat(),
            "Original": {
                "Size": obj["Size"],
                "URL": s3.generate_presigned_url(
                    ClientMethod="get_object",
                    Params={"Bucket": raw_bucket, "Key": obj["Key"]},
                    ExpiresIn=3600,
                ),
            },
        }

    # Get the processed bucket name
    processed_bucket = get_bucket_name_processed()


# Get UTC time with zoneinfo
    # Get the current time in UTC using ZoneInfo
    now = datetime.datetime.utcnow().replace(tzinfo=ZoneInfo("UTC"))
    ten_minutes_ago = now - datetime.timedelta(minutes=10)

    # Recursively list all files in the processed bucket
    processed_files = list_all_files(processed_bucket)

    for obj in processed_files:
    # Ensure obj["LastModified"] is timezone-aware, using ZoneInfo
        obj_last_modified = obj["LastModified"].replace(tzinfo=ZoneInfo("UTC"))

    # Skip files that are older than 10 minutes
        if obj_last_modified < ten_minutes_ago:
            continue

        # Skip files that are older than 10 minutes
        if obj_last_modified < ten_minutes_ago:
            continue

        # Add the resized file regardless of whether it matches the raw bucket
        if obj["Key"] not in result:
            result[obj["Key"]] = {
                "Name": obj["Key"],
                "Timestamp": obj_last_modified.isoformat(),
                "Resized": {
                    "Size": obj["Size"],
                    "URL": s3.generate_presigned_url(
                        ClientMethod="get_object",
                        Params={"Bucket": processed_bucket, "Key": obj["Key"]},
                        ExpiresIn=3600,
                    ),
                },
            }
        else:
            # If file already exists (from raw bucket), just add the resized info
            result[obj["Key"]]["Resized"] = {
                "Size": obj["Size"],
                "URL": s3.generate_presigned_url(
                    ClientMethod="get_object",
                    Params={"Bucket": processed_bucket, "Key": obj["Key"]},
                    ExpiresIn=3600,
                ),
            }

    # Return the result sorted by timestamp (newest first)
    return list(sorted(result.values(), key=lambda k: k["Timestamp"], reverse=True))


if __name__ == "__main__":
    print(handler(None, None))
