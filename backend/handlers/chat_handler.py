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
    """Intelligent dynamic expert agronomy response for offline / edge environments."""
    p_lower = prompt.lower().strip()
    class_name = diagnosis_context.get("class_name", "")
    treatment = TREATMENT_RECOMMENDATIONS.get(class_name, None)

    # 1. Step-by-Step Action Plan ("steps", "how to", "plan", "procedure", "guide")
    if any(k in p_lower for k in ["step", "how to", "plan", "procedure", "guide", "protocol", "stage", "walkthrough"]):
        if treatment:
            return (
                f"**5-Stage Action Plan for {treatment['disease_name']} Control:**\n\n"
                f"1. **Sanitize & Prune:** Remove all lower leaves exhibiting necrotic spots or halos using shears disinfected in 10% bleach.\n"
                f"2. **Targeted Spray:** Apply {treatment['chemical_control']} early in the morning for maximum foliar uptake.\n"
                f"3. **Canopy Aeration:** {treatment['cultural_practices']}\n"
                f"4. **Irrigation Guard:** Switch strictly to drip irrigation. Maintain root-zone moisture between 45% and 60%.\n"
                f"5. **Scout & Rotate:** Inspect new leaf clusters in 7 days; rotate fungicide FRAC groups if infection persists."
            )
        else:
            return (
                "**5-Step General Tomato Health Protocol:**\n\n"
                "1. **Scouting:** Inspect foliage undersides for lesions, yellowing, or webbing.\n"
                "2. **Pruning:** Prune ground-touching suckers to eliminate splash transmission.\n"
                "3. **Moisture Control:** Maintain 45%-65% soil moisture with root drip lines.\n"
                "4. **Protective Spray:** Apply copper-based or bio-fungicide at first sign of disease.\n"
                "5. **Mulching:** Apply straw mulch to insulate roots and prevent soil splash."
            )

    # 2. Alternative & Organic Remedies ("another", "alternative", "organic", "natural", "bio")
    if any(k in p_lower for k in ["another", "alternative", "organic", "natural", "bio", "what else"]):
        if treatment:
            return (
                f"**Alternative & Biological Solutions for {treatment['disease_name']}:**\n\n"
                f"- **Organic / Bio-control:** {treatment['organic_control']}\n"
                f"- **Beneficial Microbes:** Inoculate root zone and foliage with *Bacillus subtilis* to outcompete pathogens.\n"
                f"- **Cultural Measures:** {treatment['cultural_practices']}\n"
                f"- **Soil Hygiene:** Apply clean straw mulch to block soil-borne spore splashback."
            )
        else:
            return (
                "**Alternative Organic Interventions:**\n\n"
                "- Apply OMRI-listed copper octanoate or potassium bicarbonate.\n"
                "- Introduce *Trichoderma* or mycorrhizal inoculants to enhance systemic acquired resistance (SAR).\n"
                "- Intercrop with marigolds and basil to repel insect disease vectors."
            )

    # 3. Specialist Agronomic Consultation & Help Requests
    if any(k in p_lower for k in ["help", "assist", "problem", "solve", "fix", "advice", "what to do"]):
        if treatment:
            return (
                f"**Specialist Clinical Consultation: {treatment['disease_name']} (Severity: {treatment['severity']})**\n\n"
                f"**Pathological Assessment:**\n"
                f"• **Foliar Expression:** {treatment['symptoms']}\n\n"
                f"**Clinical Prescription & Immediate Action:**\n"
                f"1. **Therapeutic / Chemical Intervention:** {treatment['chemical_control']}\n"
                f"2. **Biological / Organic Alternative:** {treatment['organic_control']}\n"
                f"3. **Canopy Aeration & Sanitation:** {treatment['cultural_practices']}\n"
                f"4. **Irrigation Directive:** Maintain root-zone drip irrigation (40%-60% soil moisture). Never wet the canopy."
            )

    # 4. Irrigation Inquiries
    if any(k in p_lower for k in ["water", "irrigation", "moisture", "pump", "wet", "dry", "schedule"]):
        disease_note = f" (Crucial for {treatment['disease_name']} management)" if treatment else ""
        return (
            f"**AgriSense Precision Irrigation Advice{disease_note}:**\n\n"
            "- **Optimal Moisture Band:** Tomato plants flourish in a soil moisture range of 40% to 65%.\n"
            "- **Strict Drip Delivery:** Wetting foliage spreads fungal spores and bacteria. Deliver water exclusively via root-zone drip lines.\n"
            "- **Auto-Cutoff Safeguards:** Never exceed 15-20 minutes of continuous pumping per cycle to prevent root hypoxia.\n"
            "- **Timing:** Schedule irrigation during early morning hours so any accidental surface moisture evaporates in the sun."
        )

    # 5. Chemical / Spray / Dosage Inquiries
    if any(k in p_lower for k in ["spray", "chemical", "fungicide", "bactericide", "copper", "dose", "dosage", "interval"]):
        if treatment:
            return (
                f"**Foliar Spray Protocol for {treatment['disease_name']}:**\n\n"
                f"- **Recommended Agent:** {treatment['chemical_control']}\n"
                f"- **Application Timing:** Spray early morning (6:00-9:00 AM) or late afternoon with temps < 28°C and calm wind.\n"
                f"- **Frequency:** Re-apply every 7-10 days under humid conditions; extend to 14 days under dry sunny weather.\n"
                f"- **Coverage:** Ensure full canopy penetration covering both upper and lower leaf surfaces."
            )

    # 6. Yellowing / wilting / spots / symptoms
    if any(k in p_lower for k in ["yellow", "wilt", "spot", "blight", "curl", "fungus", "mite", "symptom"]):
        if treatment:
            return (
                f"**Pathological Profile: {treatment['disease_name']} (Severity: {treatment['severity']}):**\n\n"
                f"- **Symptom Expression:** {treatment['symptoms']}\n"
                f"- **Primary Control:** {treatment['chemical_control']}\n"
                f"- **Cultural Prevention:** {treatment['cultural_practices']}"
            )
        else:
            return (
                "**Foliar Symptom Assessment:**\n\n"
                "- Yellowing lower leaves typically signal early blight or excessive root moisture.\n"
                "- Small dark brown spots with chlorotic rings indicate fungal leaf spots (Septoria or Alternaria).\n"
                "- Stippling with fine webs indicates two-spotted spider mites; apply insecticidal soap."
            )

    # 7. General Diagnosis Remediation (Active Treatment context present)
    if treatment:
        return (
            f"Based on your diagnosis for **{treatment['disease_name']}** (Severity: {treatment['severity']}):\n\n"
            f"- **Symptoms:** {treatment['symptoms']}\n"
            f"- **Immediate Chemical Action:** {treatment['chemical_control']}\n"
            f"- **Organic / Bio-control:** {treatment['organic_control']}\n"
            f"- **Cultural Practices:** {treatment['cultural_practices']}\n\n"
            f"**Irrigation Guidance:** Maintain strict root-zone drip irrigation. "
            f"Keep soil moisture between 40% and 60%."
        )

    # 8. General Tomato Management Assistant
    return (
        "**AgriSense Tomato Management Assistant:**\n\n"
        "To maximize yield and plant vigor:\n"
        "1. Prune suckers and ground-touching foliage to improve airflow.\n"
        "2. Ensure consistent moisture (45%-65%) through regulated drip watering to prevent blossom end rot.\n"
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
    api_key = os.environ.get(
        "GEMINI_API_KEY",
        "AQ.Ab8RN6LoqoH-xrWThPBJeKaTjPYgfEjjCa4Rhnhf_5KIpYG2BA"
    ).strip()

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

