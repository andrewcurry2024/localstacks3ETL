export AWS_ACCESS_KEY_ID ?= test
export AWS_SECRET_ACCESS_KEY ?= test
export ACTIVATE_PRO=0
SHELL := /bin/bash

include .env

usage:				## Show this help 
		@grep -F -h "##" $(MAKEFILE_LIST) | grep -F -v grep -F | sed -e 's/\\$$//' -e 's/##//'

install:			## Install dependencies
		@pip install -r requirements-dev.txt

build: 				## Build lambdas in the lambdas folder
		bin/build_lambdas.sh; 

awslocal-setup: 		## Deploy the application locally using `awslocal`, a wrapper for the AWS CLI
		$(MAKE) build
		deployment/awslocal/deploy.sh

start:				## Start the LocalStack Pro container in the detached mode
		#@LOCALSTACK_AUTH_TOKEN=$(LOCALSTACK_AUTH_TOKEN) localstack start -d
		# Create Docker network if not already exists
		docker network create localstack_network || echo "Network already exists"

		# Start InfluxDB container and connect it to the localstack_network
		docker run -d --network localstack_network --name influxdb \
		  -e DOCKER_INFLUXDB_INIT_USERNAME=admin \
		  -e DOCKER_INFLUXDB_INIT_PASSWORD=adminpassword \
		  -e DOCKER_INFLUXDB_INIT_ORG=myorg \
		  -e DOCKER_INFLUXDB_INIT_BUCKET=mydb \
		  -e DOCKER_INFLUXDB_INIT_MODE=setup \
		  -e DOCKER_INFLUXDB_INIT_ADMIN_TOKEN=my-super-secret-auth-token \
		  -p 8086:8086 \
		  influxdb:2

		# Start Grafana container and connect it to the localstack_network
		docker run -d --network localstack_network --name grafana \
		  -e GF_SECURITY_ADMIN_PASSWORD=admin \
		  -p 3000:3000 grafana/grafana:latest

		echo "Starting LocalStack with provided AUTH_TOKEN..."
		@LOCALSTACK_AUTH_TOKEN=$(LOCALSTACK_AUTH_TOKEN) localstack start --network localstack_network -d
		

		# Wait for the services to initialize (optional, you can increase sleep time if necessary)
		echo "Waiting for services to start..."
		sleep 15
		curl -X POST "http://localhost:3000/api/datasources"   -H "Authorization: Basic YWRtaW46YWRtaW4="   -H "Content-Type: application/json"   --data-binary @exported_datasources/influxdb_datasource.json

		echo "LocalStack, InfluxDB, and Grafana are now running."
		echo "Grafana is available at http://localhost:3000"
		echo "InfluxDB is available at http://localhost:8086"

stop:				## Stop the LocalStack Pro container
		# Stop and remove the containers
		docker stop localstack influxdb grafana || echo "One or more containers are not running."
		docker rm localstack influxdb grafana || echo "One or more containers could not be removed."

		# Optionally, remove the Docker network if it's no longer needed
		docker network rm localstack_network || echo "Network was not removed."

		echo "LocalStack, InfluxDB, and Grafana have been stopped and removed."

clean:				## clean up everything
		localstack stop
		make stop
		docker image prune -a --force
		rm lambdas/*/lambda.zip
full:				## Stop the LocalStack Pro container
		make start install awslocal-setup
repost:		# repost website stuff (saves reloading)	
		awslocal s3 sync --delete ./website s3://webapp
		awslocal s3 website s3://webapp --index-document index.html

.PHONY: usage install build awslocal-setup terraform-destroy start stop full clean repost
