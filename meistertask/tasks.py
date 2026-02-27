"""MeisterTask task functions -- CRUD, search, and convenience actions."""

import json
from datetime import date, datetime

import requests

from config import MT_BASE_URL, MT_HEADERS


# ---------------------------------------------------------------------------
# READ
# ---------------------------------------------------------------------------


def get_all_tasks(status="", assigned_to_me="", labels="", items=0, page=0, sort=""):
    """Get all tasks across all projects with optional filters."""
    params = {}
    if status:
        params["status"] = status
    if assigned_to_me:
        params["assigned_to_me"] = assigned_to_me
    if labels:
        params["labels"] = labels
    if items > 0:
        params["items"] = items
    if page > 0:
        params["page"] = page
    if sort:
        params["sort"] = sort

    resp = requests.get(f"{MT_BASE_URL}/tasks", headers=MT_HEADERS, params=params)
    if resp.status_code == 200:
        return json.dumps([
            {
                "id": t["id"], "name": t["name"], "notes": t.get("notes", ""),
                "status": t.get("status"), "section_id": t.get("section_id"),
                "section_name": t.get("section_name"), "project_id": t.get("project_id"),
                "assigned_to_id": t.get("assigned_to_id"), "due": t.get("due"),
                "tracked_time": t.get("tracked_time"),
            }
            for t in resp.json()
        ])
    return f"Error {resp.status_code}: {resp.text}"


def get_task(task_id):
    """Get full details of a specific task by ID."""
    resp = requests.get(f"{MT_BASE_URL}/tasks/{task_id}", headers=MT_HEADERS)
    if resp.status_code == 200:
        return json.dumps(resp.json())
    return f"Error {resp.status_code}: {resp.text}"


def get_section_tasks(section_id, status="", sort=""):
    """Get all tasks within a specific section."""
    params = {}
    if status:
        params["status"] = status
        if sort:
            params["sort"] = sort
    resp = requests.get(
        f"{MT_BASE_URL}/sections/{section_id}/tasks",
        headers=MT_HEADERS, params=params,
    )
    if resp.status_code == 200:
        return json.dumps([
            {
                "id": t["id"], "name": t["name"], "notes": t.get("notes", ""),
                "status": t.get("status"), "assigned_to_id": t.get("assigned_to_id"),
                "due": t.get("due"),
            }
            for t in resp.json()
        ])
    return f"Error {resp.status_code}: {resp.text}"


def get_my_tasks():
    """Get all open tasks assigned to the current user."""
    resp = requests.get(
        f"{MT_BASE_URL}/tasks", headers=MT_HEADERS,
        params={"assigned_to_me": "true", "status": "open"},
    )
    if resp.status_code == 200:
        return json.dumps([
            {
                "id": t["id"], "name": t["name"], "notes": t.get("notes", ""),
                "section_name": t.get("section_name"), "project_id": t.get("project_id"),
                "due": t.get("due"),
            }
            for t in resp.json()
        ])
    return f"Error {resp.status_code}: {resp.text}"


def search_tasks(query, status="open"):
    """Search tasks by name or notes (case-insensitive client-side filter)."""
    params = {}
    if status:
        params["status"] = status
    resp = requests.get(f"{MT_BASE_URL}/tasks", headers=MT_HEADERS, params=params)
    if resp.status_code == 200:
        q = query.lower()
        matches = [
            {
                "id": t["id"], "name": t["name"], "notes": t.get("notes", ""),
                "project_id": t.get("project_id"), "section_name": t.get("section_name"),
                "assigned_to_id": t.get("assigned_to_id"), "due": t.get("due"),
            }
            for t in resp.json()
            if q in t.get("name", "").lower() or q in (t.get("notes") or "").lower()
        ]
        return json.dumps(matches)
    return f"Error {resp.status_code}: {resp.text}"


