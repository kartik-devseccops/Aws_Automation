import json
import boto3
import urllib3
import os
import logging
from datetime import datetime, timedelta

# Initialize logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Slack Webhook URL from Secrets Manager
def get_slack_webhook():
    try:
        secret_name = os.getenv("SLACK_SECRET_NAME", "SlackWebhookURL")
        region_name = boto3.session.Session().region_name
        client = boto3.client("secretsmanager", region_name=region_name)
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response["SecretString"])["webhook_url_cost"]
    except Exception as e:
        logger.error(f"Error fetching Slack Webhook URL: {e}")
        raise

# Fetch AWS Account ID dynamically
def get_account_id():
    try:
        client = boto3.client("sts")
        account_id = client.get_caller_identity()["Account"]
        return account_id
    except Exception as e:
        logger.error(f"Error fetching AWS Account ID: {e}")
        raise

# Service Mapping
service_mapping = {
    "CloudFront-Prod": "Amazon CloudFront",
    "CloudWatch-Prod": "Amazon CloudWatch",
    "EC2-Instances-Prod": "Amazon Elastic Compute Cloud - Compute",
    "S3-Prod": "Amazon Simple Storage Service",
    "SES-Prod": "Amazon Simple Email Service"
}


# Correct GroupBy logic
def get_group_by_key(service_name):
    if service_name in ["CloudFront-Prod", "CloudWatch-Prod", "S3-Prod"]:
        return "OPERATION"
    elif service_name in ["EC2-Instances-Prod", "SES-Prod"]:
        return "USAGE_TYPE"
    return "SERVICE"


# Fetch Top 3 API Operations/Usage Types
def fetch_top_operations(service_name):
    client = boto3.client("ce", region_name=boto3.session.Session().region_name)
    today = datetime.today().strftime('%Y-%m-%d')
    start_date = (datetime.today() - timedelta(days=1)).strftime('%Y-%m-%d')

    aws_service_name = service_mapping.get(service_name, service_name)
    group_by_key = get_group_by_key(service_name)

    try:
        filter_condition = {
            "Or": [
                {"Dimensions": {"Key": "SERVICE", "Values": [aws_service_name]}},
                {"Dimensions": {"Key": "USAGE_TYPE", "Values": [aws_service_name]}}
            ]
        }

        # Add CloudWatch-specific conditions
        if service_name == "CloudWatch-Prod":
            filter_condition["Or"].append(
                {"Dimensions": {"Key": "OPERATION", "Values": ["PutLogEvents", "ObservationCount:CI-EKS", "LogDelivery"]}}
            )

        response = client.get_cost_and_usage(
            TimePeriod={"Start": start_date, "End": today},
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": group_by_key}],
            Filter=filter_condition
        )

        operations = {}
        for result in response['ResultsByTime']:
            for group in result['Groups']:
                usage_key = group['Keys'][0]
                cost_value = float(group['Metrics']['UnblendedCost']['Amount'])

                if cost_value >= 0.01:
                    operations[usage_key] = f"${round(cost_value, 2)}"

        sorted_operations = sorted(operations.items(), key=lambda item: float(item[1].strip('$')), reverse=True)
        return dict(sorted_operations[:3])

    except Exception as e:
        logger.error(f"Error fetching data for {service_name}: {e}")
        return {}



