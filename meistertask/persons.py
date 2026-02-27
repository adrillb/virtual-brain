"""MeisterTask person functions."""

import json
import requests
from config import MT_BASE_URL, MT_HEADERS


def get_person(person_id):
    """Get details about a person/user by ID."""
    resp = requests.get(
        f"{MT_BASE_URL}/persons/{person_id}",
        headers=MT_HEADERS,
    )
    if resp.status_code == 200:
        p = resp.json()
        return json.dumps({
            "id": p["id"], "firstname": p.get("firstname"), "lastname": p.get("lastname"),
            "email": p.get("email"),
        })
    return f"Error {resp.status_code}: {resp.text}"
