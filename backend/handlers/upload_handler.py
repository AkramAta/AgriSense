"""
AgriSense - Upload Handler Lambda Function
Generates S3 presigned PUT URLs for client image uploads,
enqueues pending inference jobs to SQS, and creates an audit record in DynamoDB.
"""

import datetime
import json
import os
import sys
import uuid
import boto3

# Support both Lambda layer path (/opt/python) and local test environment
try:
    from agrisense_common import decimalize_floats, format_error, format_response
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), "../common_layer/python"))
    from agrisense_common import decimalize_floats, format_error, format_response


def get_s3_client():
    return boto3.client("s3")


def get_sqs_client():
    return boto3.client("sqs")


def get_dynamodb_resource():
    return boto3.resource("dynamodb")


def lambda_handler(event, context):
    # Handle CORS OPTIONS preflight
    http_method = event.get("httpMethod", "")
    if http_method == "OPTIONS":
        return format_response(204, {})

    bucket_name = os.environ.get("BUCKET_NAME", "agrisense-plant-images")
    queue_url = os.environ.get("QUEUE_URL", "")
    table_name = os.environ.get("TABLE_NAME", "agrisense-diagnoses")

    # Parse body
    body = {}
    if "body" in event and event["body"]:
        try:
            body = json.loads(event["body"]) if isinstance(event["body"], str) else event["body"]
        except json.JSONDecodeError:
            return format_error(400, "Invalid JSON payload in request body")

    filename = body.get("filename", "leaf.jpg")
    content_type = body.get("content_type", "image/jpeg")

    # Generate unique diagnostic job ID
    job_id = str(uuid.uuid4())
    s3_key = f"uploads/{job_id}/{filename}"
    timestamp_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    s3_client = get_s3_client()
    sqs_client = get_sqs_client()
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(table_name)

    try:
        # 1. Generate S3 Presigned URL (15 minute validity)
        presigned_url = s3_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": bucket_name,
                "Key": s3_key,
                "ContentType": content_type,
            },
            ExpiresIn=900,
        )

        # 2. Record initial PENDING state in DynamoDB
        pending_item = {
            "job_id": job_id,
            "status": "PENDING",
            "created_at": timestamp_iso,
            "s3_bucket": bucket_name,
            "s3_key": s3_key,
            "filename": filename,
            "content_type": content_type,
        }
        table.put_item(Item=decimalize_floats(pending_item))

        # 3. Push job metadata to SQS for asynchronous processing
        if queue_url:
            message_payload = {
                "job_id": job_id,
                "s3_bucket": bucket_name,
                "s3_key": s3_key,
                "created_at": timestamp_iso,
            }
            sqs_client.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(message_payload),
            )

        response_payload = {
            "job_id": job_id,
            "upload_url": presigned_url,
            "s3_bucket": bucket_name,
            "s3_key": s3_key,
            "status": "PENDING",
            "expires_in_seconds": 900,
        }
        return format_response(200, response_payload)

    except Exception as e:
        return format_error(500, f"Failed to initialize diagnostic upload: {str(e)}")
