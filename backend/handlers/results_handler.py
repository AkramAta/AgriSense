"""
AgriSense - Results Handler Lambda Function
Fetches diagnostic results and status by job_id from DynamoDB.
"""

import os
import sys
import boto3

try:
    from agrisense_common import floatify_decimals, format_error, format_response
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), "../common_layer/python"))
    from agrisense_common import floatify_decimals, format_error, format_response


def get_dynamodb_resource():
    return boto3.resource("dynamodb")


def lambda_handler(event, context):
    http_method = event.get("httpMethod", "")
    if http_method == "OPTIONS":
        return format_response(204, {})

    table_name = os.environ.get("TABLE_NAME", "agrisense-diagnoses")
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(table_name)

    # Extract job_id from pathParameters or queryStringParameters
    job_id = None
    if "pathParameters" in event and event["pathParameters"]:
        job_id = event["pathParameters"].get("job_id")
    if not job_id and "queryStringParameters" in event and event["queryStringParameters"]:
        job_id = event["queryStringParameters"].get("job_id")

    if not job_id:
        return format_error(400, "Missing required parameter: job_id")

    try:
        response = table.get_item(Key={"job_id": job_id})
        item = response.get("Item")

        if not item:
            return format_error(404, f"Diagnosis job not found for job_id: {job_id}")

        cleaned_item = floatify_decimals(item)
        return format_response(200, cleaned_item)

    except Exception as e:
        return format_error(500, f"Failed to retrieve diagnosis: {str(e)}")
