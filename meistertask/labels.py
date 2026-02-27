"""MeisterTask label functions."""

import json
import requests
from config import MT_BASE_URL, MT_HEADERS


def get_project_labels(project_id):
    """Get all labels of a specific project."""
    resp = requests.get(
        f"{MT_BASE_URL}/projects/{project_id}/labels",
        headers=MT_HEADERS,
    )
    if resp.status_code == 200:
        return json.dumps([
            {"id": l["id"], "name": l["name"], "color": l.get("color")}
            for l in resp.json()
        ])
    return f"Error {resp.status_code}: {resp.text}"
