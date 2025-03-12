#!/usr/local/bin/bash

# Ensure that the script is run with bash
if [ -z "$BASH_VERSION" ]; then
    echo "This script requires Bash. Please run it with Bash." >&2
    exit 1
fi

# Set AWS Pricing Variables (Adjust as per latest AWS pricing)
STORAGE_PRICE=0.023  # $ per GB for Standard Storage
GET_PRICE=0.0004  # $ per 1,000 GET requests
PUT_PRICE=0.005   # $ per 1,000 PUT requests
TRANSFER_PRICE=0.09  # $ per GB of data transfer

# Log & Report Files
LOG_FILE="s3_cost_report.log"
CSV_FILE="s3_cost_report.csv"
REPORT_HTML="s3_cost_report.html"

# Slack Webhook (Set this if you want Slack alerts)
SLACK_WEBHOOK_URL="https://hooks.slack.com/services/your/webhook/url"

echo "Bucket Name,Region,Storage (GB),GET Cost ($),PUT Cost ($),Data Transfer Cost ($),Total Cost ($),Most Expensive Operation" > "$CSV_FILE"

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

log_message "Fetching list of S3 buckets..."
buckets=$(aws s3api list-buckets --query "Buckets[].Name" --output text 2>/dev/null)
if [ $? -ne 0 ]; then
    handle_error "aws s3api list-buckets" "Failed to retrieve S3 bucket list"
fi

log_message "Processing S3 buckets..."

for bucket in $buckets; do
    log_message "Processing bucket: $bucket"

    region=$(aws s3api get-bucket-location --bucket "$bucket" --query "LocationConstraint" --output text 2>/dev/null)
    region="${region:-ap-south-1}"

   get_metric_data() {
    local metric="$1"
    local dimensions="Name=BucketName,Value=$bucket"
    if [[ "$metric" == "BucketSizeBytes" ]]; then
        dimensions="$dimensions Name=StorageType,Value=StandardStorage"
    elif [[ "$metric" == "GetRequests" ]]; then
        dimensions="$dimensions Name=RequestType,Value=GET"
    elif [[ "$metric" == "PutRequests" ]]; then
        dimensions="$dimensions Name=RequestType,Value=PUT"
    fi

    local response=$(aws cloudwatch get-metric-statistics --namespace AWS/S3 --metric-name "$metric" \
        --dimensions $dimensions \
        --statistics Sum --start-time "$start_date"T00:00:00Z --end-time "$end_date"T23:59:59Z --period 86400 \
        --region "$region" --output json 2>/dev/null)

    # Debugging the API response to ensure data is fetched
    log_message "CloudWatch response for $metric: $response"

    local value=$(echo "$response" | jq -r '.Datapoints[0].Sum')
    echo "${value:-0}"
}


    storage_bytes=$(get_metric_data BucketSizeBytes)
    get_requests=$(get_metric_data GetRequests)
    put_requests=$(get_metric_data PutRequests)
    transfer_bytes=$(get_metric_data "BytesTransferred")  # Corrected metric for data transfer

    # Ensure no zero values for calculations
    storage_gb=$(echo "scale=4; $storage_bytes / (1024^3)" | bc)
    transfer_gb=$(echo "scale=4; $transfer_bytes / (1024^3)" | bc)

    storage_cost=$(echo "scale=4; $storage_gb * $STORAGE_PRICE" | bc)
    get_cost=$(echo "scale=4; ($get_requests / 1000) * $GET_PRICE" | bc)
    put_cost=$(echo "scale=4; ($put_requests / 1000) * $PUT_PRICE" | bc)
    transfer_cost=$(echo "scale=4; $transfer_gb * $TRANSFER_PRICE" | bc)
    total_cost=$(echo "scale=4; $storage_cost + $get_cost + $put_cost + $transfer_cost" | bc)

    declare -A operation_costs=( ["GET"]=$get_cost ["PUT"]=$put_cost ["TRANSFER"]=$transfer_cost )
    most_expensive_op="GET"
    max_cost=$get_cost
    for op in "${!operation_costs[@]}"; do
        if (( $(echo "${operation_costs[$op]} > $max_cost" | bc -l) )); then
            max_cost="${operation_costs[$op]}"
            most_expensive_op="$op"
        fi
    done

    echo "$bucket,$region,$storage_gb,$get_cost,$put_cost,$transfer_cost,$total_cost,$most_expensive_op" >> "$CSV_FILE"
    log_message "Bucket: $bucket - Total Cost: $total_cost, Most Expensive Operation: $most_expensive_op"

    if (( $(echo "$total_cost > 100" | bc -l) )); then
        curl -X POST -H 'Content-type: application/json' --data \
        "{\"text\": \"🚨 High S3 Cost Alert! Bucket: *$bucket* in *$region* has cost \$$total_cost\"}" \
        "$SLACK_WEBHOOK_URL"
    fi

done

log_message "Cost calculation complete. Report saved to $CSV_FILE."

echo "<html>
<head>
    <title>S3 Cost Report</title>
</head>
<body>
    <h1>S3 Cost Report</h1>
    <table border='1'>
        <tr>
            <th>Bucket Name</th>
            <th>Region</th>
            <th>Storage (GB)</th>
            <th>GET Cost ($)</th>
            <th>PUT Cost ($)</th>
            <th>Data Transfer Cost ($)</th>
            <th>Total Cost ($)</th>
            <th>Most Expensive Operation</th>
        </tr>" > "$REPORT_HTML"

while IFS=, read -r bucket region storage_gb get_cost put_cost transfer_cost total_cost most_expensive_op; do
    echo "        <tr>
            <td>$bucket</td>
            <td>$region</td>
            <td>$storage_gb</td>
            <td>$get_cost</td>
            <td>$put_cost</td>
            <td>$transfer_cost</td>
            <td>$total_cost</td>
            <td>$most_expensive_op</td>
        </tr>" >> "$REPORT_HTML"
done < "$CSV_FILE"

echo "    </table>
</body>
</html>" >> "$REPORT_HTML"

log_message "HTML report generated at $REPORT_HTML."
