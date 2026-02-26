# Monitoring Module

Creates CloudWatch alarms and SNS topics for monitoring the Hedgeye Risk Ranges Tracker application.

## Features

- SNS topics for critical and warning alerts
- Email subscription support
- Lambda execution monitoring (errors, throttles, duration)
- Log-based metric filters for authentication and DynamoDB errors
- Configurable alarm thresholds

## Usage

```hcl
module "monitoring" {
  source = "./modules/monitoring"

  environment           = "dev"
  lambda_function_name  = module.lambda[0].function_name
  lambda_log_group_name = module.lambda[0].log_group_name
  lambda_timeout_ms     = 900000  # 15 minutes in ms

  # Email notifications (optional)
  alert_email = "alerts@company.com"

  # No-invocation alarm (for scheduled execution)
  enable_no_invocation_alarm        = true
  expected_invocations_period_hours = 24

  tags = {
    Environment = "dev"
    Project     = "hedgeye-risk-tracker"
  }
}
```

## Alarms Created

### Critical Alarms (immediate attention required)

| Alarm | Description | Threshold |
|-------|-------------|-----------|
| Lambda Errors | Function execution errors | > 0 errors |
| Lambda Throttles | Function throttling | > 0 throttles |
| Auth Errors | Gmail/AWS authentication failures | > 0 errors |
| DynamoDB Errors | Database operation failures | > 5 errors |

### Warning Alarms (investigate when convenient)

| Alarm | Description | Threshold |
|-------|-------------|-----------|
| Duration Warning | Execution approaching timeout | > 80% of timeout |
| No Invocations | Missing scheduled executions | < 1 invocation/period |

## SNS Topics

Two SNS topics are created for different alert severities:

- `{env}-hedgeye-alerts-critical`: Immediate attention required
- `{env}-hedgeye-alerts-warning`: Investigate when convenient

### Adding Subscriptions

Email subscriptions are automatically created if `alert_email` is provided.

For additional subscriptions (Slack, PagerDuty, etc.), use the AWS Console or CLI:

```bash
# Subscribe to Slack webhook
aws sns subscribe \
  --topic-arn arn:aws:sns:us-west-2:123456789:dev-hedgeye-alerts-critical \
  --protocol https \
  --notification-endpoint https://hooks.slack.com/services/XXX

# Subscribe Lambda function
aws sns subscribe \
  --topic-arn arn:aws:sns:us-west-2:123456789:dev-hedgeye-alerts-critical \
  --protocol lambda \
  --notification-endpoint arn:aws:lambda:us-west-2:123456789:function:alert-handler
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| environment | Environment name | `string` | n/a | yes |
| lambda_function_name | Lambda function name | `string` | n/a | yes |
| lambda_log_group_name | Lambda log group name | `string` | n/a | yes |
| lambda_timeout_ms | Lambda timeout in ms | `number` | `900000` | no |
| alert_email | Email for notifications | `string` | `""` | no |
| enable_no_invocation_alarm | Enable missing invocation alarm | `bool` | `true` | no |
| expected_invocations_period_hours | Hours between expected invocations | `number` | `24` | no |
| tags | Resource tags | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| critical_alerts_topic_arn | ARN of critical alerts SNS topic |
| warning_alerts_topic_arn | ARN of warning alerts SNS topic |
| lambda_errors_alarm_arn | ARN of Lambda errors alarm |
| lambda_throttles_alarm_arn | ARN of Lambda throttles alarm |
| auth_errors_alarm_arn | ARN of auth errors alarm |
| dynamodb_errors_alarm_arn | ARN of DynamoDB errors alarm |
| alarm_summary | Summary of all alarms created |

## CloudWatch Logs Insights Queries

Useful queries for investigating alerts:

```
# Find all errors in last hour
fields @timestamp, @message
| filter @message like /ERROR|Error|error/
| sort @timestamp desc
| limit 100

# Count emails processed
fields @timestamp
| filter @message like /Retrieved.*records/
| stats count() by bin(5m)

# Find authentication failures
fields @timestamp, @message
| filter @message like /Authentication error|credential refresh failed/
| sort @timestamp desc

# Lambda execution summary
fields @timestamp, @requestId, @duration, @billedDuration, @memorySize, @maxMemoryUsed
| stats avg(@duration), max(@duration), avg(@maxMemoryUsed) by bin(1h)
```

## Testing Alarms

To test alarm notifications:

```bash
# Manually set alarm state to ALARM
aws cloudwatch set-alarm-state \
  --alarm-name dev-hedgeye-lambda-errors \
  --state-value ALARM \
  --state-reason "Testing alarm notification"

# Wait for notification, then reset to OK
aws cloudwatch set-alarm-state \
  --alarm-name dev-hedgeye-lambda-errors \
  --state-value OK \
  --state-reason "Test complete"
```

## Common Alert Runbook

### Lambda Errors
1. Check CloudWatch Logs for error details
2. Look for authentication or network issues
3. Verify Gmail and AWS credentials are valid
4. Check if quotas are exceeded

### Authentication Errors
1. Verify Gmail service account credentials in Secrets Manager
2. Check domain-wide delegation is still configured
3. Verify GMAIL_USER_EMAIL is correct
4. Check for Google Workspace changes

### DynamoDB Errors
1. Check DynamoDB table exists and is accessible
2. Verify IAM permissions
3. Check for table capacity issues (if using provisioned)
4. Look for item size limits (400KB)

### No Invocations
1. Check EventBridge rule is enabled
2. Verify schedule expression is correct
3. Check Lambda function exists
4. Look for EventBridge delivery failures
