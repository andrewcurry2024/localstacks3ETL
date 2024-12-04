import boto3
import json

# Initialize S3 client
endpoint_url = "https://localhost.localstack.cloud:4566"  # LocalStack URL
s3 = boto3.client("s3", endpoint_url=endpoint_url)

def get_processed_bucket_name() -> str:
    return "localstack-s3etl-app-processed"

def get_raw_bucket_name() -> str:
    return "localstack-s3etl-app-raw"

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

def get_secret(secret_name):
    """Retrieve and parse the secret from Secrets Manager."""
    client = boto3.client("secretsmanager", endpoint_url=endpoint_url)
    
    try:
        # Retrieve the secret value
        response = client.get_secret_value(SecretId=secret_name)
        
        # Parse the secret string
        if 'SecretString' in response:
            secrets = json.loads(response['SecretString'])
            return secrets
        else:
            raise ValueError("SecretString is missing in the response.")
    
    except client.exceptions.ResourceNotFoundException:
        print(f"Secret {secret_name} not found.")
    except client.exceptions.InvalidRequestException as e:
        print(f"Invalid request: {e}")
    except client.exceptions.InvalidParameterException as e:
        print(f"Invalid parameter: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

    return None
