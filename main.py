from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import tempfile
import os

from analyze import analyze_document

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "*",
    "Content-Type": "application/json",
}

class Handler(BaseHTTPRequestHandler):

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

    def do_GET(self):
        if self.path == "/health":
            self.send_json({"status": "ok"})
        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        if self.path == "/detect":
            self.handle_detect()
        else:
            self.send_json({"error": "Not found"}, 404)

    def handle_detect(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            file_data = self.rfile.read(length)

            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                tmp.write(file_data)
                path = tmp.name

            result = analyze_document(path)

            self.send_json(result)

        except Exception as e:
            self.send_json({"error": str(e)}, 500)


def run():
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print("Server running on port", port)
    server.serve_forever()


if __name__ == "__main__":
    run()
