# Serverless Performance metric ETL 

| Integrations | AWS SDK, AWS CLI, GitHub actions, pytest                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| Categories   | Serverless, S3 notifications, S3 website, Lambda function URLs, LocalStack developer endpoints, JavaScript, Python                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| Level        | Intermediate                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |

## Introduction


Here's a short summary of AWS service features we use:
* S3 bucket notifications to trigger a Lambda
* Lambda function URLs
* Lambda SNS on failure destination
* SNS to SES Subscriptions
* SES LocalStack testing endpoint

## Architecture overview

## Prerequisites

### Dev environment

Make sure you use the same version as the Python Lambdas to make Pillow work.
If you use pyenv, then first install and activate Python 3.11:

```bash
pyenv install 3.11.6
pyenv global 3.11.6
```

```console
% python --version
Python 3.11.6
```

Create a virtualenv and install all the development dependencies there:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

## Instructions

modify.env if needed
Then, run `make start` to initiate LocalStack on your machine. 
Next, execute `make install` to install needed dependencies.
After that, run `make awslocal-setup` to set up the infrastructure using `awslocal`, a wrapper for the AWS CLI.
```bash
make start
make install
make awslocal-setup
```

