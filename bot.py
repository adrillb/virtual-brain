"""Telegram bot message handlers and daily summaries."""

from __future__ import annotations

import json
import logging
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests
from openai import OpenAI
from telegram import Update
from telegram.ext import ContextTypes

from config import MT_BASE_URL, MT_HEADERS, OPENAI_API_KEY, OPENAI_MODEL, TIMEZONE
from meistertask import TOOL_REGISTRY
from meistertask.projects import get_projects as _get_projects_json
from meistertask.tasks import get_health_day_tasks, get_tasks_due_today
from users import (
    get_admin_ids,
    get_all_member_mappings,
    get_tools_for_user,
    get_user,
    get_user_allowed_sections,
    get_user_project_ids,
    get_user_project_permissions,
    is_write_tool,
)

logger = logging.getLogger(__name__)

ai_client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT_BASE = (
    "Eres Virtual Brain, un asistente que gestiona proyectos en MeisterTask. "
    "Tienes acceso a herramientas para listar proyectos, secciones, etiquetas, miembros, "
    "crear/actualizar/completar/mover/asignar tareas, buscar tareas, gestionar comentarios y mas. "
    "Cuando el usuario pida algo, usa las herramientas necesarias paso a paso: "
    "primero busca el proyecto, luego la seccion, y despues ejecuta la accion. "
    "Cuando el usuario se refiera a la lista de la compra, busca en el proyecto 'Health' "
    "la seccion 'Shopping Cart', la tarea '🛒'. Dentro se encuentra una checklist con los items. "
    "Siempre que crees una tarea con fecha debe ser asignada a Adri. "
    "Responde siempre en el idioma del usuario."
)

MAX_TOOL_ROUNDS = 10

_SECTION_PROJECT_CACHE: dict[int, int] = {}
_TASK_PROJECT_CACHE: dict[int, int] = {}
_TASK_SECTION_CACHE: dict[int, int] = {}
_CHECKLIST_ITEM_TASK_CACHE: dict[int, int] = {}

_SECTION_TOOLS = {"get_section_tasks", "create_task", "create_task_with_checklist"}
_TASK_TOOLS = {
    "get_task",
    "get_task_comments",
    "create_comment",
    "get_task_checklist_items",
    "create_checklist_item",
    "complete_task",
    "reopen_task",
    "assign_task",
    "set_task_due_date",
    "trash_task",
}


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_json_loads(value: Any) -> Any | None:
    if not isinstance(value, str):
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _utc_example(local_hour: int, offset: str) -> str:
    """Return the UTC hour string for a local hour given an offset like '+01:00'."""
    sign = 1 if offset.startswith("+") else -1
    offset_hours = int(offset[1:3])
    utc_hour = (local_hour - sign * offset_hours) % 24
    return f"{utc_hour:02d}:00"


def _build_project_map() -> dict[int, str]:
    """Return a {project_id: project_name} mapping from MeisterTask."""
    try:
        data = json.loads(_get_projects_json())
        if isinstance(data, list):
            return {int(p["id"]): p["name"] for p in data}
    except (json.JSONDecodeError, TypeError, KeyError, ValueError):
        pass
    return {}


def _build_member_mapping_context() -> str:
    """Return configured Telegram user name -> MeisterTask member ID mapping."""
    member_mappings = get_all_member_mappings()
    if not member_mappings:
        return ""

    lines = [
        "Mapeo de usuarios a IDs de miembro de MeisterTask "
        "(para asignar tareas con assign_task o assigned_to_id):"
    ]
    for user_name in sorted(member_mappings):
        lines.append(f"- {user_name} -> person_id: {member_mappings[user_name]}")
    lines.append(
        "Si el usuario pide asignar a uno de estos nombres, usa directamente ese person_id "
        "sin llamar antes a get_project_members."
    )
    return "\n".join(lines)


def _build_access_context(telegram_id: str) -> str:
    permissions = get_user_project_permissions(telegram_id)
    if not permissions:
        return "No tienes acceso a ningun proyecto."

    project_map = _build_project_map()
    lines = ["Permisos del usuario actual en proyectos:"]

    for project_id in sorted(permissions):
        permission = permissions[project_id]
        project_name = project_map.get(project_id, f"Proyecto {project_id}")
        level = "lectura y escritura" if permission == "rw" else "solo lectura"
        allowed_sections = get_user_allowed_sections(telegram_id, project_id)
        if allowed_sections is None:
            lines.append(f"- {project_name} (ID: {project_id}) -> {level}")
            continue

        if allowed_sections:
            section_ids = ", ".join(str(section_id) for section_id in sorted(allowed_sections))
            lines.append(
                f"- {project_name} (ID: {project_id}) -> {level} "
                f"(solo secciones: {section_ids})"
            )
        else:
            lines.append(f"- {project_name} (ID: {project_id}) -> {level} (sin secciones permitidas)")

    if not any(permission == "rw" for permission in permissions.values()):
        lines.append("IMPORTANTE: este usuario no tiene permisos de escritura en ningun proyecto.")
    lines.append("No accedas ni modifiques proyectos fuera de esta lista.")
    return "\n".join(lines)


