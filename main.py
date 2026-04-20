import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import tempfile
from pathlib import Path

from core.pipeline.analyze import analyze_document


# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="DocShield — Forgery Detector",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────
st.title("🛡️ DocShield")
st.caption("Document Forgery Detection System")

col_upload, col_results = st.columns([1, 1.5])

# ─────────────────────────────────────────────
# UPLOAD
# ─────────────────────────────────────────────
with col_upload:
    uploaded = st.file_uploader(
        "Upload PAN / Aadhaar / Marks Card",
        type=["jpg", "jpeg", "png", "bmp", "webp"]
    )

    if uploaded:
        st.image(uploaded, use_container_width=True)

        if st.button("⚡ Analyze Document"):
            st.session_state["analyze"] = True

    analyze_btn = st.session_state.get("analyze", False)


# ─────────────────────────────────────────────
# ANALYSIS
# ─────────────────────────────────────────────
if uploaded and analyze_btn:
    with col_results:

        with st.spinner("Analyzing document..."):

            suffix = Path(uploaded.name).suffix.lower()
            if suffix not in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]:
                suffix = ".jpg"

            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded.getvalue())
                tmp_path = tmp.name

            try:
                result = analyze_document(tmp_path)
            except Exception as e:
                st.error(f"Error: {e}")
                result = None
            finally:
                try:
                    os.unlink(tmp_path)
                except:
                    pass

        # ─────────────────────────────
        # RESULT DISPLAY
        # ─────────────────────────────
        if result:
            score = max(0, min(100, result.get("score", 0)))
            verdict = result.get("verdict", "SUSPICIOUS")

            issues = result.get("issues", [])
            reasoning = result.get("reasoning", [])   # 🔥 IMPORTANT
            heatmap = result.get("heatmap")
            gdata = result.get("gemini_data", {})

            # SCORE
            st.metric("Score", score)
            st.subheader(f"Verdict: {verdict}")

            st.write("")

            # ISSUES
            if issues:
                st.subheader("⚠ Issues")
                for i in issues:
                    st.write("•", i)
            else:
                st.success("✔ No issues detected")

            st.write("")

            # 🔥 REASONING (THIS WAS MISSING)
            if reasoning:
                st.subheader("🧠 Analysis Reasoning")
                for r in reasoning:
                    st.write("•", r)

            st.write("")

            # HEATMAP
            if heatmap is not None:
                st.subheader("🔥 Tampering Heatmap")
                st.image(heatmap, use_container_width=True)

            # EXTRACTED DATA
            st.subheader("📋 Extracted Fields")

            filtered = {
                k: v for k, v in gdata.items()
                if k not in ["issues", "confidence"] and v not in [None, "", []]
            }

            if filtered:
                st.json(filtered)
            else:
                st.write("No data extracted")

# ─────────────────────────────────────────────
# EMPTY
# ─────────────────────────────────────────────
elif not uploaded:
    with col_results:
        st.info("Upload a document to begin analysis")
