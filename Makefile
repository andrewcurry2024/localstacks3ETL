export AWS_ACCESS_KEY_ID ?= test
export AWS_SECRET_ACCESS_KEY ?= test
exit ACTIVATE_PRO=0
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
		@LOCALSTACK_AUTH_TOKEN=$(LOCALSTACK_AUTH_TOKEN) localstack start -d

stop:				## Stop the LocalStack Pro container
		localstack stop
clean:				## clean up everything
		localstack stop
		docker image prune -a
		rm lambda\*\*.zip
full:				## Stop the LocalStack Pro container
		make start install awslocal-setup

.PHONY: usage install build awslocal-setup terraform-destroy start stop full clean
