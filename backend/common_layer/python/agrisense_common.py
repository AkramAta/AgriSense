"""
AgriSense - Shared Lambda Layer Utility Module
Provides standardized response formatting, Decimal conversion for DynamoDB,
and agronomic disease recommendations.
"""

import json
from decimal import Decimal
from typing import Any, Dict, List, Optional

TOMATO_CLASSES: List[str] = [
    "Tomato___Bacterial_spot",
    "Tomato___Early_blight",
    "Tomato___Late_blight",
    "Tomato___Leaf_Mold",
    "Tomato___Septoria_leaf_spot",
    "Tomato___Spider_mites_Two_spotted_spider_mite",
    "Tomato___Target_Spot",
    "Tomato___healthy",
]

TREATMENT_RECOMMENDATIONS: Dict[str, Dict[str, Any]] = {
    "Tomato___Bacterial_spot": {
        "disease_name": "Bacterial Spot (Xanthomonas spp.)",
        "severity": "High",
        "symptoms": "Small, water-soaked, dark brown to black circular lesions on leaves and fruit, often with yellow halos.",
        "chemical_control": "Apply fixed copper bactericides combined with Mancozeb to enhance copper solubility and efficacy.",
        "organic_control": "Apply Bacillus subtilis or copper octanoate (copper soap). Avoid overhead irrigation completely.",
        "cultural_practices": "Use certified disease-free seeds; sterilize pruning shears in 10% bleach; rotate with non-solanaceous crops for 2 years.",
    },
    "Tomato___Early_blight": {
        "disease_name": "Early Blight (Alternaria solani)",
        "severity": "Medium-High",
        "symptoms": "Concentric rings resembling a target board with dark brown necrotic tissue, initially on lower older leaves.",
        "chemical_control": "Apply Chlorothalonil, Azoxystrobin, or Difenoconazole fungicides at 7-10 day intervals during humid weather.",
        "organic_control": "Apply copper sulfate or potassium bicarbonate. Mulch soil heavily to prevent soil-to-leaf rain splash.",
        "cultural_practices": "Prune lower foliage 12 inches above soil line; stake and trellis plants for optimal air circulation.",
    },
    "Tomato___Late_blight": {
        "disease_name": "Late Blight (Phytophthora infestans)",
        "severity": "Critical",
        "symptoms": "Large, irregularly shaped, water-soaked oily lesions that rapidly turn dark brown to purplish-black with white sporulation underneath.",
        "chemical_control": "Immediately spray systemic fungicides containing Cymoxanil, Fluopicolide, or Mandipropamid.",
        "organic_control": "Copper hydroxide at first sign of disease. Destroy severely infected plants immediately (do not compost).",
        "cultural_practices": "Avoid planting near potatoes; maintain strict dry-canopy management through drip irrigation.",
    },
    "Tomato___Leaf_Mold": {
        "disease_name": "Leaf Mold (Passalora fulva)",
        "severity": "Medium",
        "symptoms": "Pale greenish-yellow spots on upper leaf surfaces; olive-green to brown velvety mold patches on undersides.",
        "chemical_control": "Apply Copper oxychloride or Chlorothalonil when humidity exceeds 85%.",
        "organic_control": "Improve greenhouse/tunnel ventilation; apply neem oil or sulfur dust.",
        "cultural_practices": "Keep relative humidity below 85%; space plants widely to reduce canopy density.",
    },
    "Tomato___Septoria_leaf_spot": {
        "disease_name": "Septoria Leaf Spot (Septoria lycopersici)",
        "severity": "Medium-High",
        "symptoms": "Numerous small circular spots (1-3mm) with greyish-white centers and distinct dark brown borders with black pycnidia specks.",
        "chemical_control": "Foliar application of Chlorothalonil or Mancozeb every 7-14 days.",
        "organic_control": "Copper-based fungicides. Remove and bag infected lower leaves promptly.",
        "cultural_practices": "Implement a 3-year crop rotation; use drip irrigation; disinfect all tomato cages and stakes.",
    },
    "Tomato___Spider_mites_Two_spotted_spider_mite": {
        "disease_name": "Two-Spotted Spider Mite (Tetranychus urticae)",
        "severity": "High (in hot/dry conditions)",
        "symptoms": "Yellow stippling or bronzing of upper leaf surface, progressing to chlorosis, accompanied by fine silky webbing.",
        "chemical_control": "Rotate miticides with different modes of action (e.g., Bifenazate, Abamectin, or Spiromesifen).",
        "organic_control": "Release predatory mites (Phytoseiulus persimilis); apply insecticidal soap, neem oil, or horticultural oils.",
        "cultural_practices": "Maintain soil moisture to reduce plant water stress; hose down foliage to disrupt webs in small plots.",
    },
    "Tomato___Target_Spot": {
        "disease_name": "Target Spot (Corynespora casiicola)",
        "severity": "Medium",
        "symptoms": "Brown to dark brown lesions with concentric rings, often causing extensive defoliation in humid subtropical climates.",
        "chemical_control": "Apply Pyraclostrobin, Boscalid, or Chlorothalonil.",
        "organic_control": "Bio-fungicides based on Bacillus amyloliquefaciens; copper soaps.",
        "cultural_practices": "Promptly remove crop residue post-harvest; ensure rapid canopy drying through drip irrigation.",
    },
    "Tomato___healthy": {
        "disease_name": "Healthy Tomato Foliage",
        "severity": "None",
        "symptoms": "No visible foliar lesions, chlorosis, stippling, or mycelial growth detected. Vigorous green foliage.",
        "chemical_control": "No chemical intervention required.",
        "organic_control": "Maintain balanced fertility (N-P-K with micronutrients like Calcium and Magnesium).",
        "cultural_practices": "Continue scheduled moisture sensor monitoring; maintain drip irrigation schedule; scout regularly.",
    },
}


def decimalize_floats(obj: Any) -> Any:
    """Recursively converts float values to Decimal(str(val)) for DynamoDB compatibility."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: decimalize_floats(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decimalize_floats(v) for v in obj]
    return obj


def floatify_decimals(obj: Any) -> Any:
    """Recursively converts Decimal values back to float/int for JSON serialization."""
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    elif isinstance(obj, dict):
        return {k: floatify_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [floatify_decimals(v) for v in obj]
    return obj


def format_response(status_code: int, body: Any, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Generates standard API Gateway proxy response with permissive CORS."""
    default_headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    }
    if headers:
        default_headers.update(headers)

    cleaned_body = floatify_decimals(body)
    return {
        "statusCode": status_code,
        "headers": default_headers,
        "body": json.dumps(cleaned_body),
    }


def format_error(status_code: int, message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Standard error response format."""
    payload = {"error": message, "status": "failed"}
    if details:
        payload["details"] = details
    return format_response(status_code, payload)

