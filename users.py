"""User access control helpers backed by users.json."""

from __future__ import annotations

import json
import logging
from typing import Any

from config import USERS_FILE
from tool_schemas import TOOLS

logger = logging.getLogger(__name__)

WRITE_TOOLS = {
    "create_task",
    "create_task_with_checklist",
    "update_task",
    "complete_task",
    "reopen_task",
    "move_task",
    "assign_task",
    "set_task_due_date",
    "trash_task",
    "create_checklist_item",
    "update_checklist_item",
    "delete_checklist_item",
    "create_comment",
}

_users_cache: dict[str, Any] = {"users": {}}
_users_mtime: float | None = None


def _normalize_projects(raw_projects: Any) -> dict[str, str]:
    projects: dict[str, str] = {}
    if not isinstance(raw_projects, dict):
        return projects

    for project_id, permission in raw_projects.items():
        permission_str = str(permission).lower().strip()
        if permission_str not in {"ro", "rw"}:
            continue
        try:
            key = str(int(project_id))
        except (TypeError, ValueError):
            continue
        projects[key] = permission_str
    return projects


def _normalize_daily_summary(raw_daily: Any) -> dict[str, Any]:
    if not isinstance(raw_daily, dict):
        return {"enabled": False, "project_ids": [], "include_health": False}

    project_ids: list[int] = []
    for item in raw_daily.get("project_ids", []):
        try:
            project_ids.append(int(item))
        except (TypeError, ValueError):
            continue

    return {
        "enabled": bool(raw_daily.get("enabled", False)),
        "project_ids": project_ids,
        "include_health": bool(raw_daily.get("include_health", False)),
    }


def load_users() -> dict[str, Any]:
    """Load users from users.json with mtime-based cache invalidation."""
    global _users_cache, _users_mtime

    try:
        mtime = USERS_FILE.stat().st_mtime
    except FileNotFoundError:
        logger.warning("users file not found: %s", USERS_FILE)
        _users_cache = {"users": {}}
        _users_mtime = None
        return _users_cache

    if _users_mtime is not None and mtime == _users_mtime:
        return _users_cache

    try:
        data = json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("failed to load users file %s: %s", USERS_FILE, exc)
        _users_cache = {"users": {}}
        _users_mtime = mtime
        return _users_cache

    raw_users = data.get("users", {}) if isinstance(data, dict) else {}
    users: dict[str, dict[str, Any]] = {}
    if isinstance(raw_users, dict):
        for telegram_id, user_data in raw_users.items():
            if not isinstance(user_data, dict):
                continue
            user_name = str(user_data.get("name", "")).strip()
            role = str(user_data.get("role", "user")).strip().lower() or "user"
            projects = _normalize_projects(user_data.get("projects", {}))
            daily_summary = _normalize_daily_summary(user_data.get("daily_summary", {}))
            users[str(telegram_id)] = {
                "name": user_name,
                "role": role,
                "projects": projects,
                "daily_summary": daily_summary,
            }

    _users_cache = {"users": users}
    _users_mtime = mtime
    return _users_cache


def get_user(telegram_id: str) -> dict[str, Any] | None:
    """Return a single user config by Telegram user ID."""
    users = load_users().get("users", {})
    return users.get(str(telegram_id))


def get_user_project_permissions(telegram_id: str) -> dict[int, str]:
    """Return `{project_id: permission}` for the given Telegram user."""
    user = get_user(telegram_id)
    if not user:
        return {}

    permissions: dict[int, str] = {}
    for project_id, permission in user.get("projects", {}).items():
        try:
            permissions[int(project_id)] = str(permission).lower()
        except (TypeError, ValueError):
            continue
    return permissions


def get_user_project_ids(telegram_id: str, permission: str | None = None) -> set[int]:
    """Return project IDs available to a user, optionally by exact permission."""
    permissions = get_user_project_permissions(telegram_id)
    if permission is None:
        return set(permissions.keys())

    permission = permission.lower().strip()
    return {project_id for project_id, value in permissions.items() if value == permission}


def is_write_tool(tool_name: str) -> bool:
    """Return True if the given tool mutates MeisterTask data."""
    return tool_name in WRITE_TOOLS


def get_tools_for_user(telegram_id: str) -> list[dict[str, Any]]:
    """Return the OpenAI tool schema list available to the user."""
    if not get_user(telegram_id):
        return []

    has_rw_projects = bool(get_user_project_ids(telegram_id, permission="rw"))
    if has_rw_projects:
        return TOOLS

    filtered_tools: list[dict[str, Any]] = []
    for tool in TOOLS:
        tool_name = tool.get("function", {}).get("name", "")
        if not is_write_tool(tool_name):
            filtered_tools.append(tool)
    return filtered_tools
