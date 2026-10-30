"""
AgriSense - Inference Handler Lambda Function
Triggered by SQS. Fetches leaf image from S3, executes INT8 TFLite inference via ai-edge-litert,
enriches diagnosis with treatment recommendations, and records completion in DynamoDB.
"""

import datetime
import io
import json
import os
import sys
from decimal import Decimal
import boto3
import numpy as np
from PIL import Image

try:
    from agrisense_common import (
        TOMATO_CLASSES,
        TREATMENT_RECOMMENDATIONS,
        decimalize_floats,
    )
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), "../common_layer/python"))
    from agrisense_common import (
        TOMATO_CLASSES,
        TREATMENT_RECOMMENDATIONS,
        decimalize_floats,
    )

# Global model cache across warm Lambda invocations
_INTERPRETER = None
_INPUT_DETAILS = None
_OUTPUT_DETAILS = None


def get_s3_client():
    return boto3.client("s3")


def get_dynamodb_resource():
    return boto3.resource("dynamodb")


def load_interpreter():
    global _INTERPRETER, _INPUT_DETAILS, _OUTPUT_DETAILS
    if _INTERPRETER is not None:
        return _INTERPRETER, _INPUT_DETAILS, _OUTPUT_DETAILS

    import ai_edge_litert.interpreter as tflite

    model_candidates = [
        os.environ.get("MODEL_PATH", ""),
        os.path.join(os.path.dirname(__file__), "../../ml/models/model_quant_int8.tflite"),
        os.path.join(os.path.dirname(__file__), "model_quant_int8.tflite"),
        "/opt/model_quant_int8.tflite",
    ]

    model_path = None
    for cand in model_candidates:
        if cand and os.path.exists(cand):
            model_path = cand
            break

    if not model_path:
        raise FileNotFoundError(f"TFLite model not found in candidates: {model_candidates}")

    _INTERPRETER = tflite.Interpreter(model_path=model_path)
    _INTERPRETER.allocate_tensors()
    _INPUT_DETAILS = _INTERPRETER.get_input_details()
    _OUTPUT_DETAILS = _INTERPRETER.get_output_details()
    return _INTERPRETER, _INPUT_DETAILS, _OUTPUT_DETAILS


def preprocess_image_to_int8(image_bytes: bytes, in_scale: float, in_zp: int) -> np.ndarray:
    """Resize image to 96x96 RGB and quantize to INT8."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((96, 96))
    arr = np.array(img, dtype=np.float32) / 255.0
    q = np.round(arr / in_scale) + in_zp
    q = np.clip(q, -128, 127).astype(np.int8)
    return np.expand_dims(q, axis=0)  # Shape: [1, 96, 96, 3]


def run_inference(image_bytes: bytes) -> dict:
    """Executes INT8 inference and returns top prediction with confidence."""
    interpreter, in_details, out_details = load_interpreter()

    in_scale = float(in_details[0]["quantization_parameters"]["scales"][0]) if in_details[0]["quantization_parameters"]["scales"].size > 0 else 1.0 / 255.0
    in_zp = int(in_details[0]["quantization_parameters"]["zero_points"][0]) if in_details[0]["quantization_parameters"]["zero_points"].size > 0 else -128

    input_data = preprocess_image_to_int8(image_bytes, in_scale, in_zp)
    interpreter.set_tensor(in_details[0]["index"], input_data)
    interpreter.invoke()

    output_data = interpreter.get_tensor(out_details[0]["index"])  # Shape: [1, 8]
    raw_logits = output_data[0]

    out_scale = float(out_details[0]["quantization_parameters"]["scales"][0]) if out_details[0]["quantization_parameters"]["scales"].size > 0 else 1.0 / 256.0
    out_zp = int(out_details[0]["quantization_parameters"]["zero_points"][0]) if out_details[0]["quantization_parameters"]["zero_points"].size > 0 else -128

    # Dequantize to probabilities
    probs = [(float(val) - out_zp) * out_scale for val in raw_logits]
    probs = [max(0.0, min(1.0, p)) for p in probs]
    total_p = sum(probs)
    if total_p > 0:
        probs = [p / total_p for p in probs]

    top_idx = int(np.argmax(probs))
    top_conf = float(probs[top_idx])
    class_name = TOMATO_CLASSES[top_idx]
    is_healthy = (top_idx == 7)

    return {
        "class_index": top_idx,
        "class_name": class_name,
        "confidence": top_conf,
        "is_healthy": is_healthy,
        "all_probabilities": {TOMATO_CLASSES[i]: round(probs[i], 4) for i in range(len(TOMATO_CLASSES))},
    }


def lambda_handler(event, context):
    s3_client = get_s3_client()
    dynamodb = get_dynamodb_resource()
    table_name = os.environ.get("TABLE_NAME", "agrisense-diagnoses")
    table = dynamodb.Table(table_name)

    records = event.get("Records", [])
    processed_count = 0
    errors = []

    for record in records:
        try:
            body = json.loads(record["body"]) if isinstance(record["body"], str) else record["body"]
            job_id = body["job_id"]
            s3_bucket = body["s3_bucket"]
            s3_key = body["s3_key"]

            # 1. Download image from S3
            obj = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
            image_bytes = obj["Body"].read()

            # 2. Run TFLite inference
            inference_result = run_inference(image_bytes)
            class_name = inference_result["class_name"]

            # 3. Retrieve agronomic treatments
            treatment = TREATMENT_RECOMMENDATIONS.get(class_name, TREATMENT_RECOMMENDATIONS["Tomato___healthy"])

            # 4. Update DynamoDB using Decimal(str(val)) formatting
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            update_data = {
                "job_id": job_id,
                "status": "COMPLETED",
                "class_index": inference_result["class_index"],
                "class_name": class_name,
                "confidence": Decimal(str(round(inference_result["confidence"], 4))),
                "is_healthy": inference_result["is_healthy"],
                "all_probabilities": inference_result["all_probabilities"],
                "treatment": treatment,
                "processed_at": now_iso,
            }

            table.put_item(Item=decimalize_floats(update_data))
            processed_count += 1

        except Exception as e:
            errors.append(str(e))

    return {
        "statusCode": 200,
        "processed_count": processed_count,
        "errors": errors,
    }