def _build_system_prompt(telegram_id: str) -> str:
    """Build the system prompt with date/time and user access context."""
    tz = ZoneInfo(TIMEZONE)
    now = datetime.now(tz)
    date_str = now.strftime("%Y-%m-%d (%A, %d de %B de %Y)")
    time_str = now.strftime("%H:%M")
    utc_offset = now.strftime("%z")
    utc_offset_fmt = f"{utc_offset[:3]}:{utc_offset[3:]}"
    access_context = _build_access_context(telegram_id)
    member_mapping_context = _build_member_mapping_context()
    member_mapping_block = f"{member_mapping_context}\n" if member_mapping_context else ""
    return (
        f"{SYSTEM_PROMPT_BASE}\n"
        f"{access_context}\n"
        f"{member_mapping_block}"
        f"La fecha y hora actual es: {date_str}, {time_str} (zona horaria: {TIMEZONE}, UTC{utc_offset_fmt}).\n"
        f"IMPORTANTE: Cuando el usuario indique una hora, es hora local ({TIMEZONE}). "
        f"Para el campo 'due' de las tareas, convierte siempre la hora local a UTC. "
        f"Por ejemplo, si el usuario dice '21:00' y el offset actual es UTC{utc_offset_fmt}, "
        f"debes enviar el campo due como 'YYYY-MM-DDT{_utc_example(21, utc_offset_fmt)}:00Z'."
    )


def _resolve_section_project_id(section_id: int) -> int | None:
    if section_id in _SECTION_PROJECT_CACHE:
        return _SECTION_PROJECT_CACHE[section_id]

    try:
        resp = requests.get(f"{MT_BASE_URL}/sections/{section_id}", headers=MT_HEADERS, timeout=10)
    except Exception as exc:
        logger.error("Error resolving section_id=%s: %s", section_id, exc)
        return None

    if resp.status_code != 200:
        return None

    data = resp.json()
    project_id = _safe_int(data.get("project_id"))
    if project_id is None:
        return None

    _SECTION_PROJECT_CACHE[section_id] = project_id
    return project_id


def _resolve_task_project_id(task_id: int) -> int | None:
    if task_id in _TASK_PROJECT_CACHE and task_id in _TASK_SECTION_CACHE:
        return _TASK_PROJECT_CACHE[task_id]

    try:
        resp = requests.get(f"{MT_BASE_URL}/tasks/{task_id}", headers=MT_HEADERS, timeout=10)
    except Exception as exc:
        logger.error("Error resolving task_id=%s: %s", task_id, exc)
        return None

    if resp.status_code != 200:
        return None

    data = resp.json()
    project_id = _safe_int(data.get("project_id"))
    if project_id is None:
        return None

    section_id = _safe_int(data.get("section_id"))
    if section_id is not None:
        _SECTION_PROJECT_CACHE[section_id] = project_id
        _TASK_SECTION_CACHE[task_id] = section_id
    _TASK_PROJECT_CACHE[task_id] = project_id
    return project_id


def _has_project_access(telegram_id: str, project_id: int, write: bool) -> bool:
    permission = get_user_project_permissions(telegram_id).get(project_id)
    if permission is None:
        return False
    if write and permission != "rw":
        return False
    return True


def _has_section_access(telegram_id: str, project_id: int, section_id: int, write: bool) -> bool:
    if not _has_project_access(telegram_id, project_id, write):
        return False

    allowed_sections = get_user_allowed_sections(telegram_id, project_id)
    if allowed_sections is None:
        return True
    return section_id in allowed_sections


def _validate_project_access(tool_name: str, telegram_id: str, project_id: int, write: bool) -> str | None:
    if not _has_project_access(telegram_id, project_id, write):
        action = "escritura" if write else "lectura"
        return f"Error: no tienes permiso de {action} para el proyecto {project_id} ({tool_name})."
    return None


