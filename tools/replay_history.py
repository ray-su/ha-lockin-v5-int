"""Replay HA-recorded event attributes; not a claim of native MQTT capture.

Usage: .venv/bin/python tools/replay_history.py PRIVATE_HISTORY.json [...]
Only aggregate counts/readable labels are printed. Private input is never bundled.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from custom_components.lockin_v5.decoder import Decoder, LockState

ROOT = Path(__file__).resolve().parents[1]
spec = json.loads((ROOT / "custom_components/lockin_v5/miot-v2203.json").read_text())
names = {(s["iid"], p["description"]): p["iid"] for s in spec["services"] for p in s.get("properties", []) if p["description"]}
names[(11, "customized-property")] = 20
state = LockState(Decoder(spec))
rows = []
for filename in sys.argv[1:]:
    doc = json.loads(Path(filename).read_text())
    rows.extend(r for group in doc["history"] for r in group)
counts = Counter()
labels = Counter()
for row in sorted(rows, key=lambda r: r.get("last_updated", r["last_changed"])):
    match = re.search(r"_e_(\d+)_(\d+)$", row["entity_id"])
    if not match:
        continue
    counts["event_state_rows"] += 1
    if row["state"] in ("unknown", "unavailable"):
        counts["ignored_unavailable_or_unknown"] += 1
        continue
    if row["attributes"].get("restored"):
        counts["ignored_ha_restored_state"] += 1
        continue
    siid, eiid = map(int, match.groups())
    payload = {"siid": siid, "eiid": eiid, "arguments": [{"piid": names[siid, key], "value": value} for key, value in row["attributes"].items() if (siid, key) in names and key not in ("Operation ID", "Cloud Video ID")]}
    # For untimed HA events, the entity timestamp identifies the original occurrence.
    received = datetime.fromisoformat(row["state"])
    result = state.apply_event(payload, received)
    if result is None:
        counts["duplicate_or_invalid"] += 1
    else:
        counts["accepted"] += 1
        counts[f"accepted_{result.category}"] += 1
        labels[result.summary] += 1
print(json.dumps({"input_files": len(sys.argv) - 1, "counts": counts, "readable_labels": labels, "scope": "Actual HA history, reconstructed MIoT argument shape; no live cloud or lock control exercised"}, indent=2))
