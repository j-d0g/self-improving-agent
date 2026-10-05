import json
from pathlib import Path


def read_json_logs(log_dir: Path, pattern: str = "*.json") -> list[dict]:
    if not log_dir.exists():
        return []

    logs = []
    for log_file in sorted(log_dir.glob(pattern)):
        try:
            with open(log_file) as f:
                logs.append(json.load(f))
        except (json.JSONDecodeError, IOError):
            continue
    return logs
