from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import tempfile
import os
import io

from analyze import analyze_document

# PDF
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# CORS
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "*",
    "Content-Type": "application/json",
}

class Handler(BaseHTTPRequestHandler):

    # ---------- HELPERS ----------
    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        for k, v in CORS_HEADERS.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in CORS_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()

    # ---------- HEALTH ----------
    def do_GET(self):
    if self.path == "/health":
        self.send_json({"status": "ok"})

    # ✅ TEMP TEST ROUTE
    elif self.path == "/detect-test":
        try:
            # use any sample image inside repo
            sample_path = "test.jpg"   # 👈 add this image in repo

            result = analyze_document(sample_path)

            self.send_json({
                "message": "detect working",
                "score": result.get("score"),
                "verdict": result.get("verdict")
            })

        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    else:
        self.send_json({"error": "Not found"}, 404)

    # ---------- POST ----------
    def do_POST(self):
        if self.path == "/detect":
            self.handle_detect()
        else:
            self.send_json({"error": "Not found"}, 404)

    # ---------- MAIN LOGIC ----------
    def handle_detect(self):
        try:
            # read image
            length = int(self.headers.get("Content-Length", 0))
            file_data = self.rfile.read(length)

            # save temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                tmp.write(file_data)
                path = tmp.name

            # run AI
            result = analyze_document(path)

            # ---------- CREATE PDF ----------
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer)
            styles = getSampleStyleSheet()

            content = []

            content.append(Paragraph("Forgery Detection Report", styles["Title"]))
            content.append(Spacer(1, 12))

            content.append(Paragraph(f"Score: {result.get('score', 0)}", styles["Normal"]))
            content.append(Paragraph(f"Verdict: {result.get('verdict', 'Unknown')}", styles["Normal"]))
            content.append(Spacer(1, 10))

            # Issues
            content.append(Paragraph("Issues:", styles["Heading2"]))
            issues = result.get("issues", [])
            if issues:
                for i in issues:
                    content.append(Paragraph(f"- {i}", styles["Normal"]))
            else:
                content.append(Paragraph("No issues detected", styles["Normal"]))

            content.append(Spacer(1, 10))

            # Reasoning
            content.append(Paragraph("Analysis Reasoning:", styles["Heading2"]))
            reasoning = result.get("reasoning", [])
            for r in reasoning:
                content.append(Paragraph(f"- {r}", styles["Normal"]))

            doc.build(content)

            pdf = buffer.getvalue()
            buffer.close()

            # ---------- SEND PDF ----------
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", "attachment; filename=report.pdf")
            self.send_header("Content-Length", str(len(pdf)))
            self.end_headers()

            self.wfile.write(pdf)

        except Exception as e:
            self.send_json({"error": str(e)}, 500)


# ---------- RUN ----------
def run():
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print("Server running on port", port)
    server.serve_forever()


if __name__ == "__main__":
    run()
