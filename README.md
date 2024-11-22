# Project Setup and Management

This guide outlines the setup and management of the LocalStack-based environment and Lambda functions, including key make commands.

## Prerequisites
- Install `LocalStack` for local AWS service emulation.
- Install necessary dependencies using the `install` command provided below.
- Ensure you have AWS credentials set to `test` for local usage.

## Makefile Commands

### Environment Variables
- **`AWS_ACCESS_KEY_ID`**: Default set to `test` for local use.
- **`AWS_SECRET_ACCESS_KEY`**: Default set to `test` for local use.
- **`ACTIVATE_PRO`**: Controls activation of LocalStack Pro (default is `0`).

### Commands

| Command           | Description |
|-------------------|-------------|
| `make usage`      | Show the list of commands and descriptions |
| `make install`    | Install dependencies for development |
| `make build`      | Build all Lambda functions in the `lambdas` folder |
| `make awslocal-setup` | Deploy the application locally using `awslocal` (AWS CLI wrapper) |
| `make start`      | Start LocalStack Pro in detached mode |
| `make stop`       | Stop LocalStack Pro |
| `make clean`      | Clean up environment (stop containers, remove images, and Lambda zips) |
| `make full`       | Perform a full setup, starting LocalStack and deploying the application |
| `make repost`     | Sync website content to S3 bucket and configure static site hosting |

---

## Makefile Code

Here's the complete `Makefile` with inline comments for reference:

```makefile
# Define AWS credentials for local use
export AWS_ACCESS_KEY_ID ?= test
export AWS_SECRET_ACCESS_KEY ?= test
exit ACTIVATE_PRO=0
SHELL := /bin/bash

# Load environment variables from `.env` file
include .env

# List available commands with descriptions
usage:              ## Show this help
		@grep -F -h "##" $(MAKEFILE_LIST) | grep -F -v grep -F | sed -e 's/\\$$//' -e 's/##//'

# Install necessary Python dependencies
install:            ## Install dependencies
		@pip install -r requirements-dev.txt

# Build Lambda functions from the `lambdas` directory
build:              ## Build lambdas in the lambdas folder
		bin/build_lambdas.sh;

# Set up application locally using `awslocal`
awslocal-setup:     ## Deploy the application locally using `awslocal`, a wrapper for the AWS CLI
		$(MAKE) build
		deployment/awslocal/deploy.sh

# Start LocalStack Pro container in detached mode
start:              ## Start the LocalStack Pro container in detached mode
		@LOCALSTACK_AUTH_TOKEN=$(LOCALSTACK_AUTH_TOKEN) localstack start -d

# Stop the LocalStack Pro container
stop:               ## Stop the LocalStack Pro container
		localstack stop

# Clean up all containers, images, and Lambda zip files
clean:              ## Clean up environment
		localstack stop
		docker image prune -a --force
		rm lambdas/*/lambda.zip

# Perform a full setup, including start, install, and local deployment
full:               ## Run a full setup, starting LocalStack and deploying the application
		make start install awslocal-setup

# Re-sync website files with S3 bucket and enable static hosting
repost:             ## Re-sync website content to S3
		awslocal s3 sync --delete ./website s3://webapp
		awslocal s3 website s3://webapp --index-document index.html

# Declare phony targets (i.e., not tied to specific files)
.PHONY: usage install build awslocal-setup start stop full clean repost
```

# LocalStack S3 ETL Application

This project simulates AWS services locally using **LocalStack** to build an **S3 ETL (Extract, Transform, Load)** pipeline. The application interacts with S3 buckets, Lambda functions, SNS topics, and SSM parameters to perform ETL tasks on uploaded files. The pipeline involves uploading files to a raw S3 bucket, transforming them with Lambda, and saving the results to another processed S3 bucket.

## Project Overview

The application is designed to:
- Upload files to the raw S3 bucket (`localstack-s3etl-app-raw`).
- Use Lambda functions to process and transform the files.
- Store processed files in the processed S3 bucket (`localstack-s3etl-app-processed`).
- Send notifications for failed processing events using SNS.

