"""
OpenAI function-calling tool definitions for every MeisterTask tool.
Import TOOLS from here and pass it to the chat completions API.
"""

TOOLS = [
    # --- PROJECTS ---
    {
        "type": "function",
        "function": {
            "name": "get_projects",
            "description": "Lista todos los proyectos de MeisterTask. Usa esto primero para obtener los IDs de proyecto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["active", "archived", "all"],
                        "description": "Filtrar por estado. Por defecto: active."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_project_members",
            "description": "Obtiene los miembros de un proyecto (personas con acceso).",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer", "description": "ID del proyecto."}
                },
                "required": ["project_id"]
            }
        }
    },

    # --- SECTIONS ---
    {
        "type": "function",
        "function": {
            "name": "get_sections",
            "description": "Lista todas las secciones (columnas) de todos los proyectos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["active", "trashed", "all"],
                        "description": "Filtrar por estado. Por defecto: active."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_project_sections",
            "description": "Lista las secciones (columnas) de un proyecto específico usando su ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer", "description": "ID del proyecto."}
                },
                "required": ["project_id"]
            }
        }
    },

    # --- LABELS ---
    {
        "type": "function",
        "function": {
            "name": "get_project_labels",
            "description": "Obtiene las etiquetas (labels) de un proyecto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer", "description": "ID del proyecto."}
                },
                "required": ["project_id"]
            }
        }
    },

    # --- TASKS: READ ---
    {
        "type": "function",
        "function": {
            "name": "get_all_tasks",
            "description": "Obtiene tareas de todos los proyectos con filtros opcionales.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["open", "completed", "completed_archived", "trashed"],
                        "description": "Filtrar por estado de tarea."
                    },
                    "assigned_to_me": {
                        "type": "string",
                        "enum": ["true", "false"],
                        "description": "Si es 'true', solo tareas asignadas al usuario actual."
                    },
                    "labels": {
                        "type": "string",
                        "description": "IDs de etiquetas separados por comas (ej: '1,2,3')."
                    },
                    "sort": {
                        "type": "string",
                        "description": "Orden (ej: 'name-asc', 'due-desc', 'created_at-desc')."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_task",
            "description": "Obtiene los detalles completos de una tarea por su ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "ID de la tarea."}
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_section_tasks",
            "description": "Obtiene todas las tareas dentro de una sección específica. Soport ordenamiento por cualquier campo (ej: due, created_at, name)",
            "parameters": {
                "type": "object",
                "properties": {
                    "section_id": {"type": "integer", "description": "ID de la sección."},
                    "status": {
                        "type": "string",
                        "enum": ["open", "completed", "completed_archived", "trashed"],
                        "description": "Filtrar por estado."
                    },
                    "sort": {
                        "type": "string",
                        "description": "Orden de resultados. Usar el nombre de campo (ej: 'due', 'created_at', 'name'). Prefijo '-' para descendente (ej: 'due'). Múltiples campos separados por coma (ej: 'due,-name')."
                    }
                },
                "required": ["section_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_tasks",
            "description": "Obtiene todas las tareas abiertas asignadas al usuario actual."
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_tasks",
            "description": "Busca tareas por nombre o descripción en todos los proyectos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Texto a buscar (no distingue mayúsculas)."},
                    "status": {
                        "type": "string",
                        "enum": ["open", "completed", "completed_archived", "trashed"],
                        "description": "Filtrar por estado. Por defecto: open."
                    }
                },
                "required": ["query"]
            }
        }
    },

    # --- TASKS: CREATE ---
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Crea una nueva tarea en una sección de MeisterTask.",
            "parameters": {
                "type": "object",
                "properties": {
                    "section_id": {"type": "integer", "description": "ID de la sección donde crear la tarea."},
                    "name": {"type": "string", "description": "Nombre/título de la tarea."},
                    "notes": {"type": "string", "description": "Descripción de la tarea (soporta Markdown)."},
                    "assigned_to_id": {"type": "integer", "description": "ID de la persona a asignar. 0 = sin asignar."},
                    "due": {"type": "string", "description": "Fecha/hora límite. Formato YYYY-MM-DD para solo fecha, o YYYY-MM-DDTHH:MM:SSZ para fecha y hora."},
                    "label_ids": {"type": "string", "description": "IDs de etiquetas separados por comas."}
                },
                "required": ["section_id", "name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_task_with_checklist",
            "description": "Crea una tarea con una lista de verificación (checklist).",
            "parameters": {
                "type": "object",
                "properties": {
                    "section_id": {"type": "integer", "description": "ID de la sección."},
                    "name": {"type": "string", "description": "Nombre de la tarea."},
                    "notes": {"type": "string", "description": "Descripción."},
                    "checklist_name": {"type": "string", "description": "Título del checklist. Por defecto: 'Checklist'."},
                    "checklist_items": {"type": "string", "description": "Items separados por comas (ej: 'Paso 1, Paso 2, Paso 3')."}
                },
                "required": ["section_id", "name", "checklist_items"]
            }
        }
    },

    # --- TASKS: UPDATE ---
    {
        "type": "function",
        "function": {
            "name": "update_task",
            "description": "Actualiza campos de una tarea existente. Solo los campos proporcionados se modifican.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "ID de la tarea."},
                    "name": {"type": "string", "description": "Nuevo nombre."},
                    "notes": {"type": "string", "description": "Nueva descripción."},
                    "assigned_to_id": {"type": "integer", "description": "Nuevo asignado. 0 = desasignar."},
                    "due": {"type": "string", "description": "Nueva fecha/hora límite. Formato YYYY-MM-DD para solo fecha, o YYYY-MM-DDTHH:MM:SSZ para fecha y hora."},
                    "status": {"type": "integer", "description": "1=abierta, 2=completada, 8=papelera."},
                    "section_id": {"type": "integer", "description": "Mover a otra sección."}
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "complete_task",
            "description": "Marca una tarea como completada.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "ID de la tarea a completar."}
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reopen_task",
            "description": "Reabre una tarea completada (vuelve a estado abierta).",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "ID de la tarea a reabrir."}
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_task",
            "description": "Mueve una tarea a otra sección (columna) del proyecto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "ID de la tarea."},
                    "section_id": {"type": "integer", "description": "ID de la sección destino."}
                },
                "required": ["task_id", "section_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "assign_task",
            "description": "Asigna una tarea a una persona. Usa person_id=0 para desasignar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "ID de la tarea."},
                    "person_id": {"type": "integer", "description": "ID de la persona. 0 = desasignar."}
                },
                "required": ["task_id", "person_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_task_due_date",
            "description": "Establece o cambia la fecha límite de una tarea.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "ID de la tarea."},
                    "due": {"type": "string", "description": "Fecha/hora límite. Formato YYYY-MM-DD para solo fecha, o YYYY-MM-DDTHH:MM:SSZ para fecha y hora."}
                },
                "required": ["task_id", "due"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "trash_task",
            "description": "Envía una tarea a la papelera.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "ID de la tarea."}
                },
                "required": ["task_id"]
            }
        }
    },

    # --- CHECKLISTS ---
    {
        "type": "function",
        "function": {
            "name": "get_task_checklist_items",
            "description": "Obtiene todos los items del checklist de una tarea. Cada item indica si está marcado (checked) o no.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "ID de la tarea."}
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_checklist_item",
            "description": "Añade un nuevo item al checklist de una tarea existente. Si la tarea no tiene checklist, se crea automáticamente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "ID de la tarea."},
                    "name": {"type": "string", "description": "Texto del item del checklist."},
                    "checked": {
                        "type": "string",
                        "enum": ["true", "false"],
                        "description": "Si es 'true', el item se crea ya marcado. Por defecto: 'false'."
                    }
                },
                "required": ["task_id", "name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_checklist_item",
            "description": "Actualiza un item de checklist existente: cambiar nombre, marcar como completado o desmarcar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "checklist_item_id": {"type": "integer", "description": "ID del item del checklist (obtenido con get_task_checklist_items)."},
                    "name": {"type": "string", "description": "Nuevo texto del item. Omitir para no cambiar."},
                    "checked": {
                        "type": "string",
                        "enum": ["true", "false"],
                        "description": "'true' para marcar como completado, 'false' para desmarcar."
                    }
                },
                "required": ["checklist_item_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_checklist_item",
            "description": "Elimina un item del checklist de una tarea.",
            "parameters": {
                "type": "object",
                "properties": {
                    "checklist_item_id": {"type": "integer", "description": "ID del item del checklist a eliminar (obtenido con get_task_checklist_items)."}
                },
                "required": ["checklist_item_id"]
            }
        }
    },

    # --- COMMENTS ---
    {
        "type": "function",
        "function": {
            "name": "get_task_comments",
            "description": "Obtiene todos los comentarios de una tarea.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "ID de la tarea."}
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_comment",
            "description": "Añade un comentario a una tarea (soporta Markdown).",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "ID de la tarea."},
                    "text": {"type": "string", "description": "Texto del comentario."}
                },
                "required": ["task_id", "text"]
            }
        }
    },

    # --- PERSONS ---
    {
        "type": "function",
        "function": {
            "name": "get_person",
            "description": "Obtiene los datos de una persona (nombre, email) por su ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "person_id": {"type": "integer", "description": "ID de la persona."}
                },
                "required": ["person_id"]
            }
        }
    },
]
