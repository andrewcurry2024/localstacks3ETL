#!/bin/bash

(cd lambdas/presign; rm -f lambda.zip; zip lambda.zip handler.py)
(cd lambdas/list; rm -f lambda.zip; zip lambda.zip handler.py)
(
cd lambdas/transform
rm -rf package lambda.zip
mkdir package
pip3 install -r requirements.txt --platform manylinux2014_x86_64 --only-binary=:all: -t package
cd package
find . -name 'tests' -exec rm -rf {} \;
find . -name 'doc' -exec rm -rf {} \;
find . -name '*.rst' -exec rm -f {} \;
find . -name "__pycache__" -exec rm -rf {} \;
find . -name '*.pyc' -exec rm -rf {} \;
zip  -r ../lambda.zip *  # Using -9 with recursive option here as well
cd ../
zip  lambda.zip handler.py
zip  lambda.zip subroutines_config.json
zip  lambda.zip etl/*
zip  lambda.zip database/*
zip  lambda.zip utils/*
zip  lambda.zip configs/*
zip  lambda.zip importers/*
rm -rf package
)
