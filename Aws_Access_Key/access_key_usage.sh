#!/bin/bash

# =======================================================
# AWS IAM Access Key Audit Script (Optimized)
# =======================================================

CSV_FILE="access_key_usage.csv"
LOG_FILE="access_key_usage.log"
HTML_FILE="access_key_usage.html"

# Function to log messages
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Check AWS CLI Configuration
if ! aws sts get-caller-identity >/dev/null 2>&1; then
    log_message "❌ AWS credentials not configured or missing permissions."
    exit 1
fi

log_message "Fetching list of IAM users..."
users=$(aws iam list-users --query "Users[].UserName" --output text | tr '\t' '\n')  # Fix multi-user issue

# Prepare CSV Header
echo "IAM User,Access Key ID,Status,Last Used Date,Service Used,Region,IP Address" > "$CSV_FILE"

# Function to fetch access key details (Define in Exported Script)
fetch_user_data() {
    user="$1"
    log_message "Processing IAM user: $user"

    keys=$(aws iam list-access-keys --user-name "$user" --query "AccessKeyMetadata[*].[AccessKeyId,Status]" --output text)

    if [[ -z "$keys" ]]; then
        log_message "No access keys found for user: $user"
        return
    fi

    while read -r key key_status; do
        if [[ -z "$key" || -z "$key_status" ]]; then
            continue  # Skip empty values
        fi

        log_message "Checking Access Key: $key for user $user"

        read -r last_used last_service last_region < <(aws iam get-access-key-last-used --access-key-id "$key" \
            --query "[AccessKeyLastUsed.LastUsedDate, AccessKeyLastUsed.ServiceName, AccessKeyLastUsed.Region]" --output text 2>/dev/null)
ip_address=$(aws cloudtrail lookup-events --lookup-attributes AttributeKey=AccessKeyId,AttributeValue="$key" \
    --max-results 10 --query "Events[*].SourceIPAddress" --output text 2>/dev/null)

# Handle empty results
[[ -z "$ip_address" || "$ip_address" == "None" ]] && ip_address="No recent usage found"



[[ "$last_used" == "None" || -z "$last_used" ]] && last_used="Never Used"
        last_service="${last_service:-N/A}"
        last_region="${last_region:-N/A}"
        ip_address="${ip_address:-Unknown}"

        echo "$user,$key,$key_status,$last_used,$last_service,$last_region,$ip_address" >> "$CSV_FILE"

        log_message "✅ User: $user | Key: $key | Status: $key_status | Last Used: $last_used | Service: $last_service | IP: $ip_address"
    done <<< "$keys"
}

# Export function so xargs can use it
export -f fetch_user_data
export -f log_message

# Run user processing in parallel (using bash -c to call the function)
echo "$users" | while read -r user; do
    fetch_user_data "$user"
done

# Generate HTML Report
log_message "Generating HTML report..."
active_count=$(grep -c "Active" "$CSV_FILE" || echo 0)
inactive_count=$(grep -c "Inactive" "$CSV_FILE" || echo 0)
never_used_count=$(awk -F, '$4 ~ /Never Used|None/' "$CSV_FILE" | wc -l)
total_keys=$((active_count + inactive_count))

echo "<html><head><title>AWS Access Key Report</title>
<style>
body { font-family: Arial, sans-serif; }
table { width: 100%; border-collapse: collapse; margin-top: 20px; }
th, td { border: 1px solid black; padding: 10px; text-align: left; }
th { background-color: #4CAF50; color: white; }
.inactive { background-color: #ffcccc; }
.never-used { background-color: #ffdd99; }
</style>
</head><body>
<h2>AWS Access Key Report</h2>
<p>Total Keys: $total_keys | Active: $active_count | Inactive: $inactive_count | Never Used: $never_used_count</p>
<table>
<tr><th>IAM User</th><th>Access Key ID</th><th>Status</th><th>Last Used Date</th><th>Service Used</th><th>Region</th><th>IP Address</th></tr>" > "$HTML_FILE"

tail -n +2 "$CSV_FILE" | while IFS=, read -r user key status last_used service region ip
do
    class=""
    [[ "$status" == "Inactive" ]] && class="inactive"
    [[ "$last_used" == "Never Used" ]] && class="never-used"

    echo "<tr class=\"$class\"><td>$user</td><td>$key</td><td>$status</td><td>$last_used</td><td>$service</td><td>$region</td><td>$ip</td></tr>" >> "$HTML_FILE"
done

echo "</table></body></html>" >> "$HTML_FILE"

log_message "✅ AWS Access Key Audit Completed. Report saved to $HTML_FILE"
echo "✅ AWS Access Key Audit Completed. Report saved to $HTML_FILE"

# Run the Script
# bash ./access_key_usage.sh -s "2025-01-25T12:23:00Z" -e "2025-02-03T12:12:00Z"
# bash ./access_key_usage.sh -k key_name -s "2025-01-25T12:23:00Z" -e "2025-02-03T12:12:00Z"
# bash ./access_key_usage.sh 
