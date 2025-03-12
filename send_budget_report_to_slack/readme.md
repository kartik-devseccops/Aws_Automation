Steps to Configure a CloudWatch Event Rule to Trigger AWS Lambda for Budget Reports
This guide will walk you through setting up a scheduled trigger for your AWS Lambda function using Amazon EventBridge (CloudWatch Events).

Step 1: Go to AWS Lambda Console
Sign in to the AWS Management Console.
In the search bar, type Lambda and select it.
From the Functions list, select your Lambda function (e.g., SendBudgetReportToSlack).
Step 2: Add a Trigger
Scroll down to the Function Overview section.
Click on the + Add trigger button.
In the Trigger Configuration dropdown, select EventBridge (CloudWatch Events).
Click Create a new rule (recommended for first-time setup).
Step 3: Configure the EventBridge Rule
Rule Name:
Enter a meaningful name like: Daily-Budget-Report-Trigger.
Rule Description:
Provide an optional description, e.g., "Triggers daily budget report at 9 AM"
Rule Type:
Select Schedule expression.
Step 4: Define the Schedule
In the Schedule expression field, use one of the following:
✅ For Daily Trigger at 9 AM (UTC):

cron(0 4 * * ? *)
✅ For Hourly Trigger:

rate(1 hour)
✅ For Every 30 Minutes:

rate(30 minutes)
✅ For Every Weekday at 5 PM (UTC):

cron(0 17 ? * MON-FRI *)
⏰ Note: CloudWatch cron expressions use UTC time, so adjust accordingly for your preferred timezone.

Step 5: Add Permissions
✅ AWS will automatically configure the necessary permissions for your Lambda function to be invoked by Amazon EventBridge (CloudWatch Events).

Step 6: Review and Create
Click Add to attach the trigger to your Lambda function.
In the EventBridge Rule setup page, click Create.