import boto3
import csv
from botocore.exceptions import NoCredentialsError

# Initialize S3 client
s3 = boto3.client('s3')

# Function to get filter IDs for a bucket
def get_filter_ids(bucket_name):
    try:
        response = s3.list_bucket_metrics_configurations(Bucket=bucket_name)
        metrics = response.get('MetricsConfigurationList', [])
        return [(bucket_name, metric['Id']) for metric in metrics]
    except Exception as e: 
        print(f"Error fetching metrics for {bucket_name}: {e}")
        return []

# Get list of all buckets
try:
    buckets = s3.list_buckets()['Buckets']
except NoCredentialsError:
    print("Credentials not available.")
    exit()

# Fetch filter IDs for all buckets
all_metrics = []
for bucket in buckets:
    all_metrics.extend(get_filter_ids(bucket['Name']))

# Write to CSV
csv_file = 's3_metrics_filter_ids.csv'
with open(csv_file, 'w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(['Bucket Name', 'Filter ID'])
    writer.writerows(all_metrics)

print(f"CSV file created: {csv_file}")

# Write to HTML
html_file = 's3_metrics_filter_ids.html'
with open(html_file, 'w') as file:
    file.write('<html><body><h2>S3 Metrics Filter IDs</h2><table border="1"><tr><th>Bucket Name</th><th>Filter ID</th></tr>')
    for bucket_name, filter_id in all_metrics:
        file.write(f'<tr><td>{bucket_name}</td><td>{filter_id}</td></tr>')
    file.write('</table></body></html>')

print(f"HTML file created: {html_file}")
