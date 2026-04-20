"""
analyze.py — FINAL (STRICT + BLUR + VALIDATION + NEW THRESHOLDS)
"""

import numpy as np
import cv2

from core.gemini.gemini_analyzer import analyze_with_gemini
from core.validation.validators import run_validation
from core.tamper.ela_detector import run_ela


# ── Weights ─────────────────────────────────────
W_RULE = 0.50
W_CONF = 0.30
W_ELA  = 0.20

# 🔥 NEW THRESHOLDS (as you asked)
GENUINE_THRESHOLD = 80
REVIEW_THRESHOLD  = 70


# ───────────────────────────────────────────────
def _compute_ela_integrity(tamper_score: int) -> int:
    return max(0, 100 - tamper_score)


# ───────────────────────────────────────────────
def compute_blur_penalty(image_path):
    try:
        img = cv2.imread(image_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        blur_val = cv2.Laplacian(gray, cv2.CV_64F).var()

        if blur_val < 50:
            return 30   # very blurry
        elif blur_val < 100:
            return 15   # slightly blurry
        else:
            return 0

    except:
        return 0


# ───────────────────────────────────────────────
def generate_reasoning(gemini_data, rule_score, tamper_score, blur_penalty, issues):
    reasoning = []

    if gemini_data.get("id_number"):
        reasoning.append("✔ ID detected")

    if gemini_data.get("name"):
        reasoning.append("✔ Name present")

    if rule_score > 80:
        reasoning.append("✔ Format valid")
    else:
        reasoning.append("❌ Format issues detected")

    if tamper_score >= 40:
        reasoning.append("🚨 Strong tampering detected")
    elif tamper_score >= 20:
        reasoning.append("⚠ Possible tampering detected")
    else:
        reasoning.append("✔ No strong tampering")

    if blur_penalty >= 30:
        reasoning.append("⚠ Image very blurry")
    elif blur_penalty >= 15:
        reasoning.append("⚠ Image slightly blurry")

    return list(dict.fromkeys(reasoning))


# ───────────────────────────────────────────────
def analyze_document(image_path: str) -> dict:

    all_issues = []
    heatmap = None

    # ── STEP 1: GEMINI ─────────────────────────
    try:
        gemini_data = analyze_with_gemini(image_path)
    except Exception as e:
        gemini_data = {
            "doc_type": "unknown",
            "confidence": 0,
            "issues": [str(e)]
        }

    gemini_conf = int(gemini_data.get("confidence", 0))
    all_issues.extend(gemini_data.get("issues", []))

    # ── STEP 2: VALIDATION ─────────────────────
    try:
        rule_score, rule_issues = run_validation(gemini_data)
    except:
        rule_score, rule_issues = 0, []

    all_issues.extend(rule_issues)
    rule_score = max(0, min(100, rule_score * 10))

    # ── STEP 3: ELA ────────────────────────────
    try:
        tamper_score, heatmap = run_ela(image_path)
    except:
        tamper_score = 0
        heatmap = None

    # ── STEP 4: BLUR DETECTION ─────────────────
    blur_penalty = compute_blur_penalty(image_path)

    if blur_penalty >= 30:
        all_issues.append("Image very blurry")
    elif blur_penalty >= 15:
        all_issues.append("Image slightly blurry")

    # Reduce Gemini confidence if tampered
    if tamper_score >= 20:
        gemini_conf *= 0.7
    if tamper_score >= 40:
        gemini_conf *= 0.5

    ela_integrity = _compute_ela_integrity(tamper_score)

    # ── STEP 5: BASE SCORE ─────────────────────
    final_score = int(
        W_RULE * rule_score +
        W_CONF * gemini_conf +
        W_ELA  * ela_integrity
    )

    # ─────────────────────────────
    # 🔴 STRONG VALIDATION PENALTY
    # ─────────────────────────────
    validation_penalty = 0

    for issue in all_issues:
        t = issue.lower()

        if "pan" in t and "invalid" in t:
            validation_penalty += 40

        if "aadhaar" in t and ("invalid" in t or "failed" in t):
            validation_penalty += 40

        if "marks" in t or "total mismatch" in t:
            validation_penalty += 35

        if "name" in t:
            validation_penalty += 10

        if "dob" in t:
            validation_penalty += 10

    # ─────────────────────────────
    # 🔴 TAMPER PENALTY
    # ─────────────────────────────
    if tamper_score >= 40:
        final_score -= 40
    elif tamper_score >= 20:
        final_score -= 20

    # ─────────────────────────────
    # APPLY PENALTIES
    # ─────────────────────────────
    final_score -= validation_penalty
    final_score -= blur_penalty

    issue_penalty = min(len(all_issues) * 4, 30)
    final_score -= issue_penalty

    # ─────────────────────────────
    # FINAL CLAMP
    # ─────────────────────────────
    final_score = max(0, min(100, final_score))

    # ── STEP 6: NEW VERDICT LOGIC ───────────────
    if final_score >= 80:
        verdict = "GENUINE"
    elif final_score >= 70:
        verdict = "REVIEW"
    else:
        verdict = "SUSPICIOUS"

    # CLEAN ISSUES
    clean_issues = list(dict.fromkeys(all_issues))

    # REASONING
    reasoning = generate_reasoning(
        gemini_data,
        rule_score,
        tamper_score,
        blur_penalty,
        clean_issues
    )

    return {
        "score": final_score,
        "verdict": verdict,
        "issues": clean_issues,
        "reasoning": reasoning,
        "heatmap": heatmap,
        "gemini_data": gemini_data
    }