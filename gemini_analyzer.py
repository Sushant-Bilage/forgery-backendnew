import os
import json
import re
import time
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# ─────────────────────────────────────────────
# PROMPT
# ─────────────────────────────────────────────
PROMPT = """
You are a document analysis expert. Analyze the provided document image carefully.

Extract the following information and return ONLY a valid JSON object — no markdown, no explanation, no code fences.

Required JSON schema:
{
  "doc_type": "pan|aadhaar|marks|unknown",
  "name": "",
  "father_name": "",
  "id_number": "",
  "dob": "DD/MM/YYYY",
  "subjects": [],
  "marks": [],
  "total": 0,
  "confidence": 0,
  "issues": []
}

Rules:
- doc_type must be one of: pan, aadhaar, marks, unknown
- PAN: 10 characters uppercase (ABCDE1234F), remove spaces
- Aadhaar: 12 digits, remove spaces/hyphens
- Marks card: subjects list + marks list aligned
- dob format: DD/MM/YYYY
- confidence: 0–100 estimate of authenticity
- DO NOT hallucinate
- If unsure, leave empty and add issue
- Return ONLY JSON
"""

# ─────────────────────────────────────────────
# IMAGE ENCODING (FIXED: RAW BYTES)
# ─────────────────────────────────────────────
def _encode_image(image_path: str):
    path = Path(image_path)
    ext = path.suffix.lower()

    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".bmp": "image/bmp",
        ".webp": "image/webp",
    }

    mime = mime_map.get(ext, "image/jpeg")

    with open(image_path, "rb") as f:
        data = f.read()  # ✅ RAW BYTES (FIXED)

    return data, mime


# ─────────────────────────────────────────────
# SAFE JSON CLEANING (FIXED)
# ─────────────────────────────────────────────
def _clean_json(raw: str) -> str:
    raw = raw.strip()

    # Remove markdown fences safely
    raw = re.sub(r"```.*?\n", "", raw, flags=re.DOTALL)
    raw = raw.replace("```", "")

    # Extract first JSON object safely
    start = raw.find("{")
    end = raw.rfind("}")

    if start != -1 and end != -1:
        return raw[start:end+1]

    return raw


# ─────────────────────────────────────────────
# MAIN FUNCTION
# ─────────────────────────────────────────────
def analyze_with_gemini(image_path: str) -> dict:

    default = {
        "doc_type": "unknown",
        "name": "",
        "father_name": "",
        "id_number": "",
        "dob": "",
        "subjects": [],
        "marks": [],
        "total": 0,
        "confidence": 0,
        "issues": ["Gemini analysis unavailable"],
    }

    if not GEMINI_API_KEY:
        default["issues"] = ["GEMINI_API_KEY missing in .env"]
        return default

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=GEMINI_API_KEY)

        img_data, mime_type = _encode_image(image_path)

        model_name = "gemini-2.0-flash"  # ✅ FIXED MODEL

        # 🔁 Retry logic
        response = None
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[
                        types.Content(
                            role="user",
                            parts=[
                                types.Part(
                                    inline_data=types.Blob(
                                        mime_type=mime_type,
                                        data=img_data
                                    )
                                ),
                                types.Part(text=PROMPT)
                            ],
                        )
                    ],
                )
                break
            except Exception as e:
                if attempt == 1:
                    raise e
                time.sleep(1)

        raw_text = response.text or ""
        cleaned = _clean_json(raw_text)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            default["issues"] = [f"JSON parse error: {cleaned[:200]}"]
            return default

        # ─────────────────────────────
        # SAFE STRUCTURE
        # ─────────────────────────────
        result = {
            "doc_type": str(data.get("doc_type", "unknown")).lower().strip(),
            "name": str(data.get("name", "") or ""),
            "father_name": str(data.get("father_name", "") or ""),
            "id_number": str(data.get("id_number", "") or "").strip(),
            "dob": str(data.get("dob", "") or ""),
            "subjects": data.get("subjects", []) if isinstance(data.get("subjects"), list) else [],
            "marks": data.get("marks", []) if isinstance(data.get("marks"), list) else [],
            "total": int(data.get("total", 0) or 0),
            "confidence": max(0, min(100, int(data.get("confidence", 0) or 0))),
            "issues": data.get("issues", []) if isinstance(data.get("issues"), list) else [],
        }

        # ─────────────────────────────
        # NORMALIZATION (IMPORTANT)
        # ─────────────────────────────

        # PAN normalize
        if result["doc_type"] == "pan":
            result["id_number"] = result["id_number"].replace(" ", "").upper()

        # Aadhaar normalize
        if result["doc_type"] == "aadhaar":
            result["id_number"] = re.sub(r"\D", "", result["id_number"])

        # Boost confidence if strong fields exist
        if result["id_number"] and result["name"]:
            result["confidence"] = max(result["confidence"], 60)

        # Validate doc_type
        if result["doc_type"] not in ("pan", "aadhaar", "marks", "unknown"):
            result["doc_type"] = "unknown"

        return result

    except Exception as e:
        default["issues"] = [f"Gemini API error: {str(e)}"]
        return default