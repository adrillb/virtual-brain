"""MeisterTask comment functions."""

import json
import requests
from config import MT_BASE_URL, MT_HEADERS


def get_task_comments(task_id):
    """Get all comments on a task."""
    resp = requests.get(
        f"{MT_BASE_URL}/tasks/{task_id}/comments",
        headers=MT_HEADERS,
    )
    if resp.status_code == 200:
        return json.dumps([
            {"id": c["id"], "text": c["text"], "person_id": c.get("person_id"), "created_at": c.get("created_at")}
            for c in resp.json()
        ])
    return f"Error {resp.status_code}: {resp.text}"


def create_comment(task_id, text):
    """Add a comment to a task (supports Markdown)."""
    resp = requests.post(
        f"{MT_BASE_URL}/tasks/{task_id}/comments",
        headers=MT_HEADERS,
        json={"text": text},
    )
    if resp.status_code in (200, 201):
        c = resp.json()
        return json.dumps({"id": c["id"], "task_id": c["task_id"], "result": "comment created"})
    return f"Error {resp.status_code}: {resp.text}"
