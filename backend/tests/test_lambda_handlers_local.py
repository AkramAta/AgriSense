"""
AgriSense - Backend Unit & Moto Integration Test Suite
Offline testing of S3, SQS, DynamoDB, TFLite inference, and Gemini chat handlers.
"""

import io
import json
import os
import sys
from decimal import Decimal
import boto3
import pytest
from moto import mock_aws
from PIL import Image

# Ensure handlers and common layer are on Python path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
COMMON_LAYER_DIR = os.path.join(BACKEND_DIR, "common_layer", "python")
HANDLERS_DIR = os.path.join(BACKEND_DIR, "handlers")

for path in [BACKEND_DIR, COMMON_LAYER_DIR, HANDLERS_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)

import agrisense_common
from handlers import chat_handler, inference_handler, results_handler, upload_handler

TEST_REGION = "us-east-1"
TEST_BUCKET = "test-agrisense-images"
TEST_QUEUE = "test-agrisense-queue"
TEST_TABLE = "test-agrisense-diagnoses"


@pytest.fixture(autouse=True)
def aws_env(monkeypatch):
    """Set AWS test environment variables."""
    monkeypatch.setenv("AWS_DEFAULT_REGION", TEST_REGION)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("BUCKET_NAME", TEST_BUCKET)
    monkeypatch.setenv("TABLE_NAME", TEST_TABLE)
    monkeypatch.setenv("GEMINI_API_KEY", "")

    # Point to the quantized TFLite model generated in Phase 2
    model_path = os.path.abspath(os.path.join(BACKEND_DIR, "..", "ml", "models", "model_quant_int8.tflite"))
    monkeypatch.setenv("MODEL_PATH", model_path)


@pytest.fixture
def setup_aws_resources():
    """Create mock S3, SQS, and DynamoDB resources."""
    with mock_aws():
        s3 = boto3.client("s3", region_name=TEST_REGION)
        s3.create_bucket(Bucket=TEST_BUCKET)

        sqs = boto3.client("sqs", region_name=TEST_REGION)
        queue_res = sqs.create_queue(QueueName=TEST_QUEUE)
        queue_url = queue_res["QueueUrl"]
        os.environ["QUEUE_URL"] = queue_url

        dynamodb = boto3.resource("dynamodb", region_name=TEST_REGION)
        dynamodb.create_table(
            TableName=TEST_TABLE,
            KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "job_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        yield {"s3": s3, "sqs": sqs, "queue_url": queue_url, "dynamodb": dynamodb}


def create_test_leaf_jpeg() -> bytes:
    """Generate in-memory RGB JPEG image simulating a tomato leaf."""
    img = Image.new("RGB", (96, 96), color=(45, 120, 35))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_upload_handler_creates_presigned_url_and_sqs_message(setup_aws_resources):
    event = {
        "httpMethod": "POST",
        "body": json.dumps({"filename": "tomato_leaf.jpg", "content_type": "image/jpeg"}),
    }

    res = upload_handler.lambda_handler(event, None)
    assert res["statusCode"] == 200

    body = json.loads(res["body"])
    assert "job_id" in body
    assert "upload_url" in body
    assert body["s3_bucket"] == TEST_BUCKET
    assert body["status"] == "PENDING"
    assert "tomato_leaf.jpg" in body["s3_key"]

    # Verify SQS received the job message
    sqs = setup_aws_resources["sqs"]
    queue_url = setup_aws_resources["queue_url"]
    sqs_messages = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1)
    messages = sqs_messages.get("Messages", [])
    assert len(messages) == 1
    msg_body = json.loads(messages[0]["Body"])
    assert msg_body["job_id"] == body["job_id"]

    # Verify DynamoDB has PENDING item
    table = setup_aws_resources["dynamodb"].Table(TEST_TABLE)
    db_item = table.get_item(Key={"job_id": body["job_id"]}).get("Item")
    assert db_item is not None
    assert db_item["status"] == "PENDING"


def test_inference_handler_runs_tflite_and_updates_dynamodb(setup_aws_resources):
    job_id = "test-job-inference-456"
    s3_key = f"uploads/{job_id}/leaf.jpg"
    image_bytes = create_test_leaf_jpeg()

    # 1. Put image in S3
    setup_aws_resources["s3"].put_object(
        Bucket=TEST_BUCKET,
        Key=s3_key,
        Body=image_bytes,
        ContentType="image/jpeg",
    )

    # 2. Put initial PENDING item in DynamoDB
    table = setup_aws_resources["dynamodb"].Table(TEST_TABLE)
    table.put_item(Item={"job_id": job_id, "status": "PENDING"})

    # 3. Trigger inference handler via SQS event
    sqs_event = {
        "Records": [
            {
                "body": json.dumps({
                    "job_id": job_id,
                    "s3_bucket": TEST_BUCKET,
                    "s3_key": s3_key,
                })
            }
        ]
    }

    res = inference_handler.lambda_handler(sqs_event, None)
    assert res["statusCode"] == 200
    assert res["processed_count"] == 1
    assert len(res["errors"]) == 0

    # 4. Check DynamoDB record was updated to COMPLETED
    updated_item = table.get_item(Key={"job_id": job_id}).get("Item")
    assert updated_item is not None
    assert updated_item["status"] == "COMPLETED"
    assert updated_item["class_name"] in agrisense_common.TOMATO_CLASSES
    assert isinstance(updated_item["confidence"], Decimal)
    assert float(updated_item["confidence"]) >= 0.0
    assert "treatment" in updated_item
    assert "disease_name" in updated_item["treatment"]


