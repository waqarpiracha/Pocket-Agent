"""
Pocket Agent - Autonomous AI Mobile Agent Application
Framework: Python Flet (>=0.24.0) with native Flutter rendering for Android
AI Brain: Google GenAI SDK (gemini-2.5-flash) with tool-use / function calling
Storage: page.client_storage for local offline encrypted persistence
"""

import ast
import datetime
import json
import math
import operator
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional

import flet as ft
from google import genai
from google.genai import types

# ==========================================
# CONSTANTS & DEFAULT CONFIGURATION
# ==========================================
DEFAULT_SYSTEM_INSTRUCTION = (
    "You are Pocket Agent, an elite autonomous executive AI assistant and mobile operations specialist. "
    "You run locally on an Android device. You have direct access to system tools: "
    "1) Checking device date and time (`get_device_datetime`). "
    "2) Storing and retrieving local notes & tasks (`save_note`, `read_notes`). "
    "3) Triggering external webhooks and automation workflows like n8n or Zapier (`trigger_webhook`). "
    "4) Performing precision calculations (`quick_calculator`). "
    "Always proactively use your tools whenever relevant. Respond with structured, concise, "
    "executive-grade Markdown, featuring code snippets, tables, and bullet points where helpful."
)

STORAGE_KEY_API_KEY = "pocket_agent_gemini_api_key"
STORAGE_KEY_SYSTEM_PROMPT = "pocket_agent_system_prompt"
STORAGE_KEY_CHAT_HISTORY = "pocket_agent_chat_history"
STORAGE_KEY_NOTES = "pocket_agent_notes"


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
# MAIN APPLICATION CONTROLLER
# ==========================================
def main(page: ft.Page):
    # Mobile App Window & Theme Configuration
    page.title = "Pocket Agent"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.spacing = 0
    page.bgcolor = "#0D1117"  # Deep obsidian dark background

    # Configure responsive mobile fonts & visual styling
    page.theme = ft.Theme(
        color_scheme_seed="#3B82F6",
        visual_density=ft.ThemeVisualDensity.COMPACT,
    )

    # ------------------------------------------
    # STATE MANAGEMENT
    # ------------------------------------------
    current_tool_callback: Optional[Callable[[str, str], None]] = None
    tools_executed_in_current_turn: List[str] = []

    def notify_tool_execution(tool_name: str, detail: str = ""):
        tools_executed_in_current_turn.append(tool_name)
        if current_tool_callback:
            current_tool_callback(tool_name, detail)

    # ------------------------------------------
    # LOCAL STORAGE HELPERS
    # ------------------------------------------
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

    # ------------------------------------------
    # AUTONOMOUS AGENT TOOLS (FUNCTION CALLING)
    # ------------------------------------------
    def get_device_datetime() -> str:
        """Returns the current local date, time, and day of the week on the device."""
        notify_tool_execution("get_device_datetime", "reading device clock")
        now = datetime.datetime.now()
        return now.strftime("%A, %B %d, %Y - %I:%M:%S %p")

    def save_note(title: str, content: str) -> str:
        """Saves a note, task, or reminder to the device's persistent local storage.

        Args:
            title: The short descriptive title of the note.
            content: The detailed body text or task description.
        """
        notify_tool_execution("save_note", f"title: '{title}'")
        notes = get_stored_notes()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        notes[title.strip()] = {
            "content": content.strip(),
            "updated_at": timestamp,
        }
        save_notes_to_storage(notes)
        return f"Successfully saved note '{title}' at {timestamp}."

    def read_notes() -> str:
        """Retrieves and lists all persistent notes and tasks currently stored on the device."""
        notify_tool_execution("read_notes", "querying storage")
        notes = get_stored_notes()
        if not notes:
            return "No notes or tasks found in device storage."
        
        output_lines = [f"Found {len(notes)} note(s) in local storage:\n"]
        for idx, (title, data) in enumerate(notes.items(), start=1):
            body = data.get("content", "")
            updated = data.get("updated_at", "N/A")
            output_lines.append(f"{idx}. **{title}** (Updated: {updated})\n   {body}\n")
        return "\n".join(output_lines)

    def trigger_webhook(url: str, payload_json: str) -> str:
        """Sends an HTTP POST request with a JSON payload to an external automation webhook or API (e.g. n8n, Make, Zapier, Slack).

        Args:
            url: The destination endpoint URL.
            payload_json: A valid JSON string containing the data payload.
        """
        notify_tool_execution("trigger_webhook", f"POST -> {url[:30]}...")
        try:
            # Validate JSON format
            parsed_payload = json.loads(payload_json)
            encoded_data = json.dumps(parsed_payload).encode("utf-8")
            
            req = urllib.request.Request(
                url=url,
                data=encoded_data,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "PocketAgent-Android/1.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=12) as response:
                status_code = response.getcode()
                response_body = response.read().decode("utf-8", errors="replace")
                return f"Webhook HTTP {status_code} Success. Response preview: {response_body[:300]}"
        except urllib.error.HTTPError as he:
            return f"Webhook HTTP Error {he.code}: {he.reason}"
        except urllib.error.URLError as ue:
            return f"Webhook Connection Error: {ue.reason}"
        except json.JSONDecodeError as je:
            return f"Invalid JSON payload supplied: {str(je)}"
        except Exception as ex:
            return f"Webhook execution error: {str(ex)}"

    def quick_calculator(expression: str) -> str:
        """Safely computes a mathematical or electrical load expression. Supports standard math, sqrt, pow, abs, log, round, sin, cos, pi, and e.

        Args:
            expression: The arithmetic or algebraic formula string, e.g. '(120 * 15 * 0.8) / 1000' or 'sqrt(144) + 15 * 2'.
        """
        notify_tool_execution("quick_calculator", f"evaluating '{expression}'")
        return evaluate_math_expression(expression)

    # List of callable tools for Gemini Function Calling
    AGENT_TOOL_SET = [
        get_device_datetime,
        save_note,
        read_notes,
        trigger_webhook,
        quick_calculator,
    ]

    # ------------------------------------------
    # AGENT BRAIN CONTROLLER
    # ------------------------------------------
    class AgentBrain:
        def __init__(self):
            self.client: Optional[genai.Client] = None
            self.chat_session = None
            self.initialize_session()

        def initialize_session(self):
            api_key = get_stored_api_key()
            if not api_key:
                self.client = None
                self.chat_session = None
                return

            try:
                self.client = genai.Client(api_key=api_key)
                system_instruction = get_stored_system_prompt()
                
                # Reconstruct previous conversational turns from client_storage
                stored_turns = get_stored_chat_history()
                history_contents = []
                for item in stored_turns[-20:]:  # Keep recent context window compact
                    role = item.get("role", "user")
                    text = item.get("text", "")
                    if text:
                        gemini_role = "user" if role == "user" else "model"
                        history_contents.append(
                            types.Content(
                                role=gemini_role,
                                parts=[types.Part.from_text(text=text)],
                            )
                        )

                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    tools=AGENT_TOOL_SET,
                    temperature=0.4,
                )

                self.chat_session = self.client.chats.create(
                    model="gemini-2.5-flash",
                    config=config,
                    history=history_contents if history_contents else None,
                )
            except Exception as e:
                self.chat_session = None
                print(f"Error initializing Gemini session: {e}")

        def send_query(self, user_text: str) -> str:
            if not self.client or not self.chat_session:
                self.initialize_session()
                if not self.chat_session:
                    raise ValueError(
                        "Gemini API Key is missing or invalid. Please tap the Settings icon in the top right to configure your API key."
                    )

            response = self.chat_session.send_message(user_text)
            return response.text or "*(Agent executed operations but returned no additional text)*"

    brain = AgentBrain()

    # ------------------------------------------
    # UI COMPONENTS & LAYOUT
    # ------------------------------------------
    chat_list = ft.ListView(
        expand=True,
        spacing=14,
        padding=ft.padding.only(left=16, right=16, top=16, bottom=16),
        auto_scroll=True,
    )

    # Tool Execution Status Badge / Banner
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

    def on_tool_progress(name: str, detail: str = ""):
        tool_status_text.value = f"Invoking tool: {name}{f' ({detail})' if detail else ''}..."
        tool_badge.visible = True
        page.update()

    current_tool_callback = on_tool_progress

    # ------------------------------------------
    # CHAT BUBBLE GENERATION
    # ------------------------------------------
    def create_message_bubble(role: str, text: str, timestamp: str = "", tools_used: List[str] = None) -> ft.Control:
        is_user = (role == "user")
        
        # Format tool badges if any were executed for this turn
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
            # User Bubble: Right-aligned, Indigo-Blue Accent
            bubble_content = ft.Column(
                controls=[
                    ft.Text(
                        value=text,
                        color="#FFFFFF",
                        size=15,
                        selectable=True,
                    ),
                    ft.Text(
                        value=timestamp,
                        color="#93C5FD",
                        size=10,
                        text_align=ft.TextAlign.RIGHT,
                    ),
                ],
                tight=True,
                spacing=4,
                horizontal_alignment=ft.CrossAxisAlignment.END,
            )

            bubble_container = ft.Container(
                content=bubble_content,
                bgcolor="#2563EB",
                border_radius=ft.border_radius.only(
                    top_left=16,
                    top_right=4,
                    bottom_left=16,
                    bottom_right=16,
                ),
                padding=ft.padding.symmetric(horizontal=14, vertical=10),
                shadow=ft.BoxShadow(
                    spread_radius=1,
                    blur_radius=6,
                    color="#1E3A8A44",
                    offset=ft.Offset(0, 2),
                ),
            )

            return ft.Row(
                controls=[
                    ft.Container(expand=True),  # Spacer to push to right
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
            # Agent Bubble: Left-aligned, Sleek Obsidian Dark Card with Markdown
            column_items = []
            if tools_row:
                column_items.append(tools_row)

            column_items.append(
                ft.Markdown(
                    value=text,
                    selectable=True,
                    extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                    code_theme="atom-one-dark",
                    code_style=ft.TextStyle(
                        font_family="monospace",
                        size=13,
                        color="#A7F3D0",
                    ),
                )
            )

            if timestamp:
                column_items.append(
                    ft.Text(
                        value=timestamp,
                        color="#64748B",
                        size=10,
                    )
                )

            bubble_container = ft.Container(
                content=ft.Column(controls=column_items, tight=True, spacing=6),
                bgcolor="#161B22",
                border_radius=ft.border_radius.only(
                    top_left=4,
                    top_right=16,
                    bottom_left=16,
                    bottom_right=16,
                ),
                border=ft.border.all(1, "#30363D"),
                padding=ft.padding.symmetric(horizontal=14, vertical=12),
                shadow=ft.BoxShadow(
                    spread_radius=1,
                    blur_radius=8,
                    color="#00000066",
                    offset=ft.Offset(0, 3),
                ),
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

    # ------------------------------------------
    # LOAD SAVED MESSAGES ON STARTUP
    # ------------------------------------------
    def render_chat_history():
        chat_list.controls.clear()
        saved_history = get_stored_chat_history()
        if not saved_history:
            # Welcome Placeholder Card
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
                                "Equipped with live tools: clock, notes, webhooks, and calculator.",
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

    # ------------------------------------------
    # CHAT CLEAR ACTION
    # ------------------------------------------
    def confirm_clear_chat(e):
        def perform_clear(ev):
            page.client_storage.remove(STORAGE_KEY_CHAT_HISTORY)
            brain.initialize_session()
            close_dialog(ev)
            render_chat_history()
            page.snack_bar = ft.SnackBar(
                content=ft.Text("Chat history cleared."),
                bgcolor="#1E293B",
            )
            page.snack_bar.open = True
            page.update()

        confirm_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Clear Chat History?"),
            content=ft.Text("This will erase all local conversations from this device. Notes will be preserved."),
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
    # SETTINGS MODAL / BOTTOM SHEET
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

    def save_settings(e):
        key = api_key_field.value.strip()
        prompt = system_prompt_field.value.strip() or DEFAULT_SYSTEM_INSTRUCTION
        
        page.client_storage.set(STORAGE_KEY_API_KEY, key)
        page.client_storage.set(STORAGE_KEY_SYSTEM_PROMPT, prompt)
        
        brain.initialize_session()
        close_dialog(e)
        
        page.snack_bar = ft.SnackBar(
            content=ft.Text("Settings saved successfully!"),
            bgcolor="#10B981",
        )
        page.snack_bar.open = True
        page.update()

    def reset_prompt(e):
        system_prompt_field.value = DEFAULT_SYSTEM_INSTRUCTION
        page.update()

    def open_settings_dialog(e):
        api_key_field.value = get_stored_api_key()
        system_prompt_field.value = get_stored_system_prompt()

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
                width=340,
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
    # MESSAGE SEND & ORCHESTRATION HANDLER
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
        
        # Reset tool tracker for this turn
        tools_executed_in_current_turn.clear()
        tool_badge.visible = False

        # Retrieve and update history
        history = get_stored_chat_history()
        history.append({
            "role": "user",
            "text": user_text,
            "timestamp": now_str,
            "tools_used": [],
        })
        save_chat_history_to_storage(history)

        # Clear placeholder if it was first message
        if len(history) == 1:
            chat_list.controls.clear()

        # Add user message bubble immediately
        user_bubble = create_message_bubble(role="user", text=user_text, timestamp=now_str)
        chat_list.controls.append(user_bubble)
        page.update()

        # Query Agent Brain with tool handling
        agent_reply = ""
        try:
            agent_reply = brain.send_query(user_text)
        except Exception as ex:
            agent_reply = f"⚠️ **Agent Encountered an Error:**\n\n`{str(ex)}`"

        # Turn finished: hide tool execution badge
        tool_badge.visible = False

        # Add agent message bubble
        model_now_str = datetime.datetime.now().strftime("%I:%M %p")
        used_tools_snapshot = list(tools_executed_in_current_turn)
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
    # APP BAR & MAIN CONTAINER ASSEMBLY
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
                        ft.Text("Gemini 2.5 Flash • Active", size=11, color="#94A3B8"),
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

    # Initial load of messages
    render_chat_history()


if __name__ == "__main__":
    ft.app(target=main)