def get_tasks_due_today() -> list[dict]:
    """Return open tasks whose due date is today (raw Python data, no JSON).

    The ``due`` field coming from MeisterTask can be ``YYYY-MM-DD`` or an
    ISO-8601 datetime like ``YYYY-MM-DDTHH:MM:SSZ``.  We compare only the
    first 10 characters (the date portion) against today's date.
    """
    today_str = date.today().isoformat()  # "YYYY-MM-DD"
    page_size = 500
    page = 1
    tasks: list[dict] = []

    while True:
        resp = requests.get(
            f"{MT_BASE_URL}/tasks",
            headers=MT_HEADERS,
            params={"status": "open", "items": page_size, "page": page},
        )
        if resp.status_code != 200:
            return []

        batch = resp.json()
        if not batch:
            break

        for t in batch:
            due = t.get("due") or ""
            if due[:10] == today_str:
                tasks.append({
                    "id": t["id"],
                    "name": t["name"],
                    "project_id": t.get("project_id"),
                    "section_name": t.get("section_name", ""),
                    "due": due,
                })

        if len(batch) < page_size:
            break
        page += 1

    if not tasks and page == 1:
        # Fallback in case API pages are 0-indexed or ignore "page".
        resp = requests.get(
            f"{MT_BASE_URL}/tasks",
            headers=MT_HEADERS,
            params={"status": "open", "items": page_size, "page": 0},
        )
        if resp.status_code != 200:
            return []

        for t in resp.json():
            due = t.get("due") or ""
            if due[:10] == today_str:
                tasks.append({
                    "id": t["id"],
                    "name": t["name"],
                    "project_id": t.get("project_id"),
                    "section_name": t.get("section_name", ""),
                    "due": due,
                })

    return tasks

def get_health_day_tasks(timezone="Europe/Madrid") -> list[dict]:
    """Return open tasks from Health project section matching local weekday."""
    try:
        projects_resp = requests.get(
            f"{MT_BASE_URL}/projects",
            headers=MT_HEADERS,
            params={"status": "active"},
        )
        if projects_resp.status_code != 200:
            return []

        health_project = next(
            (p for p in projects_resp.json() if p.get("name", "").strip().lower() == "health"),
            None,
        )
        if not health_project:
            return []

        sections_resp = requests.get(
            f"{MT_BASE_URL}/projects/{health_project['id']}/sections",
            headers=MT_HEADERS,
        )
        if sections_resp.status_code != 200:
            return []

        now_local = datetime.now(ZoneInfo(timezone))
        day_name = now_local.strftime("%A")
        day_section = next(
            (s for s in sections_resp.json() if str(s.get("name", "")).strip().lower() == day_name.lower()),
            None,
        )
        if not day_section:
            return []

        section_tasks_resp = requests.get(
            f"{MT_BASE_URL}/sections/{day_section['id']}/tasks",
            headers=MT_HEADERS,
            params={"status": "open"},
        )
        if section_tasks_resp.status_code != 200:
            return []

        return [
            {
                "id": t["id"],
                "name": t["name"],
                "notes": t.get("notes", ""),
                "section_name": day_section.get("name", day_name),
            }
            for t in section_tasks_resp.json()
        ]
    except Exception:
        return []

# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------


def create_task(section_id, name, notes="", assigned_to_id=0, due="", label_ids=""):
    """Create a new task in a section."""
    data = {"name": name}
    if notes:
        data["notes"] = notes
    if assigned_to_id and int(assigned_to_id) > 0:
        data["assigned_to_id"] = int(assigned_to_id)
    if due:
        data["due"] = due
    if label_ids:
        data["label_ids"] = [int(lid.strip()) for lid in str(label_ids).split(",") if lid.strip()]

    resp = requests.post(
        f"{MT_BASE_URL}/sections/{section_id}/tasks",
        headers=MT_HEADERS, json=data,
    )
    if resp.status_code in (200, 201):
        t = resp.json()
        return json.dumps({"id": t["id"], "name": t["name"], "status": "created"})
    return f"Error {resp.status_code}: {resp.text}"


