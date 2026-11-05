#!/usr/bin/env python3
"""
AgriSense Edge Model Server
===========================
Lightweight local HTTP inference server for the AgriSense 10-Class CNN Model.
Serves on port 8081 to provide direct on-demand edge inference for the mobile app
running on Android Emulator (http://10.0.2.2:8081/diagnose) and physical devices.
"""

import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

# Add backend handler to sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HANDLERS_DIR = os.path.join(ROOT_DIR, "backend", "handlers")
if HANDLERS_DIR not in sys.path:
    sys.path.insert(0, HANDLERS_DIR)

from inference_handler import run_inference
from chat_handler import generate_expert_agronomic_fallback


class ModelInferenceHandler(BaseHTTPRequestHandler):
    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Filename")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(204)

    def do_GET(self):
        if self.path in ["/", "/health", "/status"]:
            self._set_headers(200)
            self.wfile.write(json.dumps({
                "status": "online",
                "model": "AgriSense-Tomato-CNN-4Block-INT8",
                "accuracy": "77.03%",
                "classes": 10
            }).encode("utf-8"))
        else:
            self._set_headers(404)
            self.wfile.write(b'{"error": "Endpoint not found"}')

    def do_POST(self):
        if self.path.startswith("/diagnose"):
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                image_bytes = self.rfile.read(content_length)

                if not image_bytes:
                    self._set_headers(400)
                    self.wfile.write(b'{"error": "No image data received"}')
                    return

                # Execute quantized INT8 CNN model inference
                result = run_inference(image_bytes)
                result["source"] = "AgriSense TFLite INT8 CNN Model"

                self._set_headers(200)
                self.wfile.write(json.dumps(result).encode("utf-8"))

                conf_pct = result.get("confidence", 0) * 100
                print(f"[Edge Model Server] Inferred: {result.get('class_name')} ({conf_pct:.1f}% confidence)")
            except Exception as e:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        elif self.path.startswith("/chat"):
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body_bytes = self.rfile.read(content_length)
                payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
                prompt = payload.get("prompt", "")
                diagnosis_context = payload.get("diagnosis_context", {})
                reply = generate_expert_agronomic_fallback(prompt, diagnosis_context)
                self._set_headers(200)
                self.wfile.write(json.dumps({"reply": reply}).encode("utf-8"))
            except Exception as e:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        else:
            self._set_headers(404)
            self.wfile.write(b'{"error": "Endpoint not found"}')

    def log_message(self, format, *args):
        # Clean server logging
        sys.stderr.write(f"[Server] {args[0]} {args[1]} -> {args[2]}\n")


def run(port=8081):
    server_address = ("0.0.0.0", port)
    httpd = HTTPServer(server_address, ModelInferenceHandler)
    print("=" * 65)
    print("  AgriSense Edge Model Server (TFLite INT8)")
    print(f"  Listening on: http://0.0.0.0:{port}")
    print(f"  Android Emulator Endpoint: http://10.0.2.2:{port}/diagnose")
    print(f"  Desktop / Local Endpoint:   http://127.0.0.1:{port}/diagnose")
    print("=" * 65)
    httpd.serve_forever()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8081
    run(port)

