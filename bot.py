"""
Telegram bot message handler.

Key improvement over original: a multi-step tool loop.
The LLM can chain multiple tool calls (e.g. get_projects -> get_sections -> create_task)
until it produces a final text response.

Supports both text and voice messages (voice is transcribed via OpenAI Whisper).

Also includes the proactive daily-tasks callback (no LLM involved).
"""

import json
import logging
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import ContextTypes
from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL, TIMEZONE
from meistertask import TOOL_REGISTRY
from meistertask.tasks import get_health_day_tasks, get_tasks_due_today
from meistertask.projects import get_projects as _get_projects_json
from tool_schemas import TOOLS

logger = logging.getLogger(__name__)

ai_client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT_BASE = (
    "Eres Virtual Brain, un asistente que gestiona proyectos en MeisterTask. "
    "Tienes acceso a herramientas para listar proyectos, secciones, etiquetas, miembros, "
    "crear/actualizar/completar/mover/asignar tareas, buscar tareas, gestionar comentarios y más. "
    "Cuando el usuario pida algo, usa las herramientas necesarias paso a paso: "
    "primero busca el proyecto, luego la sección, y después ejecuta la acción. "
    "Cuando el usuario se refiera a la lista de la compra, busca en el proyecto 'Health' la sección 'Shopping Cart', la tarea '🛒' . Dentro se encuenta una checklist con los items de la lista de la compra."
    "Siempre que crees una tarea con fecha debe ser asignada a Adri."
    "Responde siempre en el idioma del usuario."
)


def _build_system_prompt() -> str:
    """Build the system prompt with the current date and timezone injected."""
    tz = ZoneInfo(TIMEZONE)
    now = datetime.now(tz)
    date_str = now.strftime("%Y-%m-%d (%A, %d de %B de %Y)")
    time_str = now.strftime("%H:%M")
    utc_offset = now.strftime("%z")  # e.g. "+0100" or "+0200"
    utc_offset_fmt = f"{utc_offset[:3]}:{utc_offset[3:]}"  # e.g. "+01:00"
    return (
        f"{SYSTEM_PROMPT_BASE}\n"
        f"La fecha y hora actual es: {date_str}, {time_str} (zona horaria: {TIMEZONE}, UTC{utc_offset_fmt}).\n"
        f"IMPORTANTE: Cuando el usuario indique una hora, es hora local ({TIMEZONE}). "
        f"Para el campo 'due' de las tareas, convierte siempre la hora local a UTC. "
        f"Por ejemplo, si el usuario dice '21:00' y el offset actual es UTC{utc_offset_fmt}, "
        f"debes enviar el campo due como 'YYYY-MM-DDT{_utc_example(21, utc_offset_fmt)}:00Z'."
    )


def _utc_example(local_hour: int, offset: str) -> str:
    """Return the UTC hour string for a local hour given an offset like '+01:00'."""
    sign = 1 if offset.startswith("+") else -1
    offset_hours = int(offset[1:3])
    utc_hour = (local_hour - sign * offset_hours) % 24
    return f"{utc_hour:02d}:00"

MAX_TOOL_ROUNDS = 10


def _call_tool(name: str, args: dict) -> str:
    """Dispatch a tool call to the matching MeisterTask function."""
    func = TOOL_REGISTRY.get(name)
    if not func:
        return f"Error: herramienta '{name}' no encontrada."
    try:
        return func(**args)
    except Exception as e:
        logger.error("Tool %s failed: %s", name, e)
        return f"Error ejecutando {name}: {e}"


