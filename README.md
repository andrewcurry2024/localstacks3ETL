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
