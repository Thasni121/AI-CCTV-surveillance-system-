
import json
from pathlib import Path
from collections import Counter

def write_event(path, event):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

def read_events(path, limit=1000):
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows[-limit:][::-1]

def summarize_events(events):
    types = Counter(e.get("event_type", "unknown") for e in events)
    classes = Counter(e.get("class_name", "unknown") for e in events if e.get("class_name"))
    return {"total_events": len(events), "types": dict(types), "classes": dict(classes)}