async def _transcribe_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Download a Telegram voice/audio message and transcribe it with Whisper."""
    voice = update.message.voice or update.message.audio
    file = await context.bot.get_file(voice.file_id)

    suffix = ".ogg" if update.message.voice else ".mp3"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        await file.download_to_drive(tmp_path)

    try:
        logger.info("[Audio] Transcribiendo archivo %s (%.1f KB)...",
                     tmp_path.name, tmp_path.stat().st_size / 1024)
        with open(tmp_path, "rb") as audio_file:
            transcription = ai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
            )
        text = transcription.text.strip()
        logger.info("[Audio] Transcripción: %s", text)
        return text
    finally:
        tmp_path.unlink(missing_ok=True)


async def _process_text(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str):
    """Core logic: send user_text through the multi-step tool-calling loop."""
    chat_id = update.effective_chat.id

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    system_prompt = _build_system_prompt()
    logger.info("[SystemPrompt] %s", system_prompt)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]

    for _round in range(MAX_TOOL_ROUNDS):
        response = ai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        assistant_msg = response.choices[0].message

        if not assistant_msg.tool_calls:
            reply = assistant_msg.content or "(sin respuesta)"
            logger.info("[Respuesta] chat=%s: %s", chat_id, reply)
            await update.message.reply_text(reply)
            return

        messages.append(assistant_msg)

        for tool_call in assistant_msg.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments)
            logger.info("[Acción] chat=%s tool=%s args=%s", chat_id, fn_name, fn_args)

            result = _call_tool(fn_name, fn_args)
            logger.info("[Resultado] chat=%s tool=%s resultado=%s",
                        chat_id, fn_name,
                        result[:500] if isinstance(result, str) else result)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

        await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    logger.warning("[Límite] chat=%s: se alcanzó el máximo de rondas (%s)", chat_id, MAX_TOOL_ROUNDS)
    await update.message.reply_text(
        "Lo siento, la operación requirió demasiados pasos. Intenta ser más específico."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle an incoming Telegram text message."""
    user_text = update.message.text
    chat_id = update.effective_chat.id
    user = update.effective_user

    logger.info("[Pregunta] chat=%s user=%s: %s", chat_id, user.first_name if user else "?", user_text)

    try:
        await _process_text(update, context, user_text)
    except Exception as e:
        logger.error("[Error] chat=%s: %s", chat_id, e, exc_info=True)
        try:
            await update.message.reply_text(
                f"⚠️ Ha ocurrido un error:\n{type(e).__name__}: {e}"
            )
        except Exception:
            logger.error("No se pudo enviar el mensaje de error al chat %s", chat_id)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle an incoming Telegram voice or audio message."""
    chat_id = update.effective_chat.id
    user = update.effective_user

    logger.info("[Audio] chat=%s user=%s: mensaje de voz recibido", chat_id, user.first_name if user else "?")

    try:
        user_text = await _transcribe_voice(update, context)
        if not user_text:
            await update.message.reply_text("No he podido entender el audio. ¿Puedes repetirlo?")
            return

        logger.info("[Pregunta] chat=%s user=%s (voz): %s", chat_id, user.first_name if user else "?", user_text)
        await _process_text(update, context, user_text)
    except Exception as e:
        logger.error("[Error] chat=%s: %s", chat_id, e, exc_info=True)
        try:
            await update.message.reply_text(
                f"⚠️ Ha ocurrido un error:\n{type(e).__name__}: {e}"
            )
        except Exception:
            logger.error("No se pudo enviar el mensaje de error al chat %s", chat_id)


# ---------------------------------------------------------------------------
# Proactive daily summary (no LLM -- pure data + formatting)
# ---------------------------------------------------------------------------

def _build_project_map() -> dict[int, str]:
    """Return a {project_id: project_name} mapping from MeisterTask."""
    try:
        data = json.loads(_get_projects_json())
        if isinstance(data, list):
            return {p["id"]: p["name"] for p in data}
    except (json.JSONDecodeError, TypeError, KeyError):
        pass
    return {}


async def send_daily_tasks(context: ContextTypes.DEFAULT_TYPE) -> None:
    """JobQueue callback: send today's task summary.

    * Queries MeisterTask directly -- no LLM involved.
    * Does nothing if there are no tasks due today.
    * The target ``chat_id`` is passed via ``context.job.data``.
    """
    chat_id = context.job.data
    logger.info("[DailyTasks] Comprobando tareas para hoy (chat=%s)...", chat_id)

    tasks = get_tasks_due_today()
    health_tasks = get_health_day_tasks(TIMEZONE)
    if not tasks and not health_tasks:
        logger.info("[DailyTasks] No hay tareas programadas para hoy ni tareas de Health por dia.")
        return

    tz = ZoneInfo(TIMEZONE)
    now_local = datetime.now(tz)
    today_str = now_local.strftime("%d/%m/%Y")
    day_name = now_local.strftime("%A")
    lines = [f"📋 Tareas para hoy ({today_str}):\n"]

    if tasks:
        project_map = _build_project_map()
        
        # Sort tasks by time: those with a specific hour first (earliest to latest),
        # then those with only a date (no time) at the end.
        tasks.sort(key=lambda t: (0, t["due"]) if "T" in t["due"] else (1, t["due"]))

        by_project: dict[str, list[dict]] = defaultdict(list)
        for t in tasks:
            project_name = project_map.get(t["project_id"], "Sin proyecto")
            by_project[project_name].append(t)

    for project_name in sorted(by_project):
        lines.append(f"📁 {project_name}")
        for t in by_project[project_name]:
            due_time = ""
            if "T" in t["due"]:
                try:
                    dt = datetime.fromisoformat(t["due"].replace("Z", "+00:00"))
                    local_dt = dt.astimezone(tz)
                    due_time = f" (⏰ {local_dt.strftime('%H:%M')})"
                except ValueError:
                    pass
            lines.append(f"  • {t['name']}{due_time}")
        lines.append("")
        
    if health_tasks:
        lines.append(f"🏃🏼‍➡️🥗 ({day_name})")
        for t in health_tasks:
            lines.append(f"  • {t['name']}")

    message = "\n".join(lines).rstrip()
    logger.info("[DailyTasks] Enviando %d tarea(s) a chat=%s", len(tasks) + len(health_tasks), chat_id)
    await context.bot.send_message(chat_id=chat_id, text=message)