## Prerequisites

Before starting, ensure you have the following tools installed:

- [Docker](https://www.docker.com/)
- [AWS CLI](https://aws.amazon.com/cli/)
- [LocalStack](https://github.com/localstack/localstack)
- [jq](https://stedolan.github.io/jq/)

## Project Structure

```plaintext
.
├── Makefile
├── README.md
├── bin
│   └── build_lambdas.sh
├── buildspec.yml
├── deployment
│   ├── awslocal
│   │   └── deploy.sh
│   └── grafana
│       └── dashboard.json
├── exported_datasources
│   ├── export.sh
│   ├── influxdb_datasource.json
│   └── try_export.sh
├── htmlcov
│   ├── class_index.html
│   ├── coverage_html_cb_6fb7b396.js
│   ├── favicon_32_cb_58284776.png
│   ├── function_index.html
│   ├── index.html
│   ├── keybd_closed_cb_ce680311.png
│   ├── status.json
│   ├── style_cb_8e611ae1.css
│   ├── z_a44f0ac069e85531_test_list_py.html
│   ├── z_a44f0ac069e85531_test_s3_py.html
│   └── z_a44f0ac069e85531_test_subroutines_py.html
├── lambdas
│   ├── list
│   │   ├── handler.py
│   │   └── lambda.zip
│   ├── presign
│   │   ├── handler.py
│   │   └── lambda.zip
│   └── transform
│       ├── handler.py
│       ├── lambda.zip
│       ├── requirements.txt
│       └── subroutines_config.json
├── out
├── pre_lambda
│   ├── latest.py
│   ├── move_and_clean.py
│   ├── subroutines_config.json
│   └── test.py
├── pytest.ini
├── requirements-dev.txt
├── tests
│   ├── test_files
.......
│   ├── test_s3.py
│   └── test_subroutines.py
└── website
    ├── app.js
    ├── favicon.ico
    └── index.html
```



## Application Overview

This application is designed to simulate a serverless data pipeline using **LocalStack** to locally emulate AWS services. It interacts with **AWS Lambda**, **S3**, and **SNS** for file processing, transformations, and notifications.

### Key Features:
- **Upload Files**: Files are uploaded to the raw S3 bucket (`localstack-s3etl-app-raw`) using pre-signed URLs generated by the **presign Lambda** function.
- **Lambda Functions**: The application uses several Lambda functions:
  - **Presign**: Generates pre-signed URLs to allow users to upload files to S3.
  - **List**: Lists the files in the raw S3 bucket (`localstack-s3etl-app-raw`).
  - **Transform**: Processes the files uploaded to the raw S3 bucket and stores the processed output in the processed S3 bucket (`localstack-s3etl-app-processed`).
- **File Processing**: Files uploaded to the raw bucket are automatically processed by the **transform Lambda** function.
- **SNS Notifications**: If a file processing fails, an SNS topic (`failed-process-topic`) sends a failure notification, which can be subscribed to via email.
- **InfluxDB**: Processed Files are now inserted into influxdb 
- **Grafana**: Grafana dashboard and environment created to view the metrics.
### Deployment Process:
1. **Create S3 Buckets**: Two S3 buckets are created:
   - `localstack-s3etl-app-raw`: Used for storing raw files.
   - `localstack-s3etl-app-processed`: Used for storing processed files.

2. **Create and Configure Lambda Functions**:
   - **Presign Lambda**: Generates pre-signed URLs for file uploads.
   - **List Lambda**: Lists objects in the raw S3 bucket.
   - **Transform Lambda**: Processes files from the raw bucket and stores the results in the processed bucket.
   
3. **Set Up SNS for Failure Notifications**: If file processing fails, a notification is sent to a configured email via the SNS topic `failed-process-topic`.

4. **Configure S3 Event Notifications**: The **transform Lambda** is triggered automatically when a new file is uploaded to the raw bucket via S3 event notifications.

5. **Deploy Website**: A static website is served from the `webapp` S3 bucket, providing a frontend for interacting with the application.
```

### Example Deployment Script:

```bash
#!/bin/bash

export AWS_DEFAULT_REGION=us-east-1

awslocal s3 mb s3://localstack-s3etl-app-raw
awslocal s3 mb s3://localstack-s3etl-app-processed

awslocal ssm put-parameter --name /localstack-s3etl-app/buckets/raw --type "String" --value "localstack-s3etl-app-raw"
awslocal ssm put-parameter --name /localstack-s3etl-app/buckets/processed --type "String" --value "localstack-s3etl-app-processed"

awslocal sns create-topic --name failed-process-topic
awslocal sns subscribe \
    --topic-arn arn:aws:sns:us-east-1:000000000000:failed-process-topic \
    --protocol email \
    --notification-endpoint my-email@example.com

awslocal lambda create-function \
    --function-name presign \
    --runtime python3.11 \
    --timeout 10 \
    --zip-file fileb://lambdas/presign/lambda.zip \
    --handler handler.handler \
    --role arn:aws:iam::000000000000:role/lambda-role \
    --environment Variables="{STAGE=local}"

awslocal lambda wait function-active-v2 --function-name presign

awslocal lambda create-function-url-config \
    --function-name presign \
    --auth-type NONE

awslocal lambda create-function \
    --function-name list \
    --runtime python3.11 \
    --timeout 10 \
    --zip-file fileb://lambdas/list/lambda.zip \
    --handler handler.handler \
    --role arn:aws:iam::000000000000:role/lambda-role \
    --environment Variables="{STAGE=local}"

awslocal lambda wait function-active-v2 --function-name list

awslocal lambda create-function-url-config \
    --function-name list \
    --auth-type NONE


awslocal lambda create-function \
    --function-name transform \
    --runtime python3.11 \
    --timeout 120 \
    --zip-file fileb://lambdas/transform/lambda.zip \
    --handler handler.handler \
    --dead-letter-config TargetArn=arn:aws:sns:us-east-1:000000000000:failed-process-topic \
    --role arn:aws:iam::000000000000:role/lambda-role \
    --environment Variables="{STAGE=local}"

awslocal lambda wait function-active-v2 --function-name transform
awslocal lambda put-function-event-invoke-config --function-name transform --maximum-event-age-in-seconds 3600 --maximum-retry-attempts 0

fn_transform_arn=$(awslocal lambda get-function --function-name transform --output json | jq -r .Configuration.FunctionArn)
#awslocal s3api put-bucket-notification-configuration \
#    --bucket localstack-s3etl-app-raw \
#    --notification-configuration "{\"LambdaFunctionConfigurations\": [{\"LambdaFunctionArn\": \"$fn_transform_arn\", \"Events\": [\"s3:ObjectCreated:*\"]}]}"

awslocal s3api put-bucket-notification-configuration \
    --bucket localstack-s3etl-app-raw \
    --notification-configuration '{
        "LambdaFunctionConfigurations": [{
            "LambdaFunctionArn": "'"$fn_transform_arn"'",
            "Events": ["s3:ObjectCreated:*"],
            "Filter": {
                "Key": {
                    "FilterRules": [
                        {
                            "Name": "suffix",
                            "Value": ".tar"
                        }
                    ]
                }
            }
        }]
    }'
awslocal s3 mb s3://webapp
awslocal s3 sync --delete ./website s3://webapp
awslocal s3 website s3://webapp --index-document index.html

```

## Functionality in Brief
-	Upload files via the frontend, which will generate pre-signed URLs.
-	S3 trigger on the bucket and file type will trigger a transform lambda
-	Files will be cleaned/transformed and inserted into influxdb
-	Grafana will display the metrics in a preconfigured dashboard
-	In case of a failure, an email notification will be sent via SNS.
-	HTML/HQuery interface can be used to upload the files and monitor the processing

