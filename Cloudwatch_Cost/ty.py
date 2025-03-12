import boto3

client = boto3.client('iam')
response = client.get_access_key_last_used(AccessKeyId='AKIAQUFLQG4236OZRRH3')
print(response)
