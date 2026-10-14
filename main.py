"""
Pocket Agent - Autonomous AI Mobile Agent Application
Pure Python Flet (0.25.2) Android Architecture with Direct Gemini REST API
Zero C/Rust extension dependencies (pydantic-free, pure standard library)
"""

import ast
import datetime
import json
import math
import operator
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional

import flet as ft

# ==========================================
# CONSTANTS & CONFIGURATION
# ==========================================
DEFAULT_SYSTEM_INSTRUCTION = (
    "You are Pocket Agent, an elite autonomous executive AI assistant and mobile operations specialist. "
    "You run locally on an Android device for Waqar Piracha (Senior Business Intelligence & Automation Specialist). "
    "You have direct access to native tools: "
    "1) `get_device_datetime`: Read current device clock and date. "
    "2) `save_note` & `read_notes`: Manage local device notes and tasks. "
    "3) `quick_calculator`: Safely compute mathematical and load formulas. "
    "4) `query_working_knowledge`: Search Second Brain and operational knowledge base. "
    "5) `save_to_second_brain`: Record ideas, audit logs, or operational entries into Second Brain. "
    "Proactively invoke your tools whenever relevant. Respond with structured, executive-grade Markdown "
    "with bold highlights, bullet points, tables, and formatted code snippets where helpful."
)

STORAGE_KEY_API_KEY = "pocket_agent_gemini_api_key"
STORAGE_KEY_SYSTEM_PROMPT = "pocket_agent_system_prompt"
STORAGE_KEY_CHAT_HISTORY = "pocket_agent_chat_history"
STORAGE_KEY_NOTES = "pocket_agent_notes"
STORAGE_KEY_BRAIN_URL = "pocket_agent_second_brain_url"
DEFAULT_BRAIN_URL = "https://script.google.com/macros/s/AKfycbz_bridge/exec"

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

# ==========================================
# SAFE MATHEMATICAL EVALUATOR (AST-BASED)
# ==========================================
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

SAFE_FUNCTIONS = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "abs": abs,
    "round": round,
    "ceil": math.ceil,
    "floor": math.floor,
}

SAFE_CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
}


def _eval_ast_node(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Unsupported constant type: {type(node.value)}")
    elif isinstance(node, ast.Name):
        if node.id in SAFE_CONSTANTS:
            return SAFE_CONSTANTS[node.id]
        raise ValueError(f"Unknown variable: {node.id}")
    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type in SAFE_OPERATORS:
            left = _eval_ast_node(node.left)
            right = _eval_ast_node(node.right)
            return SAFE_OPERATORS[op_type](left, right)
        raise ValueError(f"Unsupported binary operator: {op_type}")
    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type in SAFE_OPERATORS:
            operand = _eval_ast_node(node.operand)
            return SAFE_OPERATORS[op_type](operand)
        raise ValueError(f"Unsupported unary operator: {op_type}")
    elif isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in SAFE_FUNCTIONS:
            func = SAFE_FUNCTIONS[node.func.id]
            args = [_eval_ast_node(arg) for arg in node.args]
            return func(*args)
        raise ValueError(f"Unsupported function call: {ast.dump(node)}")
    raise ValueError(f"Unsupported syntax expression: {type(node).__name__}")


def evaluate_math_expression(expression: str) -> str:
    """Safely evaluates mathematical expressions without arbitrary code execution."""
    try:
        cleaned_expr = expression.strip()
        parsed = ast.parse(cleaned_expr, mode="eval")
        result = _eval_ast_node(parsed.body)
        return str(result)
    except Exception as e:
        return f"Error evaluating expression '{expression}': {str(e)}"


# ==========================================
# GEMINI TOOL DECLARATIONS (FUNCTION CALLING)
# ==========================================
GEMINI_FUNCTION_DECLARATIONS = [
    {
        "name": "get_device_datetime",
        "description": "Returns the current local date, time, and day of the week on the device.",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        },
    },
    {
        "name": "save_note",
        "description": "Saves a personal task, note, or reminder locally on the mobile device.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {
                    "type": "STRING",
                    "description": "The title or subject of the note.",
                },
                "content": {
                    "type": "STRING",
                    "description": "The body text or details of the note.",
                },
            },
            "required": ["title", "content"],
        },
    },
    {
        "name": "read_notes",
        "description": "Retrieves and lists all persistent tasks and notes saved on the mobile device.",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        },
    },
    {
        "name": "quick_calculator",
        "description": "Safely evaluates mathematical or engineering expressions (e.g., '(240*15*0.8)/1000' or 'sqrt(144)+25').",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "expression": {
                    "type": "STRING",
                    "description": "The mathematical formula string to evaluate.",
                }
            },
            "required": ["expression"],
        },
    },
    {
        "name": "query_working_knowledge",
        "description": "Queries Waqar's Google Drive AI Second Brain bridge for SOPs, supply chain patterns, bot catalogs, and notes.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "search_keyword": {
                    "type": "STRING",
                    "description": "Keyword or topic to search across the Second Brain knowledge base.",
                }
            },
            "required": ["search_keyword"],
        },
    },
    {
        "name": "save_to_second_brain",
        "description": "Appends a new note, project milestone, or operational observation to the Google Drive Second Brain.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "topic": {
                    "type": "STRING",
                    "description": "Category or topic (e.g., 'Kinaxis', 'SAP', 'Idea', 'Meeting').",
                },
                "content": {
                    "type": "STRING",
                    "description": "The content or observation to record.",
                },
            },
            "required": ["topic", "content"],
        },
    },
]


