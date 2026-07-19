#!/usr/bin/env bash
set -euo pipefail

STATE_FILE="${XDG_STATE_HOME:-$HOME/.local/state}/telemetry/telemetry.json"

if [ ! -f "$STATE_FILE" ]; then
  echo "Telemetry unavailable"
  exit 0
fi

python3 - "$STATE_FILE" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    with path.open() as handle:
        data = json.load(handle)
except Exception:
    print("Telemetry unavailable")
    sys.exit(0)

print(f"Load {data.get('cpu_load', 'n/a')} | Mem {data.get('mem_percent', 'n/a')}%")
PY