def create_task_with_checklist(section_id, name, notes="", checklist_name="Checklist", checklist_items=""):
    """Create a task with a checklist. Items are comma-separated."""
    data = {"name": name}
    if notes:
        data["notes"] = notes
    if checklist_items:
        items = [i.strip() for i in checklist_items.split(",") if i.strip()]
        data["checklists"] = [{"name": checklist_name, "items": items}]

    resp = requests.post(
        f"{MT_BASE_URL}/sections/{section_id}/tasks",
        headers=MT_HEADERS, json=data,
    )
    if resp.status_code in (200, 201):
        t = resp.json()
        return json.dumps({"id": t["id"], "name": t["name"], "status": "created"})
    return f"Error {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# UPDATE
# ---------------------------------------------------------------------------


def update_task(task_id, name="", notes="", assigned_to_id=-1, due="", status=-1, section_id=0):
    """Update any field on an existing task. Only provided fields change."""
    data = {}
    if name:
        data["name"] = name
    if notes:
        data["notes"] = notes
    if int(assigned_to_id) >= 0:
        data["assigned_to_id"] = int(assigned_to_id)
    if due:
        data["due"] = due
    if int(status) >= 0:
        data["status"] = int(status)
    if int(section_id) > 0:
        data["section_id"] = int(section_id)

    if not data:
        return "Error: No fields provided to update."

    resp = requests.put(f"{MT_BASE_URL}/tasks/{task_id}", headers=MT_HEADERS, json=data)
    if resp.status_code == 200:
        t = resp.json()
        return json.dumps({"id": t["id"], "name": t["name"], "status": t.get("status"), "result": "updated"})
    return f"Error {resp.status_code}: {resp.text}"


def complete_task(task_id):
    """Mark a task as completed (status=2)."""
    resp = requests.put(f"{MT_BASE_URL}/tasks/{task_id}", headers=MT_HEADERS, json={"status": 2})
    if resp.status_code == 200:
        return json.dumps({"id": resp.json()["id"], "result": "completed"})
    return f"Error {resp.status_code}: {resp.text}"


def reopen_task(task_id):
    """Reopen a completed task (status=1)."""
    resp = requests.put(f"{MT_BASE_URL}/tasks/{task_id}", headers=MT_HEADERS, json={"status": 1})
    if resp.status_code == 200:
        return json.dumps({"id": resp.json()["id"], "result": "reopened"})
    return f"Error {resp.status_code}: {resp.text}"


def move_task(task_id, section_id):
    """Move a task to a different section (column)."""
    resp = requests.put(f"{MT_BASE_URL}/tasks/{task_id}", headers=MT_HEADERS, json={"section_id": int(section_id)})
    if resp.status_code == 200:
        t = resp.json()
        return json.dumps({"id": t["id"], "section_id": t["section_id"], "section_name": t.get("section_name"), "result": "moved"})
    return f"Error {resp.status_code}: {resp.text}"


def assign_task(task_id, person_id):
    """Assign a task to a person. Use person_id=0 to unassign."""
    resp = requests.put(f"{MT_BASE_URL}/tasks/{task_id}", headers=MT_HEADERS, json={"assigned_to_id": int(person_id)})
    if resp.status_code == 200:
        return json.dumps({"id": resp.json()["id"], "assigned_to_id": int(person_id), "result": "assigned"})
    return f"Error {resp.status_code}: {resp.text}"


def set_task_due_date(task_id, due):
    """Set or update the due date (YYYY-MM-DD)."""
    resp = requests.put(f"{MT_BASE_URL}/tasks/{task_id}", headers=MT_HEADERS, json={"due": due})
    if resp.status_code == 200:
        return json.dumps({"id": resp.json()["id"], "due": due, "result": "due date set"})
    return f"Error {resp.status_code}: {resp.text}"


def trash_task(task_id):
    """Move a task to trash (status=8)."""
    resp = requests.put(f"{MT_BASE_URL}/tasks/{task_id}", headers=MT_HEADERS, json={"status": 8})
    if resp.status_code == 200:
        return json.dumps({"id": resp.json()["id"], "result": "trashed"})
    return f"Error {resp.status_code}: {resp.text}"