# ==========================================
# MAIN APPLICATION CONTROLLER
# ==========================================
def main(page: ft.Page):
    page.title = "Pocket Agent"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.spacing = 0
    page.bgcolor = "#0D1117"

    page.theme = ft.Theme(
        color_scheme_seed="#3B82F6",
        visual_density=ft.ThemeVisualDensity.COMPACT,
    )

    # ------------------------------------------
    # STATE MANAGEMENT
    # ------------------------------------------
    tools_executed_in_turn: List[str] = []

    def get_stored_api_key() -> str:
        return page.client_storage.get(STORAGE_KEY_API_KEY) or ""

    def get_stored_system_prompt() -> str:
        return page.client_storage.get(STORAGE_KEY_SYSTEM_PROMPT) or DEFAULT_SYSTEM_INSTRUCTION

    def get_stored_chat_history() -> List[Dict[str, Any]]:
        return page.client_storage.get(STORAGE_KEY_CHAT_HISTORY) or []

    def save_chat_history_to_storage(history: List[Dict[str, Any]]):
        page.client_storage.set(STORAGE_KEY_CHAT_HISTORY, history)

    def get_stored_notes() -> Dict[str, Any]:
        return page.client_storage.get(STORAGE_KEY_NOTES) or {}

    def save_notes_to_storage(notes: Dict[str, Any]):
        page.client_storage.set(STORAGE_KEY_NOTES, notes)

    def get_second_brain_url() -> str:
        return page.client_storage.get(STORAGE_KEY_BRAIN_URL) or DEFAULT_BRAIN_URL

    # ------------------------------------------
    # TOOL EXECUTION IMPLEMENTATIONS
    # ------------------------------------------
    def exec_get_device_datetime(args: Dict[str, Any]) -> str:
        now = datetime.datetime.now()
        return now.strftime("%A, %B %d, %Y - %I:%M:%S %p")

    def exec_save_note(args: Dict[str, Any]) -> str:
        title = args.get("title", "Untitled").strip()
        content = args.get("content", "").strip()
        notes = get_stored_notes()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        notes[title] = {
            "content": content,
            "updated_at": timestamp,
        }
        save_notes_to_storage(notes)
        return f"Successfully saved note '{title}' on device at {timestamp}."

    def exec_read_notes(args: Dict[str, Any]) -> str:
        notes = get_stored_notes()
        if not notes:
            return "No notes or tasks found on this device."
        lines = [f"Found {len(notes)} note(s) in local storage:\n"]
        for idx, (title, data) in enumerate(notes.items(), start=1):
            body = data.get("content", "")
            updated = data.get("updated_at", "N/A")
            lines.append(f"{idx}. **{title}** (Updated: {updated})\n   {body}\n")
        return "\n".join(lines)

    def exec_quick_calculator(args: Dict[str, Any]) -> str:
        expr = args.get("expression", "")
        return evaluate_math_expression(expr)

    def exec_query_working_knowledge(args: Dict[str, Any]) -> str:
        keyword = args.get("search_keyword", "").strip()
        url = get_second_brain_url()
        try:
            params = urllib.parse.urlencode({"action": "query", "q": keyword})
            req = urllib.request.Request(
                f"{url}?{params}",
                headers={"User-Agent": "PocketAgent-Android/1.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read().decode("utf-8", errors="replace")
                return f"Second Brain Query Results for '{keyword}':\n{data[:800]}"
        except Exception as e:
            # Fallback to local offline notes search
            notes = get_stored_notes()
            matching = [f"**{t}**: {d.get('content')}" for t, d in notes.items() if keyword.lower() in t.lower() or keyword.lower() in d.get("content", "").lower()]
            if matching:
                return f"(Offline Mode) Matching local device notes for '{keyword}':\n" + "\n".join(matching)
            return f"Second Brain bridge notice: Unable to contact cloud endpoint ({str(e)}). No local notes matched '{keyword}'."

    def exec_save_to_second_brain(args: Dict[str, Any]) -> str:
        topic = args.get("topic", "General")
        content = args.get("content", "")
        url = get_second_brain_url()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Always save locally on device first
        exec_save_note({"title": f"[{topic}] {timestamp}", "content": content})
        
        try:
            payload = json.dumps({"action": "save", "topic": topic, "content": content, "timestamp": timestamp}).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "PocketAgent-Android/1.0"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return f"Successfully saved to Second Brain and synced locally (HTTP {resp.getcode()})."
        except Exception as e:
            return f"Saved locally on device. Cloud sync deferred ({str(e)})."

    DISPATCH_TOOL_MAP = {
        "get_device_datetime": exec_get_device_datetime,
        "save_note": exec_save_note,
        "read_notes": exec_read_notes,
        "quick_calculator": exec_quick_calculator,
        "query_working_knowledge": exec_query_working_knowledge,
        "save_to_second_brain": exec_save_to_second_brain,
    }

    # ------------------------------------------
    # DIRECT GEMINI REST API CLIENT
    # ------------------------------------------
    def call_gemini_rest_api(contents_payload: List[Dict[str, Any]], system_prompt: str, api_key: str) -> Dict[str, Any]:
        endpoint = f"{GEMINI_API_BASE}?key={api_key}"
        payload = {
            "system_instruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": contents_payload,
            "tools": [
                {"function_declarations": GEMINI_FUNCTION_DECLARATIONS}
            ],
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 2048,
            },
        }

        encoded_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=encoded_data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "PocketAgent-Android/1.0",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            raw_response = resp.read().decode("utf-8")
            return json.loads(raw_response)

    def execute_agent_multi_turn(user_message: str) -> str:
        api_key = get_stored_api_key()
        if not api_key:
            raise ValueError("Gemini API key is not configured. Please open Settings to enter your API key.")

        system_instruction = get_stored_system_prompt()
        history = get_stored_chat_history()

        # Build contents array from recent chat history (last 16 messages)
        contents: List[Dict[str, Any]] = []
        for item in history[-16:]:
            role = item.get("role", "user")
            text = item.get("text", "")
            if text:
                contents.append({
                    "role": "user" if role == "user" else "model",
                    "parts": [{"text": text}],
                })

        # Append current user prompt
        contents.append({
            "role": "user",
            "parts": [{"text": user_message}],
        })

        # Multi-turn tool execution loop (up to 5 function-calling hops)
        for _ in range(5):
            api_result = call_gemini_rest_api(contents, system_instruction, api_key)
            candidates = api_result.get("candidates", [])
            if not candidates:
                return "No response received from Gemini API."

            first_candidate = candidates[0]
            model_content = first_candidate.get("content", {})
            parts = model_content.get("parts", [])

            # Check if Gemini invoked a function call
            function_call = None
            text_response = ""
            for part in parts:
                if "functionCall" in part:
                    function_call = part["functionCall"]
                if "text" in part:
                    text_response += part["text"]

            if not function_call:
                # Terminal text answer reached
                return text_response or "*(Agent executed operations successfully)*"

            # Execute tool call
            fn_name = function_call.get("name", "")
            fn_args = function_call.get("args", {})
            tools_executed_in_turn.append(fn_name)

            # Update UI indicator
            tool_status_text.value = f"Executing tool: {fn_name}..."
            tool_badge.visible = True
            page.update()

            handler = DISPATCH_TOOL_MAP.get(fn_name)
            if handler:
                try:
                    tool_output = handler(fn_args)
                except Exception as err:
                    tool_output = f"Tool '{fn_name}' execution error: {str(err)}"
            else:
                tool_output = f"Unknown tool: '{fn_name}'."

            # Append assistant's function call and user's function response to conversation
            contents.append({
                "role": "model",
                "parts": [{"functionCall": {"name": fn_name, "args": fn_args}}],
            })
            contents.append({
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "name": fn_name,
                            "response": {"output": str(tool_output)},
                        }
                    }
                ],
            })

        return "Agent completed multi-turn tool operations."

    # ------------------------------------------
    # UI COMPONENTS
    # ------------------------------------------
    chat_list = ft.ListView(
        expand=True,
        spacing=14,
        padding=ft.padding.symmetric(horizontal=16, vertical=16),
        auto_scroll=True,
    )

    tool_status_text = ft.Text(
        value="",
        color="#93C5FD",
        size=12,
        weight=ft.FontWeight.W_500,
        expand=True,
    )

    tool_badge = ft.Container(
        visible=False,
        bgcolor="#1E293B",
        border_radius=12,
        padding=ft.padding.symmetric(horizontal=12, vertical=8),
        margin=ft.padding.symmetric(horizontal=16, vertical=4),
        border=ft.border.all(1, "#334155"),
        content=ft.Row(
            controls=[
                ft.ProgressRing(width=14, height=14, stroke_width=2, color="#60A5FA"),
                ft.Icon(name=ft.Icons.AUTO_AWESOME_ROUNDED, size=15, color="#F59E0B"),
                tool_status_text,
            ],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        ),
    )

    def create_message_bubble(role: str, text: str, timestamp: str = "", tools_used: List[str] = None) -> ft.Control:
        is_user = (role == "user")
        tools_row = None
        if tools_used and not is_user:
            tool_chips = [
                ft.Container(
                    bgcolor="#1E293B",
                    border=ft.border.all(1, "#38BDF8"),
                    border_radius=8,
                    padding=ft.padding.symmetric(horizontal=8, vertical=3),
                    content=ft.Row(
                        controls=[
                            ft.Icon(name=ft.Icons.BOLT_ROUNDED, size=12, color="#38BDF8"),
                            ft.Text(f"tool: {tool}", size=11, color="#BAE6FD", weight=ft.FontWeight.W_600),
                        ],
                        spacing=4,
                        tight=True,
                    ),
                )
                for tool in tools_used
            ]
            tools_row = ft.Row(controls=tool_chips, wrap=True, spacing=6)

        if is_user:
            bubble_content = ft.Column(
                controls=[
                    ft.Text(value=text, color="#FFFFFF", size=15, selectable=True),
                    ft.Text(value=timestamp, color="#93C5FD", size=10, text_align=ft.TextAlign.RIGHT),
                ],
                tight=True,
                spacing=4,
                horizontal_alignment=ft.CrossAxisAlignment.END,
            )

            bubble_container = ft.Container(
                content=bubble_content,
                bgcolor="#2563EB",
                border_radius=ft.border_radius.only(top_left=16, top_right=4, bottom_left=16, bottom_right=16),
                padding=ft.padding.symmetric(horizontal=14, vertical=10),
                shadow=ft.BoxShadow(spread_radius=1, blur_radius=6, color="#1E3A8A44", offset=ft.Offset(0, 2)),
            )

            return ft.Row(
                controls=[
                    ft.Container(expand=True),
                    bubble_container,
                    ft.CircleAvatar(
                        content=ft.Icon(name=ft.Icons.PERSON_ROUNDED, size=18, color="#FFFFFF"),
                        bgcolor="#1D4ED8",
                        radius=16,
                    ),
                ],
                alignment=ft.MainAxisAlignment.END,
                vertical_alignment=ft.CrossAxisAlignment.START,
                spacing=8,
            )
        else:
            column_items = []
            if tools_row:
                column_items.append(tools_row)

            column_items.append(
                ft.Markdown(
                    value=text,
                    selectable=True,
                    extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                    code_theme="atom-one-dark",
                    code_style=ft.TextStyle(font_family="monospace", size=13, color="#A7F3D0"),
                )
            )

            if timestamp:
                column_items.append(ft.Text(value=timestamp, color="#64748B", size=10))

            bubble_container = ft.Container(
                content=ft.Column(controls=column_items, tight=True, spacing=6),
                bgcolor="#161B22",
                border_radius=ft.border_radius.only(top_left=4, top_right=16, bottom_left=16, bottom_right=16),
                border=ft.border.all(1, "#30363D"),
                padding=ft.padding.symmetric(horizontal=14, vertical=12),
                shadow=ft.BoxShadow(spread_radius=1, blur_radius=8, color="#00000066", offset=ft.Offset(0, 3)),
                expand=True,
            )

            return ft.Row(
                controls=[
                    ft.CircleAvatar(
                        content=ft.Icon(name=ft.Icons.SMART_TOY_ROUNDED, size=18, color="#38BDF8"),
                        bgcolor="#0F172A",
                        radius=16,
                    ),
                    bubble_container,
                ],
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.START,
                spacing=8,
            )

    def render_chat_history():
        chat_list.controls.clear()
        saved_history = get_stored_chat_history()
        if not saved_history:
            chat_list.controls.append(
                ft.Container(
                    alignment=ft.alignment.center,
                    padding=ft.padding.symmetric(vertical=30, horizontal=20),
                    content=ft.Column(
                        controls=[
                            ft.Icon(name=ft.Icons.ROBOT_ROUNDED, size=48, color="#38BDF8"),
                            ft.Text("Pocket Agent Online", size=20, weight=ft.FontWeight.BOLD, color="#F8FAFC"),
                            ft.Text(
                                "Autonomous on-device assistant powered by Gemini 2.5 Flash.\n"
                                "Direct REST API with zero native compilation dependencies.",
                                size=13,
                                color="#94A3B8",
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Container(height=10),
                            ft.OutlinedButton(
                                text="Configure API Key",
                                icon=ft.Icons.KEY_ROUNDED,
                                on_click=lambda e: open_settings_dialog(e),
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                    ),
                )
            )
        else:
            for item in saved_history:
                bubble = create_message_bubble(
                    role=item.get("role", "user"),
                    text=item.get("text", ""),
                    timestamp=item.get("timestamp", ""),
                    tools_used=item.get("tools_used", []),
                )
                chat_list.controls.append(bubble)
        page.update()

    def confirm_clear_chat(e):
        def perform_clear(ev):
            page.client_storage.remove(STORAGE_KEY_CHAT_HISTORY)
            close_dialog(ev)
            render_chat_history()
            page.snack_bar = ft.SnackBar(content=ft.Text("Chat history cleared."), bgcolor="#1E293B")
            page.snack_bar.open = True
            page.update()

        confirm_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Clear Chat History?"),
            content=ft.Text("This will erase conversational history. Local notes and Second Brain records are preserved."),
            actions=[
                ft.TextButton("Cancel", on_click=lambda ev: close_dialog(ev)),
                ft.TextButton("Clear All", on_click=perform_clear, style=ft.ButtonStyle(color="#EF4444")),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.dialog = confirm_dialog
        confirm_dialog.open = True
        page.update()

    def close_dialog(e):
        if page.dialog:
            page.dialog.open = False
            page.update()

    # ------------------------------------------
    # SETTINGS MODAL
    # ------------------------------------------
    api_key_field = ft.TextField(
        label="Gemini API Key",
        password=True,
        can_reveal_password=True,
        hint_text="AIzaSy...",
        border_color="#3B82F6",
        prefix_icon=ft.Icons.VPN_KEY_ROUNDED,
        bgcolor="#0F172A",
    )

    system_prompt_field = ft.TextField(
        label="Agent Persona / System Instruction",
        multiline=True,
        min_lines=3,
        max_lines=6,
        border_color="#3B82F6",
        bgcolor="#0F172A",
    )

    brain_url_field = ft.TextField(
        label="Second Brain Bridge URL (Google Apps Script / Webhook)",
        hint_text="https://script.google.com/macros/s/.../exec",
        border_color="#3B82F6",
        prefix_icon=ft.Icons.CLOUD_SYNC_ROUNDED,
        bgcolor="#0F172A",
    )

    def save_settings(e):
        key = api_key_field.value.strip()
        prompt = system_prompt_field.value.strip() or DEFAULT_SYSTEM_INSTRUCTION
        brain_url = brain_url_field.value.strip() or DEFAULT_BRAIN_URL

        page.client_storage.set(STORAGE_KEY_API_KEY, key)
        page.client_storage.set(STORAGE_KEY_SYSTEM_PROMPT, prompt)
        page.client_storage.set(STORAGE_KEY_BRAIN_URL, brain_url)

        close_dialog(e)
        page.snack_bar = ft.SnackBar(content=ft.Text("Settings saved successfully!"), bgcolor="#10B981")
        page.snack_bar.open = True
        page.update()

    def reset_prompt(e):
        system_prompt_field.value = DEFAULT_SYSTEM_INSTRUCTION
        page.update()

    def open_settings_dialog(e):
        api_key_field.value = get_stored_api_key()
        system_prompt_field.value = get_stored_system_prompt()
        brain_url_field.value = get_second_brain_url()

        settings_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                controls=[
                    ft.Icon(name=ft.Icons.TUNE_ROUNDED, color="#38BDF8"),
                    ft.Text("Agent Settings", weight=ft.FontWeight.BOLD),
                ],
                spacing=8,
            ),
            content=ft.Container(
                width=350,
                content=ft.Column(
                    controls=[
                        api_key_field,
                        ft.Container(height=4),
                        system_prompt_field,
                        ft.Row(
                            controls=[
                                ft.TextButton(
                                    "Reset Persona",
                                    icon=ft.Icons.RESTORE_ROUNDED,
                                    on_click=reset_prompt,
                                    style=ft.ButtonStyle(color="#94A3B8"),
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.END,
                        ),
                        brain_url_field,
                    ],
                    tight=True,
                    spacing=8,
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=close_dialog),
                ft.ElevatedButton(
                    "Save & Apply",
                    icon=ft.Icons.CHECK_ROUNDED,
                    on_click=save_settings,
                    style=ft.ButtonStyle(bgcolor="#2563EB", color="#FFFFFF"),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.dialog = settings_dialog
        settings_dialog.open = True
        page.update()

    # ------------------------------------------
    # INPUT BAR & SEND ORCHESTRATION
    # ------------------------------------------
    message_input = ft.TextField(
        hint_text="Ask Pocket Agent or trigger tools...",
        multiline=True,
        min_lines=1,
        max_lines=4,
        expand=True,
        shift_enter=True,
        border_radius=24,
        filled=True,
        fill_color="#161B22",
        border_color="#30363D",
        focused_border_color="#3B82F6",
        content_padding=ft.padding.symmetric(horizontal=16, vertical=12),
        text_size=15,
    )

    send_button = ft.IconButton(
        icon=ft.Icons.ARROW_UPWARD_ROUNDED,
        icon_color="#FFFFFF",
        bgcolor="#2563EB",
        width=44,
        height=44,
        tooltip="Send Message",
    )

    def handle_send_message(e):
        user_text = message_input.value.strip()
        if not user_text:
            return

        api_key = get_stored_api_key()
        if not api_key:
            open_settings_dialog(e)
            return

        now_str = datetime.datetime.now().strftime("%I:%M %p")
        message_input.value = ""
        message_input.disabled = True
        send_button.disabled = True

        tools_executed_in_turn.clear()
        tool_badge.visible = False

        history = get_stored_chat_history()
        history.append({
            "role": "user",
            "text": user_text,
            "timestamp": now_str,
            "tools_used": [],
        })
        save_chat_history_to_storage(history)

        if len(history) == 1:
            chat_list.controls.clear()

        user_bubble = create_message_bubble(role="user", text=user_text, timestamp=now_str)
        chat_list.controls.append(user_bubble)
        page.update()

        try:
            agent_reply = execute_agent_multi_turn(user_text)
        except Exception as ex:
            agent_reply = f"⚠️ **Agent Error:**\n\n`{str(ex)}`"

        tool_badge.visible = False

        model_now_str = datetime.datetime.now().strftime("%I:%M %p")
        used_tools_snapshot = list(tools_executed_in_turn)
        history.append({
            "role": "model",
            "text": agent_reply,
            "timestamp": model_now_str,
            "tools_used": used_tools_snapshot,
        })
        save_chat_history_to_storage(history)

        agent_bubble = create_message_bubble(
            role="model",
            text=agent_reply,
            timestamp=model_now_str,
            tools_used=used_tools_snapshot,
        )
        chat_list.controls.append(agent_bubble)

        message_input.disabled = False
        send_button.disabled = False
        message_input.focus()
        page.update()

    message_input.on_submit = handle_send_message
    send_button.on_click = handle_send_message

    # ------------------------------------------
    # APPBAR & ASSEMBLY
    # ------------------------------------------
    page.appbar = ft.AppBar(
        leading=ft.Container(
            padding=ft.padding.only(left=12),
            content=ft.CircleAvatar(
                bgcolor="#1E293B",
                content=ft.Icon(name=ft.Icons.PSYCHOLOGY_ROUNDED, color="#38BDF8", size=22),
            ),
        ),
        title=ft.Column(
            controls=[
                ft.Text("Pocket Agent", size=18, weight=ft.FontWeight.BOLD, color="#F8FAFC"),
                ft.Row(
                    controls=[
                        ft.Container(width=7, height=7, border_radius=4, bgcolor="#10B981"),
                        ft.Text("Gemini 2.5 Flash • REST Direct", size=11, color="#94A3B8"),
                    ],
                    spacing=5,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            spacing=1,
        ),
        bgcolor="#161B22",
        elevation=2,
        actions=[
            ft.IconButton(
                icon=ft.Icons.DELETE_SWEEP_ROUNDED,
                tooltip="Clear Chat",
                icon_color="#94A3B8",
                on_click=confirm_clear_chat,
            ),
            ft.IconButton(
                icon=ft.Icons.SETTINGS_ROUNDED,
                tooltip="Settings",
                icon_color="#94A3B8",
                on_click=open_settings_dialog,
            ),
        ],
    )

    input_container = ft.Container(
        bgcolor="#161B22",
        padding=ft.padding.only(left=12, right=12, top=8, bottom=12),
        border=ft.border.only(top=ft.BorderSide(1, "#30363D")),
        content=ft.Row(
            controls=[
                message_input,
                send_button,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        ),
    )

    page.add(
        ft.Column(
            controls=[
                chat_list,
                tool_badge,
                input_container,
            ],
            expand=True,
            spacing=0,
        )
    )

    render_chat_history()


if __name__ == "__main__":
    ft.app(target=main)
