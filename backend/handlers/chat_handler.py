"""
AgriSense - Gemini Plant-Care Chat Handler
Provides intelligent agronomic advice for plant health and irrigation management.
Proxies to Google Gemini API when an API key is configured, and provides an offline
expert agronomy engine fallback for self-contained operation.
"""

import datetime
import json
import os
import sys
import urllib.request
import urllib.error

try:
    from agrisense_common import (
        TREATMENT_RECOMMENDATIONS,
        format_error,
        format_response,
    )
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), "../common_layer/python"))
    from agrisense_common import (
        TREATMENT_RECOMMENDATIONS,
        format_error,
        format_response,
    )


def generate_expert_agronomic_fallback(prompt: str, diagnosis_context: dict) -> str:
    """Intelligent rule-based expert agronomy response for offline / test environments."""
    p_lower = prompt.lower()
    class_name = diagnosis_context.get("class_name", "")

    treatment = TREATMENT_RECOMMENDATIONS.get(class_name, None)

    # 1. Direct inquiry about a detected disease
    if treatment:
        return (
            f"Based on your diagnosis for **{treatment['disease_name']}** (Severity: {treatment['severity']}):\n\n"
            f"- **Symptoms:** {treatment['symptoms']}\n"
            f"- **Immediate Chemical Action:** {treatment['chemical_control']}\n"
            f"- **Organic / Bio-control:** {treatment['organic_control']}\n"
            f"- **Cultural Practices:** {treatment['cultural_practices']}\n\n"
            f"**Irrigation Guidance:** Maintain strict drip irrigation. Wetting the tomato canopy exacerbates fungal sporulation. "
            f"Keep soil volumetric moisture between 40% and 60%."
        )

    # 2. General irrigation inquiries
    if any(k in p_lower for k in ["water", "irrigation", "moisture", "pump", "wet", "dry"]):
        return (
            "**AgriSense Precision Irrigation Advice:**\n"
            "- **Optimal Moisture Band:** Tomato plants flourish in a soil moisture range of 40% to 65%.\n"
            "- **Auto-Cutoff Safeguards:** Never exceed 15-20 minutes of continuous pumping per cycle to prevent root hypoxia (suffocation) and blossom end rot.\n"
            "- **Timing:** Schedule irrigation during early morning hours to allow any unintended surface moisture to evaporate quickly in the sun."
        )

    # 3. Yellowing / wilting / spots
    if any(k in p_lower for k in ["yellow", "wilt", "spot", "blight", "curl", "fungus", "mite"]):
        return (
            "**Foliar Symptom Assessment:**\n"
            "- Yellowing leaves on lower branches often signal early blight or excessive root moisture.\n"
            "- For small brown spots with halos, consider applying a preventive copper fungicide and pruning infected leaves.\n"
            "- If fine webbing is visible, inspect leaf undersides for two-spotted spider mites and apply insecticidal soap."
        )

    # 4. General Tomato Care
    return (
        "**AgriSense Tomato Management Assistant:**\n"
        "To maximize yield and plant vigor:\n"
        "1. Prune suckers and ground-touching foliage to improve airflow.\n"
        "2. Ensure consistent calcium uptake through regulated watering to prevent blossom end rot.\n"
        "3. Use the AgriSense Disease Scanner whenever you notice unusual lesions or discoloration on leaves."
    )


def lambda_handler(event, context):
    http_method = event.get("httpMethod", "")
    if http_method == "OPTIONS":
        return format_response(204, {})

    body = {}
    if "body" in event and event["body"]:
        try:
            body = json.loads(event["body"]) if isinstance(event["body"], str) else event["body"]
        except json.JSONDecodeError:
            return format_error(400, "Invalid JSON payload in request body")

    prompt = body.get("prompt", "").strip()
    if not prompt:
        return format_error(400, "Missing required field: 'prompt'")

    diagnosis_context = body.get("diagnosis_context", {})
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()

    # If Gemini API key is available, call the Gemini REST API
    if api_key:
        try:
            gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            system_prompt = (
                "You are AgriSense AI, an elite precision agriculture and plant pathology assistant. "
                "Provide concise, actionable agronomic advice for tomato crop health, irrigation management, "
                "and disease remediation. Format your answer with clear markdown bullet points."
            )
            context_str = f"\nActive Diagnosis Context: {json.dumps(diagnosis_context)}" if diagnosis_context else ""
            user_text = f"{prompt}{context_str}"

            req_payload = {
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"parts": [{"text": user_text}]}],
                "generationConfig": {"temperature": 0.4, "maxOutputTokens": 600},
            }

            req = urllib.request.Request(
                gemini_url,
                data=json.dumps(req_payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                reply_text = res_data["candidates"][0]["content"]["parts"][0]["text"]
                return format_response(200, {
                    "reply": reply_text,
                    "model": "gemini-1.5-flash",
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                })
        except Exception as e:
            # Fall back to internal agronomic engine if network or auth fails
            pass

    # Expert agronomic fallback
    fallback_reply = generate_expert_agronomic_fallback(prompt, diagnosis_context)
    return format_response(200, {
        "reply": fallback_reply,
        "model": "agrisense-expert-rules-v1",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    })