def _validate_section_access(
    tool_name: str,
    telegram_id: str,
    project_id: int,
    section_id: int,
    write: bool,
) -> str | None:
    if not _has_section_access(telegram_id, project_id, section_id, write):
        if not _has_project_access(telegram_id, project_id, write):
            action = "escritura" if write else "lectura"
            return f"Error: no tienes permiso de {action} para el proyecto {project_id} ({tool_name})."
        action = "escritura" if write else "lectura"
        return (
            f"Error: no tienes permiso de {action} para la seccion {section_id} "
            f"del proyecto {project_id} ({tool_name})."
        )
    return None


def _validate_tool_access(tool_name: str, args: dict[str, Any], telegram_id: str) -> str | None:
    if not get_user(telegram_id):
        return "Error: usuario no autorizado."

    write = is_write_tool(tool_name)

    if "project_id" in args and args.get("project_id") not in ("", None):
        project_id = _safe_int(args.get("project_id"))
        if project_id is None:
            return "Error: project_id invalido."
        return _validate_project_access(tool_name, telegram_id, project_id, write)

    if tool_name in _SECTION_TOOLS:
        section_id = _safe_int(args.get("section_id"))
        if section_id is None:
            return "Error: section_id invalido."
        project_id = _resolve_section_project_id(section_id)
        if project_id is None:
            return f"Error: no se pudo resolver el proyecto de la seccion {section_id}."
        return _validate_section_access(tool_name, telegram_id, project_id, section_id, write)

    if tool_name == "move_task":
        task_id = _safe_int(args.get("task_id"))
        section_id = _safe_int(args.get("section_id"))
        if task_id is None or section_id is None:
            return "Error: task_id o section_id invalido."

        source_project_id = _resolve_task_project_id(task_id)
        destination_project_id = _resolve_section_project_id(section_id)
        if source_project_id is None or destination_project_id is None:
            return "Error: no se pudo validar acceso para mover la tarea."
        source_section_id = _TASK_SECTION_CACHE.get(task_id)
        if source_section_id is None:
            return "Error: no se pudo resolver la seccion de la tarea origen."

        err = _validate_section_access(tool_name, telegram_id, source_project_id, source_section_id, True)
        if err:
            return err
        return _validate_section_access(tool_name, telegram_id, destination_project_id, section_id, True)

    if tool_name == "update_task":
        task_id = _safe_int(args.get("task_id"))
        if task_id is None:
            return "Error: task_id invalido."
        task_project_id = _resolve_task_project_id(task_id)
        if task_project_id is None:
            return "Error: no se pudo resolver el proyecto de la tarea."
        task_section_id = _TASK_SECTION_CACHE.get(task_id)
        if task_section_id is None:
            return "Error: no se pudo resolver la seccion de la tarea."

        err = _validate_section_access(tool_name, telegram_id, task_project_id, task_section_id, True)
        if err:
            return err

        destination_section = _safe_int(args.get("section_id"))
        if destination_section:
            destination_project_id = _resolve_section_project_id(destination_section)
            if destination_project_id is None:
                return "Error: no se pudo resolver el proyecto de la seccion destino."
            return _validate_section_access(
                tool_name,
                telegram_id,
                destination_project_id,
                destination_section,
                True,
            )
        return None

    if tool_name in _TASK_TOOLS:
        task_id = _safe_int(args.get("task_id"))
        if task_id is None:
            return "Error: task_id invalido."
        project_id = _resolve_task_project_id(task_id)
        if project_id is None:
            return "Error: no se pudo resolver el proyecto de la tarea."
        section_id = _TASK_SECTION_CACHE.get(task_id)
        if section_id is None:
            return "Error: no se pudo resolver la seccion de la tarea."
        return _validate_section_access(tool_name, telegram_id, project_id, section_id, write)

    if tool_name in {"update_checklist_item", "delete_checklist_item"}:
        checklist_item_id = _safe_int(args.get("checklist_item_id"))
        if checklist_item_id is None:
            return "Error: checklist_item_id invalido."
        task_id = _CHECKLIST_ITEM_TASK_CACHE.get(checklist_item_id)
        if task_id is None:
            return (
                "Error: no se puede validar permisos de ese checklist_item_id aun. "
                "Primero consulta los items del checklist de la tarea."
            )
        project_id = _resolve_task_project_id(task_id)
        if project_id is None:
            return "Error: no se pudo resolver el proyecto de la tarea."
        section_id = _TASK_SECTION_CACHE.get(task_id)
        if section_id is None:
            return "Error: no se pudo resolver la seccion de la tarea."
        return _validate_section_access(tool_name, telegram_id, project_id, section_id, True)

    return None


