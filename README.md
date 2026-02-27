# Virtual Brain

A Telegram bot running on a Raspberry Pi that manages MeisterTask projects through natural language. Send a message to the bot, an LLM interprets it, and executes the right MeisterTask API calls automatically.

## How It Works

1. You send a message to your Telegram bot (e.g. "Crea una tarea en el proyecto Marketing")
2. The LLM reads your message and decides which MeisterTask tools to call
3. It chains multiple steps automatically (find project -> find section -> create task)
4. You get a natural-language response back in Telegram

## Available Tools (22)

| Category   | Tool                         | What it does                                |
|------------|------------------------------|---------------------------------------------|
| Projects   | `get_projects`               | List all projects                           |
| Projects   | `get_project_members`        | List members of a project                   |
| Sections   | `get_sections`               | List all sections across projects           |
| Sections   | `get_project_sections`       | List sections of a specific project         |
| Labels     | `get_project_labels`         | List labels of a project                    |
| Tasks      | `get_all_tasks`              | Get tasks with filters (status, labels...) |
| Tasks      | `get_task`                   | Get a single task by ID                     |
| Tasks      | `get_section_tasks`          | Get tasks in a section                      |
| Tasks      | `get_my_tasks`               | Get tasks assigned to you                   |
| Tasks      | `search_tasks`               | Search tasks by name or notes               |
| Tasks      | `create_task`                | Create a task in a section                  |
| Tasks      | `create_task_with_checklist` | Create a task with a checklist              |
| Tasks      | `update_task`                | Update any field on a task                  |
| Tasks      | `complete_task`              | Mark a task as completed                    |
| Tasks      | `reopen_task`                | Reopen a completed task                     |
| Tasks      | `move_task`                  | Move a task to another section              |
| Tasks      | `assign_task`                | Assign a task to someone                    |
| Tasks      | `set_task_due_date`          | Set or change a due date                    |
| Tasks      | `trash_task`                 | Send a task to trash                        |
| Comments   | `get_task_comments`          | Get comments on a task                      |
| Comments   | `create_comment`             | Add a comment (Markdown supported)          |
| Persons    | `get_person`                 | Get person details by ID                    |

## Project Structure

```
virtual_brain/
  main.py                 # Entry point
  config.py               # Loads tokens and API config from .env
  bot.py                  # Telegram message handler with multi-step tool loop
  tool_schemas.py         # OpenAI function-calling definitions (all 22 tools)
  meistertask/
    __init__.py           # Tool registry: maps function names to callables
    projects.py           # Project functions
    sections.py           # Section functions
    labels.py             # Label functions
    tasks.py              # Task CRUD + convenience functions
    comments.py           # Comment functions
    persons.py            # Person functions
  requirements.txt        # Python dependencies
  .env.example            # Template for your API tokens
  setup.sh                # One-command setup script
```

## General Setup

python3 -m venv .virtual-brain-env && source .virtual-brain-env/bin/activate && pip install -r requirements.txt

## Setup on Raspberry Pi

### Prerequisites

- Raspberry Pi with Raspberry Pi OS (or any Debian-based Linux)
- Python 3.10 or newer (`python3 --version` to check)
- Internet connection

### 1. Copy the project

Copy the `virtual_brain/` folder to your Raspberry Pi (via USB, SCP, or directly).

### 2. Run the setup script

```bash
cd ~/virtual_brain
chmod +x setup.sh
./setup.sh
```

This creates a virtual environment and installs all dependencies.

### 3. Configure your tokens

Edit the `.env` file the setup script created:

```bash
nano .env
```

Fill in your three tokens:

```
OPENAI_API_KEY=sk-...
TELEGRAM_TOKEN=123456:ABC-DEF...
MEISTERTASK_TOKEN=your_meistertask_token
```

#### Where to get each token

| Token              | Where to get it                                                                                                  |
|--------------------|------------------------------------------------------------------------------------------------------------------|
| `OPENAI_API_KEY`   | [platform.openai.com/api-keys](https://platform.openai.com/api-keys)                                            |
| `TELEGRAM_TOKEN`   | Message [@BotFather](https://t.me/BotFather) on Telegram, use `/newbot`                                         |
| `MEISTERTASK_TOKEN`| Create a personal access token at [MindMeister API](https://developers.mindmeister.com/docs/register-application) with scopes `userinfo.profile`, `userinfo.email`, and `meistertask` |

### 4. Start the bot

```bash
.venv/bin/python main.py
```

You should see:

```
Virtual Brain conectado a MeisterTask...
```

Now open Telegram and send a message to your bot.

## Usage Examples

| You say in Telegram                                           | What happens                                         |
|---------------------------------------------------------------|------------------------------------------------------|
| "Muéstrame mis proyectos"                                    | Lists all your MeisterTask projects                  |
| "Crea una tarea 'Revisar diseño' en el proyecto Marketing"   | Finds the project, picks the first section, creates it |
| "¿Qué tareas tengo asignadas?"                               | Shows your open assigned tasks                       |
| "Completa la tarea 'Enviar propuesta'"                       | Searches for it and marks it completed               |
| "Mueve la tarea 'Bug login' a la columna Done"               | Finds the task and moves it to the Done section      |
| "Añade un comentario a la tarea 12345: Revisado, todo OK"    | Adds a Markdown comment to that task                 |
| "¿Quiénes están en el proyecto Desarrollo?"                  | Lists project members with names and emails          |
| "Crea una tarea con checklist: comprar pan, leche, huevos"   | Creates a task with a checklist                      |
| "Asigna la tarea 'Deploy' a María"                           | Finds the person and assigns the task                |
| "Pon fecha límite 2026-03-01 a la tarea 'Entrega final'"    | Sets the due date                                    |

## Running on Startup (optional)

To have the bot start automatically when the Raspberry Pi boots, create a systemd service:

```bash
sudo nano /etc/systemd/system/virtual-brain.service
```

Paste:

```ini
[Unit]
Description=Virtual Brain Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/virtual_brain
ExecStart=/home/pi/virtual_brain/.venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable virtual-brain
sudo systemctl start virtual-brain
```

Check status anytime with:

```bash
sudo systemctl status virtual-brain
```

## Changing the LLM Model

By default the bot uses `gpt-4o-mini`. To change it, edit `.env`:

```
OPENAI_MODEL=gpt-4o
```

Any OpenAI model that supports function calling will work.
