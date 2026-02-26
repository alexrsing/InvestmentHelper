"""
Google Chat Notifier Lambda Function

Forwards CloudWatch Alarm notifications from SNS to Google Chat.
"""

import json
import os
import urllib.request
import urllib.error

import boto3


def get_webhook_url():
    """Retrieve Google Chat webhook URL from Secrets Manager."""
    secret_name = os.environ.get("WEBHOOK_SECRET_NAME")
    region = os.environ.get("AWS_REGION", "us-west-2")

    if not secret_name:
        raise ValueError("WEBHOOK_SECRET_NAME environment variable not set")

    client = boto3.client("secretsmanager", region_name=region)
    response = client.get_secret_value(SecretId=secret_name)
    secret = json.loads(response["SecretString"])

    return secret.get("webhook_url")


def format_alarm_message(alarm_data):
    """Format CloudWatch alarm data as a Google Chat message."""
    alarm_name = alarm_data.get("AlarmName", "Unknown Alarm")
    new_state = alarm_data.get("NewStateValue", "UNKNOWN")
    reason = alarm_data.get("NewStateReason", "No reason provided")
    region = alarm_data.get("Region", "us-west-2")
    timestamp = alarm_data.get("StateChangeTime", "")

    # Set emoji based on state
    if new_state == "ALARM":
        emoji = "🚨"
        header = "ALARM TRIGGERED"
    elif new_state == "OK":
        emoji = "✅"
        header = "ALARM RESOLVED"
    else:
        emoji = "⚠️"
        header = new_state

    # Build CloudWatch console URL
    alarm_url = (
        f"https://{region}.console.aws.amazon.com/cloudwatch/home"
        f"?region={region}#alarmsV2:alarm/{alarm_name}"
    )

    # Format as simple text message (more reliable than cards)
    time_str = timestamp[:19] if timestamp else "N/A"
    reason_short = reason[:300] + "..." if len(reason) > 300 else reason

    message = {
        "text": (
            f"{emoji} *{header}*\n\n"
            f"*Alarm:* {alarm_name}\n"
            f"*State:* {new_state}\n"
            f"*Region:* {region}\n"
            f"*Time:* {time_str}\n\n"
            f"*Reason:* {reason_short}\n\n"
            f"<{alarm_url}|View in CloudWatch>"
        )
    }

    return message


def send_to_google_chat(webhook_url, message):
    """Send message to Google Chat webhook."""
    data = json.dumps(message).encode("utf-8")

    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status == 200
    except urllib.error.URLError as e:
        print(f"Error sending to Google Chat: {e}")
        return False


def handler(event, context):
    """Lambda handler for SNS notifications."""
    print(f"Received event: {json.dumps(event)}")

    try:
        webhook_url = get_webhook_url()
    except Exception as e:
        print(f"Error getting webhook URL: {e}")
        return {"statusCode": 500, "body": f"Error getting webhook URL: {e}"}

    # Process SNS records
    for record in event.get("Records", []):
        if record.get("EventSource") != "aws:sns":
            print(f"Skipping non-SNS record: {record.get('EventSource')}")
            continue

        sns_message = record.get("Sns", {}).get("Message", "{}")

        try:
            alarm_data = json.loads(sns_message)
        except json.JSONDecodeError:
            print(f"Could not parse SNS message as JSON: {sns_message}")
            # Send as plain text
            message = {"text": f"CloudWatch Notification: {sns_message}"}
            send_to_google_chat(webhook_url, message)
            continue

        # Format and send alarm notification
        message = format_alarm_message(alarm_data)
        success = send_to_google_chat(webhook_url, message)

        if success:
            print(f"Successfully sent notification for alarm: {alarm_data.get('AlarmName')}")
        else:
            print(f"Failed to send notification for alarm: {alarm_data.get('AlarmName')}")

    return {"statusCode": 200, "body": "Notifications processed"}
