"""
Tool registry: maps function names to callables.
The bot uses this to dispatch LLM tool calls to the right function.
"""

from meistertask.projects import get_projects, get_project_members
from meistertask.sections import get_sections, get_project_sections
from meistertask.labels import get_project_labels
from meistertask.tasks import (
    get_all_tasks, get_task, get_section_tasks, get_my_tasks, search_tasks,
    create_task, create_task_with_checklist, update_task,
    complete_task, reopen_task, move_task, assign_task,
    set_task_due_date, trash_task,
)
from meistertask.checklists import (
    get_task_checklist_items, create_checklist_item,
    update_checklist_item, delete_checklist_item,
)
from meistertask.comments import get_task_comments, create_comment
from meistertask.persons import get_person

TOOL_REGISTRY = {
    "get_projects": get_projects,
    "get_project_members": get_project_members,
    "get_sections": get_sections,
    "get_project_sections": get_project_sections,
    "get_project_labels": get_project_labels,
    "get_all_tasks": get_all_tasks,
    "get_task": get_task,
    "get_section_tasks": get_section_tasks,
    "get_my_tasks": get_my_tasks,
    "search_tasks": search_tasks,
    "create_task": create_task,
    "create_task_with_checklist": create_task_with_checklist,
    "update_task": update_task,
    "complete_task": complete_task,
    "reopen_task": reopen_task,
    "move_task": move_task,
    "assign_task": assign_task,
    "set_task_due_date": set_task_due_date,
    "trash_task": trash_task,
    "get_task_checklist_items": get_task_checklist_items,
    "create_checklist_item": create_checklist_item,
    "update_checklist_item": update_checklist_item,
    "delete_checklist_item": delete_checklist_item,
    "get_task_comments": get_task_comments,
    "create_comment": create_comment,
    "get_person": get_person,
}
