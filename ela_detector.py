import io
import numpy as np
from PIL import Image, ImageChops, ImageEnhance
import cv2


def run_ela(image_path: str, quality: int = 90) -> tuple[int, np.ndarray]:

    try:
        original = Image.open(image_path).convert("RGB")
    except:
        return 0, np.zeros((100, 100, 3), dtype=np.uint8)

    # ── Recompress image ─────────────────────────────
    buf = io.BytesIO()
    original.save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    recompressed = Image.open(buf).convert("RGB")

    # ── Difference ───────────────────────────────────
    diff = ImageChops.difference(original, recompressed)

    # Amplify
    amplified = ImageEnhance.Brightness(diff).enhance(15)

    # Convert to numpy
    diff_arr = np.array(diff, dtype=np.float32)
    amp_arr = np.array(amplified, dtype=np.uint8)

    # ── Convert to grayscale ─────────────────────────
    gray = diff_arr.mean(axis=2)

    # ── Smooth noise (IMPORTANT) ─────────────────────
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    # Normalize
    norm = gray / 255.0

    # ── Compute tamper ratio ─────────────────────────
    high_pixels = (norm > 0.15).sum()
    total_pixels = norm.size

    tamper_ratio = high_pixels / total_pixels

    # ── Score mapping (IMPROVED) ─────────────────────
    if tamper_ratio > 0.12:
        tamper_score = 40
    elif tamper_ratio > 0.06:
        tamper_score = 20
    else:
        tamper_score = 0

    # ── Heatmap ──────────────────────────────────────
    heatmap = _colorize_heatmap(gray)

    return tamper_score, heatmap


# ─────────────────────────────────────────────
def _colorize_heatmap(gray: np.ndarray) -> np.ndarray:
    """
    Better color mapping using OpenCV colormap
    """

    # Normalize to 0–255
    gray_norm = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
    gray_uint8 = gray_norm.astype(np.uint8)

    # Apply heatmap (JET gives red hotspots)
    heatmap = cv2.applyColorMap(gray_uint8, cv2.COLORMAP_JET)

    return heatmap