def test_results_handler_success_and_404(setup_aws_resources):
    table = setup_aws_resources["dynamodb"].Table(TEST_TABLE)
    job_id = "job-results-789"
    table.put_item(Item={
        "job_id": job_id,
        "status": "COMPLETED",
        "class_name": "Tomato___Early_blight",
        "confidence": Decimal("0.9450"),
        "is_healthy": False,
        "treatment": {
            "disease_name": "Early Blight",
            "chemical_control": "Apply Chlorothalonil",
        },
    })

    # Test GET existing
    event = {
        "httpMethod": "GET",
        "pathParameters": {"job_id": job_id},
    }
    res = results_handler.lambda_handler(event, None)
    assert res["statusCode"] == 200
    body = json.loads(res["body"])
    assert body["job_id"] == job_id
    assert body["class_name"] == "Tomato___Early_blight"
    assert body["confidence"] == 0.945

    # Test GET 404 non-existent
    event_404 = {
        "httpMethod": "GET",
        "pathParameters": {"job_id": "non-existent-id"},
    }
    res_404 = results_handler.lambda_handler(event_404, None)
    assert res_404["statusCode"] == 404


def test_chat_handler_expert_fallback():
    event = {
        "httpMethod": "POST",
        "body": json.dumps({
            "prompt": "How do I control fungal blight and what irrigation schedule is best?",
            "diagnosis_context": {
                "class_name": "Tomato___Early_blight",
                "confidence": 0.92,
            },
        }),
    }

    res = chat_handler.lambda_handler(event, None)
    assert res["statusCode"] == 200
    body = json.loads(res["body"])
    assert "reply" in body
    assert "Early Blight" in body["reply"]
    assert "Irrigation" in body["reply"]


def test_end_to_end_serverless_pipeline(setup_aws_resources):
    """Verifies complete client upload -> async SQS -> TFLite -> DB -> Results flow."""
    # Step 1: Client calls presign endpoint
    upload_event = {
        "httpMethod": "POST",
        "body": json.dumps({"filename": "infected_leaf.jpg", "content_type": "image/jpeg"}),
    }
    upload_res = upload_handler.lambda_handler(upload_event, None)
    assert upload_res["statusCode"] == 200
    upload_data = json.loads(upload_res["body"])
    job_id = upload_data["job_id"]
    s3_key = upload_data["s3_key"]

    # Step 2: Client uploads image bytes to S3
    setup_aws_resources["s3"].put_object(
        Bucket=TEST_BUCKET,
        Key=s3_key,
        Body=create_test_leaf_jpeg(),
        ContentType="image/jpeg",
    )

    # Step 3: SQS triggers Inference Lambda
    sqs_event = {
        "Records": [
            {
                "body": json.dumps({
                    "job_id": job_id,
                    "s3_bucket": TEST_BUCKET,
                    "s3_key": s3_key,
                })
            }
        ]
    }
    inf_res = inference_handler.lambda_handler(sqs_event, None)
    assert inf_res["statusCode"] == 200
    assert inf_res["processed_count"] == 1

    # Step 4: Client polls Results Endpoint
    results_event = {
        "httpMethod": "GET",
        "pathParameters": {"job_id": job_id},
    }
    results_res = results_handler.lambda_handler(results_event, None)
    assert results_res["statusCode"] == 200
    results_data = json.loads(results_res["body"])
    assert results_data["job_id"] == job_id
    assert results_data["status"] == "COMPLETED"
    assert results_data["class_name"] in agrisense_common.TOMATO_CLASSES
    assert results_data["confidence"] > 0.0

    # Step 5: Client requests chat advice with diagnosis context
    chat_event = {
        "httpMethod": "POST",
        "body": json.dumps({
            "prompt": "What fungicides and irrigation safeguards should I apply?",
            "diagnosis_context": results_data,
        }),
    }
    chat_res = chat_handler.lambda_handler(chat_event, None)
    assert chat_res["statusCode"] == 200
    chat_data = json.loads(chat_res["body"])
    assert "reply" in chat_data
    assert len(chat_data["reply"]) > 50
