#!/bin/bash

# Ensure that the script is run with bash
if [ -z "$BASH_VERSION" ]; then
    echo "This script requires Bash. Please run it with Bash." >&2
    exit 1
fi

# Set CloudWatch Pricing Variables (adjust as per AWS pricing)
CUSTOM_METRIC_PRICE=0.30   # $ per metric per month
LOG_INGESTION_PRICE=0.50   # $ per GB of log data ingested
LOG_STORAGE_PRICE=0.03    # $ per GB per month for log storage
DASHBOARD_PRICE=3.00      # $ per dashboard per month
ALARM_PRICE=0.10          # $ per alarm per month

# Log & Report Files
LOG_FILE="cloudwatch_cost_report.log"
CSV_FILE="cloudwatch_cost_report.csv"
REPORT_HTML="cloudwatch_cost_report.html"

echo "Metric Name,Metric Count,Log Ingestion (GB),Log Storage (GB),Alarms Count,Dashboards Count,Total Cost ($)" > "$CSV_FILE"

log_message() {
    local message="$1"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $message" >> "$LOG_FILE"
}

handle_error() {
    local command="$1"
    local error_msg="$2"
    log_message "ERROR: $error_msg"
    log_message "Command failed: $command"
    exit 1
}

get_date_range() {
    echo "Enter start date (YYYY-MM-DD) or press Enter to use today:"
    read start_date
    start_date="${start_date:-$(date +%Y-%m-%d)}"

    echo "Enter end date (YYYY-MM-DD) or press Enter to use today:"
    read end_date
    end_date="${end_date:-$(date +%Y-%m-%d)}"

    echo "Using date range: $start_date to $end_date"
}

# Ask for custom date range
echo "Do you want to specify a custom date range? (y/n)"
read use_custom_range
if [[ "$use_custom_range" == "y" ]]; then
    get_date_range
else
    start_date=$(date +%Y-%m-%d)
    end_date=$(date +%Y-%m-%d)
fi

log_message "Fetching CloudWatch resources and metrics..."

# Get CloudWatch Metrics
metrics=$(aws cloudwatch list-metrics --region ap-south-1 --output text 2>/dev/null)
if [ $? -ne 0 ]; then
    handle_error "aws cloudwatch list-metrics" "Failed to retrieve CloudWatch metrics list"
fi

metric_count=$(echo "$metrics" | grep "MetricName" | wc -l)

log_message "Fetching CloudWatch Alarms..."
alarms=$(aws cloudwatch describe-alarms --region ap-south-1 --output text 2>/dev/null)
if [ $? -ne 0 ]; then
    handle_error "aws cloudwatch describe-alarms" "Failed to retrieve CloudWatch alarms list"
fi

alarm_count=$(echo "$alarms" | grep "AlarmName" | wc -l)

log_message "Fetching CloudWatch Dashboards..."
dashboards=$(aws cloudwatch list-dashboards --region ap-south-1 --output text 2>/dev/null)
if [ $? -ne 0 ]; then
    handle_error "aws cloudwatch list-dashboards" "Failed to retrieve CloudWatch dashboards list"
fi

dashboard_count=$(echo "$dashboards" | grep "DashboardName" | wc -l)

log_message "Fetching CloudWatch Log Groups..."
log_groups=$(aws logs describe-log-groups --region ap-south-1 --output text 2>/dev/null)
if [ $? -ne 0 ]; then
    handle_error "aws logs describe-log-groups" "Failed to retrieve CloudWatch log groups list"
fi

# Estimate log data ingestion and storage
log_ingestion_gb=0
log_storage_gb=0

for log_group in $(echo "$log_groups" | grep "logGroupName" | awk '{print $2}'); do
    # Get the total log data ingestion and storage
    log_ingestion=$(aws logs get-log-events --log-group-name "$log_group" --start-time $(date --date="$start_date" +%s) --end-time $(date --date="$end_date" +%s) --region ap-south-1 --output text 2>/dev/null)
    if [[ $? -ne 0 ]]; then
        handle_error "aws logs get-log-events" "Failed to retrieve log data for group $log_group"
    fi

    log_data_size=$(echo "$log_ingestion" | grep "bytes" | awk '{sum += $4} END {print sum}')
    log_storage_gb=$(echo "scale=4; $log_data_size / (1024^3)" | bc)
    log_ingestion_gb=$(echo "scale=4; $log_ingestion_gb + $log_storage_gb" | bc)
done

# Calculate costs
metric_cost=$(echo "scale=4; $metric_count * $CUSTOM_METRIC_PRICE" | bc)
log_cost=$(echo "scale=4; $log_ingestion_gb * $LOG_INGESTION_PRICE" | bc)
storage_cost=$(echo "scale=4; $log_storage_gb * $LOG_STORAGE_PRICE" | bc)
dashboard_cost=$(echo "scale=4; $dashboard_count * $DASHBOARD_PRICE" | bc)
alarm_cost=$(echo "scale=4; $alarm_count * $ALARM_PRICE" | bc)

total_cost=$(echo "scale=4; $metric_cost + $log_cost + $storage_cost + $dashboard_cost + $alarm_cost" | bc)

# Output the results
echo "$metric_count,$log_ingestion_gb,$log_storage_gb,$alarm_count,$dashboard_count,$total_cost" >> "$CSV_FILE"

log_message "CloudWatch Cost Estimation - Total Cost: $total_cost"

# Generate HTML Report from CSV
echo "<html>
<head>
    <title>CloudWatch Cost Report</title>
</head>
<body>
    <h1>CloudWatch Cost Report</h1>
    <table border='1'>
        <tr>
            <th>Metric Count</th>
            <th>Log Ingestion (GB)</th>
            <th>Log Storage (GB)</th>
            <th>Alarms Count</th>
            <th>Dashboards Count</th>
            <th>Total Cost ($)</th>
        </tr>" > "$REPORT_HTML"

# Read CSV and convert to HTML table
while IFS=, read -r metric_count log_ingestion log_storage alarms_count dashboards_count total_cost; do
    echo "        <tr>
            <td>$metric_count</td>
            <td>$log_ingestion</td>
            <td>$log_storage</td>
            <td>$alarms_count</td>
            <td>$dashboards_count</td>
            <td>$total_cost</td>
        </tr>" >> "$REPORT_HTML"
done < "$CSV_FILE"

echo "    </table>
</body>
</html>" >> "$REPORT_HTML"

log_message "HTML report generated at $REPORT_HTML."
