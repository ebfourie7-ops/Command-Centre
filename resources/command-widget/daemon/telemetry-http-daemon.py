#!/usr/bin/env python3
import json
import os
import signal
import sys
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

state_dir = Path.home() / ".local" / "state" / "telemetry"
state_dir.mkdir(parents=True, exist_ok=True)
state_file = state_dir / "telemetry.json"
pid_file = state_dir / "telemetry-http.pid"

def cleanup(sig, frame):
    if pid_file.exists():
        pid_file.unlink()
    sys.exit(0)

class TelemetryHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/telemetry" or self.path == "/":
            try:
                if state_file.exists():
                    with open(state_file) as f:
                        data = json.load(f)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps(data).encode())
                else:
                    self.send_response(503)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"error":"telemetry unavailable"}')
            except Exception:
                self.send_response(500)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    if "INVOCATION_ID" not in os.environ and pid_file.exists():
        try:
            pid = int(pid_file.read_text())
            os.kill(pid, 0)
            sys.exit(0)
        except (ProcessLookupError, ValueError):
            pass

    pid_file.write_text(str(os.getpid()))

    print("Starting telemetry HTTP server on port 9090")
    server = HTTPServer(("127.0.0.1", 9090), TelemetryHandler)
    server.serve_forever()
