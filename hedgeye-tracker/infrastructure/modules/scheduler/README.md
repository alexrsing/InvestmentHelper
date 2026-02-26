# Scheduler Module

Creates an AWS EventBridge rule for scheduled Lambda function invocation.

## Features

- Configurable cron or rate schedule expression
- Enable/disable schedule without destroying resources
- Optional custom event payload
- Automatic Lambda invocation permission

## Usage

```hcl
module "scheduler" {
  source = "./modules/scheduler"

  rule_name    = "dev-hedgeye-daily-schedule"
  environment  = "dev"

  # Run at 8 AM UTC every weekday
  schedule_expression = "cron(0 8 ? * MON-FRI *)"

  # Lambda function to invoke
  lambda_function_arn  = module.lambda[0].function_arn
  lambda_function_name = module.lambda[0].function_name

  # Disable for initial deployment
  enabled = false

  tags = {
    Environment = "dev"
    Project     = "hedgeye-risk-tracker"
  }
}
```

## Schedule Expression Examples

### Cron Expressions

```hcl
# Daily at 8 AM UTC (market hours)
schedule_expression = "cron(0 8 * * ? *)"

# Every weekday at 8 AM UTC
schedule_expression = "cron(0 8 ? * MON-FRI *)"

# Weekly on Monday at 9 AM UTC
schedule_expression = "cron(0 9 ? * MON *)"

# Twice daily at 8 AM and 4 PM UTC
schedule_expression = "cron(0 8,16 * * ? *)"
```

### Rate Expressions

```hcl
# Every 6 hours
schedule_expression = "rate(6 hours)"

# Every day
schedule_expression = "rate(1 day)"

# Every 30 minutes
schedule_expression = "rate(30 minutes)"
```

### Cron Format Reference

```
cron(Minutes Hours Day-of-month Month Day-of-week Year)

Fields:
- Minutes: 0-59
- Hours: 0-23
- Day-of-month: 1-31
- Month: 1-12 or JAN-DEC
- Day-of-week: 1-7 or SUN-SAT
- Year: 1970-2199

Special characters:
- * : all values
- ? : no specific value (day-of-month or day-of-week)
- - : range (e.g., MON-FRI)
- , : list (e.g., MON,WED,FRI)
- / : increment (e.g., 0/15 = every 15 minutes)
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| rule_name | Name of the EventBridge rule | `string` | n/a | yes |
| environment | Environment name | `string` | n/a | yes |
| schedule_expression | Cron or rate expression | `string` | n/a | yes |
| lambda_function_arn | ARN of Lambda to invoke | `string` | n/a | yes |
| lambda_function_name | Name of Lambda to invoke | `string` | n/a | yes |
| description | Rule description | `string` | `"Scheduled execution..."` | no |
| enabled | Enable the rule | `bool` | `true` | no |
| event_input | Custom JSON payload | `string` | `null` | no |
| tags | Resource tags | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| rule_arn | ARN of the EventBridge rule |
| rule_name | Name of the rule |
| rule_id | ID of the rule |
| schedule_expression | Configured schedule |
| enabled | Whether rule is enabled |

## Manual Trigger

To manually trigger the schedule (useful for testing):

```bash
# Get the rule details
aws events describe-rule --name dev-hedgeye-daily-schedule

# Manually invoke the Lambda function
aws lambda invoke \
  --function-name dev-hedgeye-risk-tracker \
  --payload '{"source": "manual", "test": true}' \
  response.json

# View response
cat response.json
```

## Monitoring

View scheduled invocations in CloudWatch:

```bash
# List recent invocations
aws logs filter-log-events \
  --log-group-name /aws/lambda/dev-hedgeye-risk-tracker \
  --start-time $(date -d '1 hour ago' +%s000) \
  --filter-pattern "Request ID"
```

## Environment-Specific Schedules

Recommended schedules per environment:

| Environment | Schedule | Purpose |
|-------------|----------|---------|
| Dev | Disabled or rate(1 day) | Testing only |
| Staging | cron(0 8 * * ? *) | Daily validation |
| Prod | cron(0 8 ? * MON-FRI *) | Market hours |
