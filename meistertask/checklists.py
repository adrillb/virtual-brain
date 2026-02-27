"""MeisterTask checklist functions -- CRUD for checklist items of a task."""

import json
import logging
import requests
from config import MT_BASE_URL, MT_HEADERS

logger = logging.getLogger(__name__)

# Status codes used by MeisterTask for checklist items
_STATUS_UNCHECKED = 1
_STATUS_CHECKED = 5


# ---------------------------------------------------------------------------
# HELPERS (internal)
# ---------------------------------------------------------------------------


def _get_or_create_checklist_id(task_id):
    """Return the first checklist ID for a task, creating one if none exists.

    Returns (checklist_id, error_string).  On success error_string is None.
    """
    resp = requests.get(
        f"{MT_BASE_URL}/tasks/{task_id}/checklists",
        headers=MT_HEADERS,
    )
    if resp.status_code == 200:
        checklists = resp.json()
        if checklists:
            return checklists[0]["id"], None
    elif resp.status_code != 200:
        return None, f"Error fetching checklists: {resp.status_code}: {resp.text}"

    # No checklist exists yet -- create one
    logger.info("Task %s has no checklist; creating one.", task_id)
    resp = requests.post(
        f"{MT_BASE_URL}/tasks/{task_id}/checklists",
        headers=MT_HEADERS,
        json={"name": "Checklist"},
    )
    if resp.status_code in (200, 201):
        return resp.json()["id"], None
    return None, f"Error creating checklist: {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# READ
# ---------------------------------------------------------------------------


def get_task_checklist_items(task_id):
    """Get all checklist items belonging to a task."""
    resp = requests.get(
        f"{MT_BASE_URL}/tasks/{task_id}/checklist_items",
        headers=MT_HEADERS,
    )
    if resp.status_code == 200:
        items = resp.json()
        return json.dumps([
            {
                "id": i["id"],
                "name": i["name"],
                "checked": i.get("status") == _STATUS_CHECKED,
                "checklist_id": i.get("checklist_id"),
            }
            for i in items
        ])
    return f"Error {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------


def create_checklist_item(task_id, name, checked="false"):
    """Add a new item to a task's checklist.

    Automatically resolves the checklist_id from the task.
    If the task has no checklist yet, one is created first.
    """
    checklist_id, err = _get_or_create_checklist_id(task_id)
    if err:
        return err

    data = {"name": name}
    if checked.lower() == "true":
        data["status"] = _STATUS_CHECKED

    resp = requests.post(
        f"{MT_BASE_URL}/checklists/{checklist_id}/checklist_items",
        headers=MT_HEADERS,
        json=data,
    )
    if resp.status_code in (200, 201):
        item = resp.json()
        return json.dumps({
            "id": item["id"],
            "name": item["name"],
            "checked": item.get("status") == _STATUS_CHECKED,
            "result": "created",
        })
    return f"Error {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# UPDATE
# ---------------------------------------------------------------------------


def update_checklist_item(checklist_item_id, name="", checked=""):
    """Update a checklist item's name and/or checked status.

    - name: new text for the item (optional).
    - checked: "true" to mark as checked, "false" to uncheck (optional).
    """
    data = {}
    if name:
        data["name"] = name
    if checked:
        if checked.lower() == "true":
            data["status"] = _STATUS_CHECKED
        elif checked.lower() == "false":
            data["status"] = _STATUS_UNCHECKED

    if not data:
        return "Error: No fields provided to update."

    resp = requests.put(
        f"{MT_BASE_URL}/checklist_items/{checklist_item_id}",
        headers=MT_HEADERS,
        json=data,
    )
    if resp.status_code == 200:
        item = resp.json()
        return json.dumps({
            "id": item["id"],
            "name": item["name"],
            "checked": item.get("status") == _STATUS_CHECKED,
            "result": "updated",
        })
    return f"Error {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------


def delete_checklist_item(checklist_item_id):
    """Delete a checklist item by its ID."""
    resp = requests.delete(
        f"{MT_BASE_URL}/checklist_items/{checklist_item_id}",
        headers=MT_HEADERS,
    )
    if resp.status_code in (200, 204):
        return json.dumps({"id": checklist_item_id, "result": "deleted"})
    return f"Error {resp.status_code}: {resp.text}"
