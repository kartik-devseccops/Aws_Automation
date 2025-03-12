import boto3
import csv

def create_s3_metrics_filter(s3_client, bucket_name, filter_id):
    try:
        # Create metrics configuration for the bucket
        s3_client.put_bucket_metrics_configuration(
            Bucket=bucket_name,
            Id=filter_id,
            MetricsConfiguration={
                'Id': filter_id,
                'Filter': {'Prefix': ''}  # Apply to all objects
            }
        )
        return 'Success'
    except Exception as e:
        return f'Failed - {str(e)}'

def main():
    s3 = boto3.client('s3')
    buckets = s3.list_buckets()['Buckets']
    filter_id = 'CommonFilterID'
    results = []

    for bucket in buckets:
        bucket_name = bucket['Name']
        print(f'Creating metrics filter {filter_id} for bucket: {bucket_name}')
        status = create_s3_metrics_filter(s3, bucket_name, filter_id)
        results.append((bucket_name, filter_id, status))

    with open('s3_metrics_filter_results.csv', 'w') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Bucket Name', 'Filter ID', 'Status'])
        writer.writerows(results)

    print('CSV file generated: s3_metrics_filter_results.csv')

if __name__ == "__main__":
    main()