def _remember_tool_entities(tool_name: str, args: dict[str, Any], result: str) -> None:
    result_data = _safe_json_loads(result)

    if tool_name in {"create_task", "create_task_with_checklist"} and isinstance(result_data, dict):
        task_id = _safe_int(result_data.get("id"))
        section_id = _safe_int(args.get("section_id"))
        if task_id is not None and section_id is not None:
            project_id = _resolve_section_project_id(section_id)
            if project_id is not None:
                _TASK_PROJECT_CACHE[task_id] = project_id
                _TASK_SECTION_CACHE[task_id] = section_id

    if tool_name == "get_task_checklist_items" and isinstance(result_data, list):
        task_id = _safe_int(args.get("task_id"))
        if task_id is not None:
            for item in result_data:
                if isinstance(item, dict):
                    checklist_item_id = _safe_int(item.get("id"))
                    if checklist_item_id is not None:
                        _CHECKLIST_ITEM_TASK_CACHE[checklist_item_id] = task_id

    if tool_name == "create_checklist_item" and isinstance(result_data, dict):
        checklist_item_id = _safe_int(result_data.get("id"))
        task_id = _safe_int(args.get("task_id"))
        if checklist_item_id is not None and task_id is not None:
            _CHECKLIST_ITEM_TASK_CACHE[checklist_item_id] = task_id


def _filter_tool_result(tool_name: str, result: str, telegram_id: str, args: dict[str, Any]) -> str:
    allowed_projects = get_user_project_ids(telegram_id)
    if not allowed_projects:
        return result

    data = _safe_json_loads(result)
    if data is None:
        return result

    def _can_read_section(project_id: int | None, section_id: int | None) -> bool:
        if project_id is None or project_id not in allowed_projects:
            return False

        restricted_sections = get_user_allowed_sections(telegram_id, project_id)
        if restricted_sections is None:
            return True
        if section_id is None:
            return False
        return section_id in restricted_sections

    if tool_name == "get_projects" and isinstance(data, list):
        filtered = [item for item in data if _safe_int(item.get("id")) in allowed_projects]
        return json.dumps(filtered, ensure_ascii=False)

    if tool_name == "get_sections" and isinstance(data, list):
        filtered = [
            item
            for item in data
            if _can_read_section(_safe_int(item.get("project_id")), _safe_int(item.get("id")))
        ]
        return json.dumps(filtered, ensure_ascii=False)

    if tool_name == "get_project_sections" and isinstance(data, list):
        requested_project_id = _safe_int(args.get("project_id"))
        filtered = [
            item
            for item in data
            if _can_read_section(
                _safe_int(item.get("project_id")) or requested_project_id,
                _safe_int(item.get("id")),
            )
        ]
        return json.dumps(filtered, ensure_ascii=False)

    if tool_name in {"get_all_tasks", "get_my_tasks", "search_tasks"} and isinstance(data, list):
        filtered = [
            item
            for item in data
            if _can_read_section(_safe_int(item.get("project_id")), _safe_int(item.get("section_id")))
        ]
        return json.dumps(filtered, ensure_ascii=False)

    if tool_name == "get_task" and isinstance(data, dict):
        task_project_id = _safe_int(data.get("project_id"))
        task_section_id = _safe_int(data.get("section_id"))
        if task_section_id is None:
            task_id = _safe_int(data.get("id"))
            if task_id is not None:
                task_section_id = _TASK_SECTION_CACHE.get(task_id)
        if not _can_read_section(task_project_id, task_section_id):
            return "Error: no tienes permiso para leer esa tarea."

    return result


def _call_tool(name: str, args: dict[str, Any], telegram_id: str) -> str:
    """Dispatch a validated tool call to the matching MeisterTask function."""
    func = TOOL_REGISTRY.get(name)
    if not func:
        return f"Error: herramienta '{name}' no encontrada."

    access_error = _validate_tool_access(name, args, telegram_id)
    if access_error:
        return access_error

    try:
        result = func(**args)
    except Exception as exc:
        logger.error("Tool %s failed: %s", name, exc)
        return f"Error ejecutando {name}: {exc}"

    if isinstance(result, str):
        _remember_tool_entities(name, args, result)
        return _filter_tool_result(name, result, telegram_id, args)
    return str(result)


