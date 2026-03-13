"""MeisterTask section functions."""

import json
import requests
from config import MT_BASE_URL, MT_HEADERS


def get_sections(status="active"):
    """List all sections across all projects."""
    resp = requests.get(
        f"{MT_BASE_URL}/sections",
        headers=MT_HEADERS,
        params={"status": status},
    )
    if resp.status_code == 200:
        return json.dumps([
            {"id": s["id"], "name": s["name"], "project_id": s.get("project_id"), "color": s.get("color")}
            for s in resp.json()
        ])
    return f"Error {resp.status_code}: {resp.text}"


def get_project_sections(project_id):
    """List all sections (columns) of a specific project."""
    resp = requests.get(
        f"{MT_BASE_URL}/projects/{project_id}/sections",
        headers=MT_HEADERS,
    )
    if resp.status_code == 200:
        return json.dumps([
            {
                "id": s["id"],
                "name": s["name"],
                "project_id": s.get("project_id", project_id),
                "color": s.get("color"),
            }
            for s in resp.json()
        ])
    return f"Error {resp.status_code}: {resp.text}"
