import json
import boto3
import urllib3
import os
import re
import urllib.parse
from datetime import datetime

# Define the ONE person to tag in Slack
SLACK_MENTION = "<@U58HJDVAQ>"  # Replace with actual Slack user ID

def get_slack_webhook():
    """Retrieve Slack webhook URL from AWS Secrets Manager."""
    secret_name = os.getenv("SLACK_SECRET_NAME", "SlackWebhookURL")
    region_name = boto3.session.Session().region_name

    client = boto3.client("secretsmanager", region_name=region_name)
    response = client.get_secret_value(SecretId=secret_name)
    
    return json.loads(response["SecretString"])["webhook_url_alarm"]

def extract_current_value(reason):
    """Extracts the current value from the CloudWatch alarm reason string."""
    match = re.search(r"\[(\d+(\.\d+)?) \(", reason)
    return float(match.group(1)) if match else None

def determine_severity(threshold, current_value):
    """Determine severity based on threshold breach percentage."""
    if current_value is None:
        return "⚪ Unknown", "No severity determined."
    
    breach_percentage = (current_value / threshold) * 100
    
    if breach_percentage > 200:
        return "🔴 Critical", "🚨 *Immediate Action:* Requires urgent investigation."
    elif breach_percentage > 150:
        return "🟠 High", "⚠️ *Action Needed:* Investigate and resolve soon."
    elif breach_percentage > 100:
        return "🟡 Medium", "📊 *Monitor:* Watch the trend and take action if needed."
    else:
        return "🟢 Low", "✅ *No Immediate Action:* Continue monitoring."

def get_suggested_action(metric_name, threshold, current_value):
    """Provides suggested actions based on metric type and threshold breach."""
    if current_value is None:
        return "No data available for suggested action."

    if metric_name == "CPUUtilization":
        if current_value > threshold * 1.5:
            return "🚀 *Immediate Action:* Scale up the instance or investigate high CPU-consuming processes."
        return " Monitor CPU usage; consider optimization if it remains high."

    if metric_name in ["WriteIOPS", "ReadIOPS"]:
        if current_value > threshold * 1.5:
            return "🚀 *Immediate Action:* Optimize database queries and indexing."
        return " Review query patterns and check inefficient storage usage."

    if metric_name == "MemoryUtilization":
        if current_value > threshold * 1.5:
            return "🚀 *Immediate Action:* Restart unused services or increase memory allocation."
        return " Monitor memory usage trends."

    if metric_name == "DiskUsage":
        if current_value > threshold * 1.5:
            return "🚀 *Immediate Action:* Increase disk size or clean up unnecessary files."
        return " Archive old data and monitor disk usage."

    if metric_name in ["NetworkIn", "NetworkOut"]:
        if current_value > threshold * 1.5:
            return "🚀 *Immediate Action:* Analyze load balancer logs for unusual spikes."
        return " Monitor network traffic and investigate anomalies."

    return "🔍 *General Action:* Investigate the cause and take necessary steps."

def lambda_handler(event, context):
    http = urllib3.PoolManager()
    slack_webhook_url = get_slack_webhook()

    try:
        message = json.loads(event["Records"][0]["Sns"]["Message"])

        # Extract details
        alarm_name = message.get("AlarmName", "Unknown Alarm")
        new_state = message.get("NewStateValue", "UNKNOWN")
        old_state = message.get("OldStateValue", "UNKNOWN")
        reason = message.get("NewStateReason", "No reason provided")
        metric_name = message.get("Trigger", {}).get("MetricName", "N/A")
        namespace = message.get("Trigger", {}).get("Namespace", "N/A")
        threshold = message.get("Trigger", {}).get("Threshold", 0)
        current_value = extract_current_value(reason)
        aws_account = message.get("AWSAccountId", "Unknown Account")
        region = boto3.session.Session().region_name
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")



         # Ignore unknown alarms
        if alarm_name == "Unknown Alarm" or new_state == "UNKNOWN":
            print("Ignoring unknown alarm.")
            return {"statusCode": 200, "body": "Unknown alarm ignored."}
        

        # Determine severity and suggested action
        severity, severity_message = determine_severity(threshold, current_value)
        suggested_action = get_suggested_action(metric_name, threshold, current_value)

        # AWS CloudWatch Alarm URL
               # AWS CloudWatch Alarm URL
        encoded_alarm_name = urllib.parse.quote(alarm_name)
        dashboard_url = (
            f"https://{region}.console.aws.amazon.com/cloudwatch/home"
            f"?region={region}#alarmsV2:alarm/{encoded_alarm_name}"
        )




        # Construct Slack message
        slack_message = {
            "text": (
                f"{SLACK_MENTION} ⚠️ *AWS Alarm Triggered!*\n"
                f" *Alarm:* `{alarm_name}`\n"
                f" *State Change:* `{old_state} → {new_state}`\n"
                f" *Reason:* {reason}\n"
                f" *Metric:* `{metric_name}` (`{namespace}`)\n"
                f" *Threshold:* `{threshold}` | *Current Value:* `{current_value}`\n"
                f" *Timestamp:* `{timestamp}`\n"
                f" *Severity:* {severity}\n"
                f"{severity_message}\n"
                f" *Suggested Action:* {suggested_action}\n"
                f" *[View in AWS CloudWatch]({dashboard_url})*"
            )
        }

        response = http.request(
            "POST", slack_webhook_url, 
            body=json.dumps(slack_message).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        if response.status != 200:
            raise Exception(f"Slack API error: {response.data.decode('utf-8')}")

        return {"statusCode": 200, "body": "Notification sent successfully"}

    except Exception as e:
        print(f"Error: {str(e)}")
        return {"statusCode": 500, "body": f"Error sending notification: {str(e)}"} 