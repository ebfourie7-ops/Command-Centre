import json
import tempfile
import unittest
from pathlib import Path

from core.telemetry import read_telemetry


class TelemetryTests(unittest.TestCase):
    def test_local_fallback_and_malformed_state(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "telemetry.json"
            state.write_text(json.dumps({"cpu_usage": 12.5}), encoding="utf-8")
            self.assertEqual(read_telemetry("http://127.0.0.1:1", state, 0.01)["cpu_usage"], 12.5)
            state.write_text("not json", encoding="utf-8")
            self.assertEqual(read_telemetry("http://127.0.0.1:1", state, 0.01), {})


if __name__ == "__main__":
    unittest.main()