# Fetch budget data dynamically via AWS Budgets API
# Fetch budget data dynamically via AWS Budgets API
# Fetch budget data dynamically via AWS Budgets API
# Enhanced Budget Data Fetching Logic
# Enhanced Budget Data Fetching Logic with Flexible Matching
def fetch_budget_data():
    client = boto3.client('budgets', region_name=boto3.session.Session().region_name)

    try:
        account_id = get_account_id()
        budgets = []
        threshold_exceeded_data = []

        # Pagination logic for full budget data
        next_token = None
        while True:
            params = {"AccountId": account_id, "MaxResults": 100}
            if next_token:
                params["NextToken"] = next_token
                
            response = client.describe_budgets(**params)

            for budget in response.get('Budgets', []):
                total_spent = float(budget["CalculatedSpend"]["ActualSpend"]["Amount"])
                threshold = float(budget["BudgetLimit"]["Amount"])

                budget_data = {
                    "service": budget["BudgetName"],
                    "total_spent": total_spent,
                    "threshold": threshold,
                    "top_operations": fetch_top_operations(budget["BudgetName"])
                }

                budgets.append(budget_data)

                # ✅ Improved Matching for EC2 and OpenSearch
                if total_spent >= threshold or "EC2" in budget["BudgetName"] or "OpenSearch" in budget["BudgetName"]:
                    threshold_exceeded_data.append({
                        "name": budget["BudgetName"],
                        "thresholds": "Exceeded (1)",
                        "budget": f"${threshold}",
                        "amount_used": f"${total_spent}",
                        "current_vs_budgeted": f"{round((total_spent / threshold) * 100, 2)}%"
                    })

            next_token = response.get('NextToken')
            if not next_token:
                break

        # Filter Daily Budget Report for 5 core services only
        filtered_budget_data = [
            budget for budget in budgets
            if budget['service'] in [
                "CloudFront-Prod", "CloudWatch-Prod", 
                "EC2-Instances-Prod", "S3-Prod", "SES-Prod"
            ]
        ]

        return filtered_budget_data, threshold_exceeded_data

    except Exception as e:
        logger.error(f"Error fetching budget data: {e}")
        return [], []


# Updated Lambda Handler
# Updated Lambda Handler
def lambda_handler(event, context):
    http = urllib3.PoolManager()
    slack_webhook_url = get_slack_webhook()

    budget_data, threshold_exceeded_data = fetch_budget_data()

    if not budget_data:
        logger.info("No budget data found. Skipping Slack message.")
        return {"statusCode": 200, "body": "No budget data available"}

    report_lines = [f"📅 *Daily Budget Report - {datetime.utcnow().strftime('%Y-%m-%d')}*"]

    # Daily Budget Report - Show only 5 core services
    for budget in budget_data:
        service_name = budget["service"]
        total_spent = float(budget["total_spent"])
        top_operations = budget["top_operations"]

        top_operation_details = "\n".join([f"  ➤ {k}: {v}" for k, v in top_operations.items()]) if top_operations else ""

        report_lines.append(
            f"\n🔹 *{service_name}* - ${round(total_spent, 2)}\n"
            f"{top_operation_details}\n"
        )

    # Threshold Exceeded Report - Show ALL exceeded services
    if threshold_exceeded_data:
        report_lines.append("\n📊 *Threshold Exceeded Report*")
        report_lines.append("```")  # Start code block for better alignment
        report_lines.append(f"{'Name'.ljust(25)}| {'Thresholds'.ljust(12)}| {'Budget'.ljust(10)}| {'Amount Used'.ljust(14)}| {'% Used'.ljust(8)}")
        report_lines.append(f"{'-'*25}|{'-'*12}|{'-'*10}|{'-'*14}|{'-'*8}")
        
        for threshold in threshold_exceeded_data:
            report_lines.append(
                f"{threshold['name'].ljust(25)}| {threshold['thresholds'].ljust(12)}| {threshold['budget'].ljust(10)}| {threshold['amount_used'].ljust(14)}| {threshold['current_vs_budgeted'].ljust(8)}"
            )
        report_lines.append("```")  # Close code block

    slack_message = {"text": "\n".join(report_lines)}

    try:
        response = http.request(
            "POST", slack_webhook_url,
            body=json.dumps(slack_message).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        if response.status != 200:
            logger.error(f"Slack API error: {response.data.decode('utf-8')}")
            raise Exception("Failed to send Slack message")
    except Exception as e:
        logger.error(f"Error sending Slack message: {e}")
        return {"statusCode": 500, "body": "Failed to send Slack message"}

    return {"statusCode": 200, "body": "Budget report sent successfully"}
