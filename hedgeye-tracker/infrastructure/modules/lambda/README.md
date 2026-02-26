# Lambda Module

Creates an AWS Lambda function for the Hedgeye Risk Ranges Tracker application.

## Features

- Lambda function with configurable runtime, memory, and timeout
- CloudWatch Log Group with configurable retention
- Optional Lambda function URL for direct HTTP access
- EventBridge invocation permission for scheduled execution

## Usage

```hcl
module "lambda" {
  source = "./modules/lambda"

  function_name      = "dev-hedgeye-risk-tracker"
  execution_role_arn = module.iam.execution_role_arn

  deployment_package_path = "${path.root}/../deployment/lambda.zip"

  environment_variables = {
    AWS_REGION        = "us-west-2"
    GMAIL_USER_EMAIL  = "shared@singtech.com.au"
    GMAIL_SECRET_NAME = "dev/hedgeye/gmail-service-account"
  }

  timeout     = 900  # 15 minutes
  memory_size = 512

  log_retention_days = 30

  tags = {
    Environment = "dev"
    Project     = "hedgeye-risk-tracker"
  }
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| function_name | Name of the Lambda function | `string` | n/a | yes |
| execution_role_arn | ARN of the IAM role for Lambda execution | `string` | n/a | yes |
| description | Description of the Lambda function | `string` | `"Hedgeye Risk Ranges Tracker..."` | no |
| handler | Lambda function handler | `string` | `"lambda_handler.handler"` | no |
| runtime | Lambda runtime environment | `string` | `"python3.11"` | no |
| timeout | Lambda timeout in seconds (max 900) | `number` | `900` | no |
| memory_size | Memory allocation in MB | `number` | `512` | no |
| deployment_package_path | Path to the Lambda zip file | `string` | `null` | no |
| environment_variables | Environment variables map | `map(string)` | `{}` | no |
| log_retention_days | CloudWatch Logs retention | `number` | `30` | no |
| enable_function_url | Enable Lambda function URL | `bool` | `false` | no |
| allow_eventbridge_invocation | Allow EventBridge to invoke | `bool` | `true` | no |
| eventbridge_rule_arn | ARN of EventBridge rule | `string` | `null` | no |
| tags | Tags for all resources | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| function_arn | ARN of the Lambda function |
| function_name | Name of the Lambda function |
| invoke_arn | ARN used to invoke the function |
| function_url | URL of the function (if enabled) |
| log_group_name | CloudWatch Log Group name |
| log_group_arn | CloudWatch Log Group ARN |
| version | Published version |
| last_modified | Last modified timestamp |

## Deployment Package

The Lambda function requires a deployment package (zip file) containing:
- Application source code
- All Python dependencies
- Lambda handler wrapper

### Creating the Deployment Package

```bash
# From project root
cd src

# Install dependencies to a package directory
pip install -r ../requirements.txt -t package/

# Copy source code
cp -r *.py handlers/ services/ util/ package/

# Create zip file
cd package
zip -r ../../deployment/lambda.zip .
```

### Lambda Handler

Create a `lambda_handler.py` in the src directory:

```python
import json
from main import main

def handler(event, context):
    """AWS Lambda handler function."""
    try:
        main()
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Success'})
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
```

## Manual Invocation

```bash
# Invoke Lambda function directly
aws lambda invoke \
  --function-name dev-hedgeye-risk-tracker \
  --payload '{}' \
  response.json

# View response
cat response.json

# View logs
aws logs tail /aws/lambda/dev-hedgeye-risk-tracker --follow
```

## Updating the Function

```bash
# Update deployment package
aws lambda update-function-code \
  --function-name dev-hedgeye-risk-tracker \
  --zip-file fileb://deployment/lambda.zip
```
