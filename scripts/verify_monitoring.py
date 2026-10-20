"""Create sample traffic and verify individual API pods in Prometheus."""

import argparse
import json
import time
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path

from verify_api import request


def run(api_url: str, prometheus_url: str, count: int) -> dict:
    if not 1 <= count <= 600:
        raise ValueError("Traffic count must be between 1 and 600")
    sample = json.loads(Path("examples/patient.json").read_text())
    for index in range(count):
        payload = {**sample, "thal": 0} if index % 10 == 0 else sample
        status, _ = request(api_url, "/predict", payload)
        if status != (422 if index % 10 == 0 else 200):
            raise RuntimeError(f"Unexpected traffic response: {status}")
        time.sleep(1)
    status, text = request(prometheus_url, "/api/v1/targets")
    if status != 200:
        raise RuntimeError("Prometheus targets query failed")
    targets = [
        target
        for target in json.loads(text)["data"]["activeTargets"]
        if target["labels"].get("job") == "heart-risk-api"
    ]
    if len(targets) < 2 or any(target["health"] != "up" for target in targets):
        raise RuntimeError("Expected at least two healthy API pod scrape targets")
    query = urllib.parse.urlencode(
        {"query": 'sum(rate(heart_requests_total{route="/predict"}[2m]))'}
    )
    status, text = request(prometheus_url, "/api/v1/query?" + query)
    series = json.loads(text)
    if status != 200 or not series["data"]["result"]:
        raise RuntimeError("No request-rate series; capture at least two scrape intervals")
    return {
        "status": "passed",
        "verified_at": datetime.now(UTC).isoformat(),
        "healthy_targets": len(targets),
        "request_rate": series["data"]["result"],
        "traffic_requests": count,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://localhost:8080")
    parser.add_argument("--prometheus", default="http://localhost:9090")
    parser.add_argument("--count", type=int, default=120)
    arguments = parser.parse_args()
    result = run(arguments.api, arguments.prometheus, arguments.count)
    output = Path("reports/evidence/monitoring.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
