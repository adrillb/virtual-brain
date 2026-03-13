"""Interactive CLI to manually test MeisterTask API wrapper functions."""

from __future__ import annotations

import inspect
import json
from collections import OrderedDict

from meistertask import TOOL_REGISTRY
from meistertask.tasks import get_health_day_tasks, get_tasks_due_today


MENU_GROUPS = OrderedDict(
    [
        ("Projects", ["get_projects", "get_project_members"]),
        ("Sections", ["get_sections", "get_project_sections"]),
        ("Labels", ["get_project_labels"]),
        (
            "Tasks",
            [
                "get_all_tasks",
                "get_task",
                "get_section_tasks",
                "get_my_tasks",
                "search_tasks",
                "create_task",
                "create_task_with_checklist",
                "update_task",
                "complete_task",
                "reopen_task",
                "move_task",
                "assign_task",
                "set_task_due_date",
                "trash_task",
            ],
        ),
        (
            "Checklists",
            [
                "get_task_checklist_items",
                "create_checklist_item",
                "update_checklist_item",
                "delete_checklist_item",
            ],
        ),
        ("Comments", ["get_task_comments", "create_comment"]),
        ("Persons", ["get_person"]),
        ("Utilities", ["get_tasks_due_today", "get_health_day_tasks"]),
    ]
)


def _build_function_index() -> OrderedDict[str, list[tuple[str, callable]]]:
    """Build categorized function list from TOOL_REGISTRY + utility helpers."""
    available = dict(TOOL_REGISTRY)
    available["get_tasks_due_today"] = get_tasks_due_today
    available["get_health_day_tasks"] = get_health_day_tasks

    grouped_functions: OrderedDict[str, list[tuple[str, callable]]] = OrderedDict()
    for category, function_names in MENU_GROUPS.items():
        grouped_functions[category] = []
        for name in function_names:
            function = available.get(name)
            if function is not None:
                grouped_functions[category].append((name, function))
    return grouped_functions


def _format_signature(function: callable) -> str:
    """Return parameter list for display, e.g. a, b, c."""
    signature = inspect.signature(function)
    params = ", ".join(signature.parameters.keys())
    return params


def _print_menu(grouped_functions: OrderedDict[str, list[tuple[str, callable]]]) -> dict[str, callable]:
    """Render menu and return numeric index => function map."""
    print("\n=== MeisterTask API Tester ===\n")
    selection_map: dict[str, callable] = {}
    index = 1

    for category, functions in grouped_functions.items():
        if not functions:
            continue
        print(f"[{category}]")
        for name, function in functions:
            params = _format_signature(function)
            print(f"  {index}. {name}({params})")
            selection_map[str(index)] = function
            index += 1
        print()

    print("0/q. Salir")
    return selection_map


def _coerce_input(value: str, parameter: inspect.Parameter):
    """Convert user input to match simple expected types when possible."""
    default = parameter.default
    annotation = parameter.annotation

    if annotation is int:
        return int(value)
    if annotation is float:
        return float(value)

    if default is not inspect._empty:
        if isinstance(default, bool):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "y"}:
                return True
            if lowered in {"false", "0", "no", "n"}:
                return False
            raise ValueError("Expected boolean value (true/false).")
        if isinstance(default, int):
            return int(value)
        if isinstance(default, float):
            return float(value)

    return value


def _collect_arguments(function: callable) -> dict:
    """Prompt user for parameters based on function signature."""
    signature = inspect.signature(function)
    arguments = {}

    for parameter in signature.parameters.values():
        has_default = parameter.default is not inspect._empty
        default = parameter.default

        while True:
            if has_default:
                prompt = f"  - {parameter.name} [default={default!r}]: "
            else:
                prompt = f"  - {parameter.name} (required): "

            raw_value = input(prompt).strip()
            if raw_value == "":
                if has_default:
                    arguments[parameter.name] = default
                    break
                print("    Este campo es obligatorio.")
                continue

            try:
                arguments[parameter.name] = _coerce_input(raw_value, parameter)
                break
            except ValueError as exc:
                print(f"    Valor invalido: {exc}")

    return arguments


def _pretty_print_result(result) -> None:
    """Pretty print strings/JSON/dicts/lists in a readable way."""
    print("\nResultado:")
    if isinstance(result, (dict, list)):
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if isinstance(result, str):
        stripped = result.strip()
        try:
            parsed = json.loads(stripped)
            print(json.dumps(parsed, indent=2, ensure_ascii=False))
        except json.JSONDecodeError:
            print(result)
        return

    print(repr(result))


def main() -> None:
    """Interactive loop to invoke MeisterTask helper functions."""
    grouped_functions = _build_function_index()

    while True:
        selection_map = _print_menu(grouped_functions)
        choice = input("\nSelecciona una opcion: ").strip().lower()

        if choice in {"0", "q", "quit", "exit"}:
            print("Saliendo...")
            return

        function = selection_map.get(choice)
        if function is None:
            print("Opcion invalida. Intenta de nuevo.")
            continue

        print(f"\nParametros para: {function.__name__}")
        try:
            arguments = _collect_arguments(function)
            result = function(**arguments)
            _pretty_print_result(result)
        except KeyboardInterrupt:
            print("\nOperacion cancelada por el usuario.")
        except EOFError:
            print("\nEntrada finalizada. Saliendo...")
            return
        except Exception as exc:  # noqa: BLE001 - test helper should never crash hard
            print(f"\nError ejecutando {function.__name__}: {exc}")

        input("\nPresiona Enter para volver al menu...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrumpido. Hasta luego.")
