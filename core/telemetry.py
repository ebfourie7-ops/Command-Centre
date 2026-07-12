"""Command Widget telemetry client with local-state fallback."""

import json
import urllib.request
from pathlib import Path


DEFAULT_URL = "http://127.0.0.1:9090/telemetry"
DEFAULT_STATE_FILE = Path.home() / ".local/state/telemetry/telemetry.json"


def read_telemetry(url=DEFAULT_URL, state_file=DEFAULT_STATE_FILE, timeout=0.8):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        pass
    try:
        data = json.loads(Path(state_file).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}