async def _transcribe_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Download a Telegram voice/audio message and transcribe it with Whisper."""
    voice = update.message.voice or update.message.audio
    file = await context.bot.get_file(voice.file_id)

    suffix = ".ogg" if update.message.voice else ".mp3"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        await file.download_to_drive(tmp_path)

    try:
        logger.info(
            "[Audio] Transcribiendo archivo %s (%.1f KB)...",
            tmp_path.name,
            tmp_path.stat().st_size / 1024,
        )
        with open(tmp_path, "rb") as audio_file:
            transcription = ai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
            )
        text = transcription.text.strip()
        logger.info("[Audio] Transcripcion: %s", text)
        return text
    finally:
        tmp_path.unlink(missing_ok=True)


async def _process_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_text: str,
    telegram_id: str,
) -> str:
    """Core logic: send user_text through the multi-step tool-calling loop."""
    chat_id = update.effective_chat.id
    tools_for_user = get_tools_for_user(telegram_id)
    if not tools_for_user:
        reply = "No tienes permisos suficientes para usar este bot."
        await update.message.reply_text(reply)
        return reply

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    system_prompt = _build_system_prompt(telegram_id)
    logger.info("[SystemPrompt][user=%s] %s", telegram_id, system_prompt)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]

    for _round in range(MAX_TOOL_ROUNDS):
        response = ai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            tools=tools_for_user,
            tool_choice="auto",
        )

        assistant_msg = response.choices[0].message

        if not assistant_msg.tool_calls:
            reply = assistant_msg.content or "(sin respuesta)"
            logger.info("[Respuesta] chat=%s user=%s: %s", chat_id, telegram_id, reply)
            await update.message.reply_text(reply)
            return reply

        messages.append(assistant_msg)

        for tool_call in assistant_msg.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments)
            logger.info("[Accion] chat=%s user=%s tool=%s args=%s", chat_id, telegram_id, fn_name, fn_args)

            result = _call_tool(fn_name, fn_args, telegram_id)
            logger.info(
                "[Resultado] chat=%s user=%s tool=%s resultado=%s",
                chat_id,
                telegram_id,
                fn_name,
                result[:500] if isinstance(result, str) else result,
            )

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

        await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    logger.warning("[Limite] chat=%s user=%s: max rondas=%s", chat_id, telegram_id, MAX_TOOL_ROUNDS)
    reply = "Lo siento, la operacion requirio demasiados pasos. Intenta ser mas especifico."
    await update.message.reply_text(reply)
    return reply


async def _notify_admins(
    context: ContextTypes.DEFAULT_TYPE,
    user_name: str,
    user_text: str,
    bot_reply: str,
) -> None:
    """Notify admin users when a non-admin interacts with the bot."""
    admin_ids = get_admin_ids()
    if not admin_ids:
        return

    notification = (
        "-- Notificacion --\n"
        f"Usuario: {user_name}\n"
        f"Pregunta: {user_text}\n"
        f"Respuesta: {bot_reply}"
    )

    for admin_id in admin_ids:
        try:
            await context.bot.send_message(chat_id=int(admin_id), text=notification)
        except Exception as exc:
            logger.error("No se pudo notificar al admin %s: %s", admin_id, exc)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle an incoming Telegram text message."""
    user_text = update.message.text
    chat_id = update.effective_chat.id
    user = update.effective_user
    telegram_id = str(user.id) if user else ""

    logger.info("[Pregunta] chat=%s user=%s: %s", chat_id, user.first_name if user else "?", user_text)

    if not telegram_id or not get_user(telegram_id):
        logger.warning("[Auth] Acceso denegado chat=%s user_id=%s", chat_id, telegram_id or "?")
        await update.message.reply_text("No tienes acceso a este bot.")
        return

    try:
        reply = await _process_text(update, context, user_text, telegram_id)
        if telegram_id not in get_admin_ids():
            display_name = user.full_name if user and user.full_name else (user.first_name if user else telegram_id)
            await _notify_admins(context, display_name, user_text, reply)
    except Exception as exc:
        logger.error("[Error] chat=%s: %s", chat_id, exc, exc_info=True)
        try:
            await update.message.reply_text(
                f"⚠️ Ha ocurrido un error:\n{type(exc).__name__}: {exc}"
            )
        except Exception:
            logger.error("No se pudo enviar el mensaje de error al chat %s", chat_id)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle an incoming Telegram voice or audio message."""
    chat_id = update.effective_chat.id
    user = update.effective_user
    telegram_id = str(user.id) if user else ""

    logger.info("[Audio] chat=%s user=%s: mensaje de voz recibido", chat_id, user.first_name if user else "?")

    if not telegram_id or not get_user(telegram_id):
        logger.warning("[Auth] Acceso denegado chat=%s user_id=%s (voz)", chat_id, telegram_id or "?")
        await update.message.reply_text("No tienes acceso a este bot.")
        return

    try:
        user_text = await _transcribe_voice(update, context)
        if not user_text:
            await update.message.reply_text("No he podido entender el audio. Puedes repetirlo?")
            return

        logger.info("[Pregunta] chat=%s user=%s (voz): %s", chat_id, user.first_name if user else "?", user_text)
        reply = await _process_text(update, context, user_text, telegram_id)
        if telegram_id not in get_admin_ids():
            display_name = user.full_name if user and user.full_name else (user.first_name if user else telegram_id)
            await _notify_admins(context, display_name, user_text, reply)
    except Exception as exc:
        logger.error("[Error] chat=%s: %s", chat_id, exc, exc_info=True)
        try:
            await update.message.reply_text(
                f"⚠️ Ha ocurrido un error:\n{type(exc).__name__}: {exc}"
            )
        except Exception:
            logger.error("No se pudo enviar el mensaje de error al chat %s", chat_id)


async def send_daily_tasks(context: ContextTypes.DEFAULT_TYPE) -> None:
    """JobQueue callback: send today's task summary for one registered user."""
    job_data = context.job.data
    if isinstance(job_data, dict):
        telegram_id = str(job_data.get("telegram_id", "")).strip()
    else:
        telegram_id = str(job_data).strip()

    if not telegram_id:
        logger.warning("[DailyTasks] Job sin telegram_id.")
        return

    user = get_user(telegram_id)
    if not user:
        logger.warning("[DailyTasks] Usuario no registrado: %s", telegram_id)
        return

    daily_summary = user.get("daily_summary", {})
    if not daily_summary.get("enabled", False):
        logger.info("[DailyTasks] Resumen diario desactivado para user=%s", telegram_id)
        return

    allowed_projects = get_user_project_ids(telegram_id)
    selected_projects = {_safe_int(p) for p in daily_summary.get("project_ids", [])}
    selected_projects = {p for p in selected_projects if p is not None}
    selected_projects &= allowed_projects
    include_health = bool(daily_summary.get("include_health", False))

    logger.info("[DailyTasks] Comprobando tareas para user=%s...", telegram_id)

    tasks = get_tasks_due_today()
    tasks = [t for t in tasks if _safe_int(t.get("project_id")) in selected_projects]

    project_map = _build_project_map()
    health_project_ids = {
        project_id
        for project_id, project_name in project_map.items()
        if "health" in str(project_name).lower()
    }
    has_health_access = bool(allowed_projects & health_project_ids) or not health_project_ids
    health_tasks = get_health_day_tasks(TIMEZONE) if include_health and has_health_access else []

    if not tasks and not health_tasks:
        logger.info("[DailyTasks] Sin tareas para user=%s.", telegram_id)
        return

    tz = ZoneInfo(TIMEZONE)
    now_local = datetime.now(tz)
    today_str = now_local.strftime("%d/%m/%Y")
    day_name = now_local.strftime("%A")
    lines = [f"📋 Tareas para hoy ({today_str}):\n"]

    if tasks:
        tasks.sort(key=lambda t: (0, t["due"]) if "T" in t["due"] else (1, t["due"]))
        by_project: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for task in tasks:
            project_name = project_map.get(_safe_int(task.get("project_id")) or -1, "Sin proyecto")
            by_project[project_name].append(task)

        for project_name in sorted(by_project):
            lines.append(f"📁 {project_name}")
            for task in by_project[project_name]:
                due_time = ""
                due = str(task.get("due", ""))
                if "T" in due:
                    try:
                        dt = datetime.fromisoformat(due.replace("Z", "+00:00"))
                        local_dt = dt.astimezone(tz)
                        due_time = f" (⏰ {local_dt.strftime('%H:%M')})"
                    except ValueError:
                        pass
                lines.append(f"  • {task['name']}{due_time}")
            lines.append("")

    if health_tasks:
        lines.append(f"🏃🏼‍➡️🥗 ({day_name})")
        for task in health_tasks:
            lines.append(f"  • {task['name']}")

    message = "\n".join(lines).rstrip()
    logger.info(
        "[DailyTasks] Enviando %d tarea(s) a user=%s",
        len(tasks) + len(health_tasks),
        telegram_id,
    )
    await context.bot.send_message(chat_id=int(telegram_id), text=message)
