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

echo
echo "Fetching function URL for 'presign' Lambda..."
awslocal lambda list-function-url-configs --function-name presign --output json | jq -r '.FunctionUrlConfigs[0].FunctionUrl'
echo "Fetching function URL for 'list' Lambda..."
awslocal lambda list-function-url-configs --function-name list --output json | jq -r '.FunctionUrlConfigs[0].FunctionUrl'

echo "Now open the Web app under https://webapp.s3-website.localhost.localstack.cloud:4566/"
echo "and paste the function URLs above (make sure to use https:// as protocol)"
