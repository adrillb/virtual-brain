"""MeisterTask project functions."""

import json
import requests
from config import MT_BASE_URL, MT_HEADERS


def get_projects(status="active"):
    """List all projects. Returns JSON array with id, name, notes, status."""
    resp = requests.get(
        f"{MT_BASE_URL}/projects",
        headers=MT_HEADERS,
        params={"status": status},
    )
    if resp.status_code == 200:
        return json.dumps([
            {"id": p["id"], "name": p["name"], "notes": p.get("notes"), "status": p.get("status")}
            for p in resp.json()
        ])
    return f"Error {resp.status_code}: {resp.text}"


def get_project_members(project_id):
    """Get all members of a project. Returns JSON with persons array."""
    resp = requests.get(
        f"{MT_BASE_URL}/projects/{project_id}/members",
        headers=MT_HEADERS,
        params={"include_persons": "true"},
    )
    if resp.status_code == 200:
        data = resp.json()
        persons = data.get("persons", [])
        return json.dumps([
            {"id": p["id"], "firstname": p.get("firstname"), "lastname": p.get("lastname"), "email": p.get("email")}
            for p in persons
        ])
    return f"Error {resp.status_code}: {resp.text}"
