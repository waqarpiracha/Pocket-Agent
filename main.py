"""
Waqar-SuperAgent: Personal Intelligence & Automation Hub
Mobile Application Architecture: Pure Python Flet (0.25.2)
Backend: 100% Free Zero-Server Google Drive Robot (google_drive_robot.gs)
AI Brain: Direct Google Gemini 2.5 Flash REST API (Zero C/Rust extension dependencies)
"""

import ast
import datetime
import json
import math
import operator
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

import flet as ft

# ==========================================
# STORAGE KEYS & CONSTANTS
# ==========================================
STORAGE_KEY_API_KEY = "waqar_superagent_gemini_api_key"
STORAGE_KEY_SYSTEM_PROMPT = "waqar_superagent_system_prompt"
STORAGE_KEY_CHAT_HISTORY = "waqar_superagent_chat_history"
STORAGE_KEY_NOTES = "waqar_superagent_notes"
STORAGE_KEY_ROBOT_URL = "waqar_superagent_drive_robot_url"
STORAGE_KEY_DRIVE_FOLDER = "waqar_superagent_drive_folder"

DEFAULT_ROBOT_URL = "https://script.google.com/macros/s/AKfycbw_example_drive_robot/exec"
DEFAULT_FOLDER = "PocketAgent_Videos"

DEFAULT_SYSTEM_INSTRUCTION = (
    "You are Waqar-SuperAgent, the personal executive AI assistant for Waqar Aslam Piracha "
    "(Senior Business Intelligence Consultant, Supply Chain Digital Transformation Specialist & Automation Expert). "
    "You run locally on Android. You have direct tools to: "
    "1) `get_device_datetime`: Current device date and time. "
    "2) `save_note` & `read_notes`: On-device notes and tasks. "
    "3) `quick_calculator`: Exact math and freight/supply chain formulas. "
    "4) `query_working_knowledge`: Search Second Brain SOPs, bot catalogs, and notes in Google Drive. "
    "5) `save_to_second_brain`: Log ideas and operational notes to Google Drive. "
    "Respond with concise, executive-grade Markdown, featuring bullet points and structured formatting."
)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

# ==========================================
# SAFE MATHEMATICAL EVALUATOR (AST)
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

SAFE_CONSTANTS = {"pi": math.pi, "e": math.e}


def _eval_ast(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("Unsupported constant")
    elif isinstance(node, ast.Name):
        if node.id in SAFE_CONSTANTS:
            return SAFE_CONSTANTS[node.id]
        raise ValueError(f"Unknown variable: {node.id}")
    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type in SAFE_OPERATORS:
            return SAFE_OPERATORS[op_type](_eval_ast(node.left), _eval_ast(node.right))
        raise ValueError("Unsupported binary operator")
    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type in SAFE_OPERATORS:
            return SAFE_OPERATORS[op_type](_eval_ast(node.operand))
        raise ValueError("Unsupported unary operator")
    elif isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in SAFE_FUNCTIONS:
            args = [_eval_ast(arg) for arg in node.args]
            return SAFE_FUNCTIONS[node.func.id](*args)
        raise ValueError("Unsupported function call")
    raise ValueError("Unsupported expression")


def evaluate_math(expr: str) -> str:
    try:
        parsed = ast.parse(expr.strip(), mode="eval")
        return str(_eval_ast(parsed.body))
    except Exception as e:
        return f"Calculation Error: {str(e)}"


# ==========================================
# GEMINI FUNCTION CALLING TOOL DECLARATIONS
# ==========================================
GEMINI_FUNCTION_DECLARATIONS = [
    {
        "name": "get_device_datetime",
        "description": "Returns the current local date, time, and day of the week on the device.",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "save_note",
        "description": "Saves a personal task, note, or reminder locally on the mobile device.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING", "description": "The title or subject."},
                "content": {"type": "STRING", "description": "The details of the note."},
            },
            "required": ["title", "content"],
        },
    },
    {
        "name": "read_notes",
        "description": "Retrieves all persistent tasks and notes saved on the mobile device.",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "quick_calculator",
        "description": "Safely evaluates mathematical or engineering expressions (e.g., '(240*15*0.8)/1000' or 'sqrt(144)+25').",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "expression": {"type": "STRING", "description": "The formula to evaluate."}
            },
            "required": ["expression"],
        },
    },
    {
        "name": "query_working_knowledge",
        "description": "Queries Waqar's Google Drive AI Second Brain for SOPs, supply chain patterns, bot catalogs, and notes.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "search_keyword": {"type": "STRING", "description": "Keyword to search across Second Brain."}
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
                "topic": {"type": "STRING", "description": "Topic or category."},
                "content": {"type": "STRING", "description": "The content to record."},
            },
            "required": ["topic", "content"],
        },
    },
]


# ==========================================
# MAIN APPLICATION CONTROLLER
# ==========================================
def main(page: ft.Page):
    page.title = "Waqar-SuperAgent"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.spacing = 0
    page.bgcolor = "#0B0F17"  # High-contrast deep obsidian

    page.theme = ft.Theme(
        color_scheme_seed="#10B981",  # Emerald theme seed
        visual_density=ft.ThemeVisualDensity.COMPACT,
    )

    tools_executed_in_turn: List[str] = []

    # Storage accessors
    def get_api_key() -> str:
        return page.client_storage.get(STORAGE_KEY_API_KEY) or ""

    def get_system_prompt() -> str:
        return page.client_storage.get(STORAGE_KEY_SYSTEM_PROMPT) or DEFAULT_SYSTEM_INSTRUCTION

    def get_chat_history() -> List[Dict[str, Any]]:
        return page.client_storage.get(STORAGE_KEY_CHAT_HISTORY) or []

    def set_chat_history(h: List[Dict[str, Any]]):
        page.client_storage.set(STORAGE_KEY_CHAT_HISTORY, h)

    def get_notes() -> Dict[str, Any]:
        return page.client_storage.get(STORAGE_KEY_NOTES) or {}

    def set_notes(n: Dict[str, Any]):
        page.client_storage.set(STORAGE_KEY_NOTES, n)

    def get_robot_url() -> str:
        return page.client_storage.get(STORAGE_KEY_ROBOT_URL) or DEFAULT_ROBOT_URL

    def get_drive_folder() -> str:
        return page.client_storage.get(STORAGE_KEY_DRIVE_FOLDER) or DEFAULT_FOLDER

    # ------------------------------------------
    # SECOND BRAIN TOOLS
    # ------------------------------------------
    def tool_get_device_datetime(args: Dict[str, Any]) -> str:
        return datetime.datetime.now().strftime("%A, %B %d, %Y - %I:%M:%S %p")

    def tool_save_note(args: Dict[str, Any]) -> str:
        title = args.get("title", "Untitled").strip()
        content = args.get("content", "").strip()
        notes = get_notes()
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        notes[title] = {"content": content, "updated_at": ts}
        set_notes(notes)
        return f"Saved note '{title}' on device at {ts}."

    def tool_read_notes(args: Dict[str, Any]) -> str:
        notes = get_notes()
        if not notes:
            return "No notes or tasks found on this device."
        lines = [f"Found {len(notes)} note(s) in local storage:\n"]
        for idx, (title, data) in enumerate(notes.items(), start=1):
            lines.append(f"{idx}. **{title}** ({data.get('updated_at', 'N/A')})\n   {data.get('content', '')}\n")
        return "\n".join(lines)

    def tool_quick_calculator(args: Dict[str, Any]) -> str:
        return evaluate_math(args.get("expression", ""))

    def tool_query_working_knowledge(args: Dict[str, Any]) -> str:
        kw = args.get("search_keyword", "").strip()
        url = get_robot_url()
        try:
            params = urllib.parse.urlencode({"action": "query_second_brain", "q": kw})
            req = urllib.request.Request(f"{url}?{params}", headers={"User-Agent": "WaqarSuperAgent-Android/1.0"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return f"Second Brain Query for '{kw}':\n" + str(data.get("results", data))
        except Exception as e:
            notes = get_notes()
            matching = [f"**{t}**: {d.get('content')}" for t, d in notes.items() if kw.lower() in t.lower() or kw.lower() in d.get("content", "").lower()]
            if matching:
                return f"(Offline Mode) Local notes matching '{kw}':\n" + "\n".join(matching)
            return f"Second Brain notice: Could not contact Google Drive Robot ({str(e)})."

    def tool_save_to_second_brain(args: Dict[str, Any]) -> str:
        topic = args.get("topic", "General")
        content = args.get("content", "")
        url = get_robot_url()
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tool_save_note({"title": f"[{topic}] {ts}", "content": content})
        try:
            payload = json.dumps({"action": "save_second_brain", "topic": topic, "content": content}).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", "User-Agent": "WaqarSuperAgent-Android/1.0"}, method="POST")
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return f"Logged to Second Brain: {data.get('message', 'Success')}"
        except Exception as e:
            return f"Saved locally on device. Drive sync deferred ({str(e)})."

    TOOL_DISPATCH = {
        "get_device_datetime": tool_get_device_datetime,
        "save_note": tool_save_note,
        "read_notes": tool_read_notes,
        "quick_calculator": tool_quick_calculator,
        "query_working_knowledge": tool_query_working_knowledge,
        "save_to_second_brain": tool_save_to_second_brain,
    }

    # ------------------------------------------
    # DIRECT GEMINI REST API
    # ------------------------------------------
    def call_gemini_api(contents_payload: List[Dict[str, Any]], system_prompt: str, api_key: str) -> Dict[str, Any]:
        endpoint = f"{GEMINI_API_BASE}?key={api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": contents_payload,
            "tools": [{"function_declarations": GEMINI_FUNCTION_DECLARATIONS}],
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 2048},
        }
        encoded = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(endpoint, data=encoded, headers={"Content-Type": "application/json", "User-Agent": "WaqarSuperAgent-Android/1.0"}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def run_agent_turn(user_msg: str) -> str:
        api_key = get_api_key()
        if not api_key:
            raise ValueError("Gemini API key is missing. Tap the Settings icon in the top right to configure it.")

        sys_prompt = get_system_prompt()
        history = get_chat_history()
        contents: List[Dict[str, Any]] = []

        for item in history[-14:]:
            role = item.get("role", "user")
            text = item.get("text", "")
            if text:
                contents.append({"role": "user" if role == "user" else "model", "parts": [{"text": text}]})

        contents.append({"role": "user", "parts": [{"text": user_msg}]})

        for _ in range(5):
            api_result = call_gemini_api(contents, sys_prompt, api_key)
            candidates = api_result.get("candidates", [])
            if not candidates:
                return "No response from Gemini API."

            parts = candidates[0].get("content", {}).get("parts", [])
            fn_call = None
            text_acc = ""
            for p in parts:
                if "functionCall" in p:
                    fn_call = p["functionCall"]
                if "text" in p:
                    text_acc += p["text"]

            if not fn_call:
                return text_acc or "*(Agent executed operations)*"

            fn_name = fn_call.get("name", "")
            fn_args = fn_call.get("args", {})
            tools_executed_in_turn.append(fn_name)

            tool_status_text.value = f"Executing tool: {fn_name}..."
            tool_badge.visible = True
            page.update()

            handler = TOOL_DISPATCH.get(fn_name)
            tool_out = handler(fn_args) if handler else f"Unknown tool: '{fn_name}'"

            contents.append({"role": "model", "parts": [{"functionCall": {"name": fn_name, "args": fn_args}}]})
            contents.append({"role": "user", "parts": [{"functionResponse": {"name": fn_name, "response": {"output": str(tool_out)}}}]})

        return "Agent completed multi-turn tool operations."

    # ------------------------------------------
    # TAB 1: SECOND BRAIN CHAT UI
    # ------------------------------------------
    chat_list = ft.ListView(expand=True, spacing=14, padding=ft.padding.symmetric(horizontal=16, vertical=16), auto_scroll=True)
    tool_status_text = ft.Text(value="", color="#A7F3D0", size=12, weight=ft.FontWeight.W_500, expand=True)

    tool_badge = ft.Container(
        visible=False,
        bgcolor="#064E3B",
        border_radius=12,
        padding=ft.padding.symmetric(horizontal=12, vertical=8),
        margin=ft.padding.symmetric(horizontal=16, vertical=4),
        border=ft.border.all(1, "#10B981"),
        content=ft.Row(
            controls=[
                ft.ProgressRing(width=14, height=14, stroke_width=2, color="#34D399"),
                ft.Icon(name=ft.Icons.AUTO_AWESOME_ROUNDED, size=15, color="#FBBF24"),
                tool_status_text,
            ],
            spacing=8,
        ),
    )

    def create_chat_bubble(role: str, text: str, timestamp: str = "", tools_used: List[str] = None) -> ft.Control:
        is_user = (role == "user")
        tools_row = None
        if tools_used and not is_user:
            tool_chips = [
                ft.Container(
                    bgcolor="#064E3B",
                    border=ft.border.all(1, "#10B981"),
                    border_radius=8,
                    padding=ft.padding.symmetric(horizontal=8, vertical=3),
                    content=ft.Row(
                        controls=[
                            ft.Icon(name=ft.Icons.BOLT_ROUNDED, size=12, color="#34D399"),
                            ft.Text(f"tool: {t}", size=11, color="#D1FAE5", weight=ft.FontWeight.W_600),
                        ],
                        spacing=4,
                        tight=True,
                    ),
                )
                for t in tools_used
            ]
            tools_row = ft.Row(controls=tool_chips, wrap=True, spacing=6)

        if is_user:
            bubble = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(value=text, color="#FFFFFF", size=15, selectable=True),
                        ft.Text(value=timestamp, color="#A7F3D0", size=10, text_align=ft.TextAlign.RIGHT),
                    ],
                    tight=True,
                    spacing=4,
                    horizontal_alignment=ft.CrossAxisAlignment.END,
                ),
                bgcolor="#047857",  # Deep emerald user bubble
                border_radius=ft.border_radius.only(top_left=16, top_right=4, bottom_left=16, bottom_right=16),
                padding=ft.padding.symmetric(horizontal=14, vertical=10),
            )
            return ft.Row(
                controls=[
                    ft.Container(expand=True),
                    bubble,
                    ft.CircleAvatar(content=ft.Icon(name=ft.Icons.PERSON_ROUNDED, size=18, color="#FFFFFF"), bgcolor="#065F46", radius=16),
                ],
                alignment=ft.MainAxisAlignment.END,
                vertical_alignment=ft.CrossAxisAlignment.START,
                spacing=8,
            )
        else:
            col_items = []
            if tools_row:
                col_items.append(tools_row)
            col_items.append(
                ft.Markdown(
                    value=text,
                    selectable=True,
                    extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                    code_theme="atom-one-dark",
                    code_style=ft.TextStyle(font_family="monospace", size=13, color="#6EE7B7"),
                )
            )
            if timestamp:
                col_items.append(ft.Text(value=timestamp, color="#6B7280", size=10))

            card = ft.Container(
                content=ft.Column(controls=col_items, tight=True, spacing=6),
                bgcolor="#111827",
                border_radius=ft.border_radius.only(top_left=4, top_right=16, bottom_left=16, bottom_right=16),
                border=ft.border.all(1, "#1F2937"),
                padding=ft.padding.symmetric(horizontal=14, vertical=12),
                expand=True,
            )
            return ft.Row(
                controls=[
                    ft.CircleAvatar(content=ft.Icon(name=ft.Icons.PSYCHOLOGY_ROUNDED, size=18, color="#10B981"), bgcolor="#064E3B", radius=16),
                    card,
                ],
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.START,
                spacing=8,
            )

    def reload_chat_history():
        chat_list.controls.clear()
        history = get_chat_history()
        if not history:
            chat_list.controls.append(
                ft.Container(
                    alignment=ft.alignment.center,
                    padding=ft.padding.symmetric(vertical=24, horizontal=16),
                    content=ft.Column(
                        controls=[
                            ft.Icon(name=ft.Icons.AUTO_AWESOME_ROUNDED, size=46, color="#10B981"),
                            ft.Text("Second Brain Active", size=18, weight=ft.FontWeight.BOLD, color="#F9FAFB"),
                            ft.Text("Ask anything about your supply chain SOPs, bots, or notes.", size=13, color="#9CA3AF", text_align=ft.TextAlign.CENTER),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                    ),
                )
            )
        else:
            for item in history:
                chat_list.controls.append(create_chat_bubble(item.get("role", "user"), item.get("text", ""), item.get("timestamp", ""), item.get("tools_used", [])))
        page.update()

    chat_input = ft.TextField(
        hint_text="Ask Second Brain or run tools...",
        multiline=True,
        min_lines=1,
        max_lines=3,
        expand=True,
        border_radius=24,
        filled=True,
        fill_color="#111827",
        border_color="#1F2937",
        focused_border_color="#10B981",
        content_padding=ft.padding.symmetric(horizontal=16, vertical=10),
    )

    send_btn = ft.IconButton(icon=ft.Icons.ARROW_UPWARD_ROUNDED, bgcolor="#10B981", icon_color="#FFFFFF", width=42, height=42)

    def on_send_chat(e):
        txt = chat_input.value.strip()
        if not txt:
            return
        if not get_api_key():
            open_settings(e)
            return

        now = datetime.datetime.now().strftime("%I:%M %p")
        chat_input.value = ""
        chat_input.disabled = True
        send_btn.disabled = True
        tools_executed_in_turn.clear()
        tool_badge.visible = False

        hist = get_chat_history()
        hist.append({"role": "user", "text": txt, "timestamp": now, "tools_used": []})
        set_chat_history(hist)

        if len(hist) == 1:
            chat_list.controls.clear()
        chat_list.controls.append(create_chat_bubble("user", txt, now))
        page.update()

        try:
            ans = run_agent_turn(txt)
        except Exception as err:
            ans = f"⚠️ **Error:** {str(err)}"

        tool_badge.visible = False
        m_now = datetime.datetime.now().strftime("%I:%M %p")
        hist.append({"role": "model", "text": ans, "timestamp": m_now, "tools_used": list(tools_executed_in_turn)})
        set_chat_history(hist)

        chat_list.controls.append(create_chat_bubble("model", ans, m_now, list(tools_executed_in_turn)))
        chat_input.disabled = False
        send_btn.disabled = False
        chat_input.focus()
        page.update()

    chat_input.on_submit = on_send_chat
    send_btn.on_click = on_send_chat

    tab1_content = ft.Column(
        controls=[
            chat_list,
            tool_badge,
            ft.Container(
                bgcolor="#111827",
                padding=ft.padding.only(left=12, right=12, top=6, bottom=10),
                border=ft.border.only(top=ft.BorderSide(1, "#1F2937")),
                content=ft.Row([chat_input, send_btn], spacing=8),
            ),
        ],
        expand=True,
        spacing=0,
    )

    # ------------------------------------------
    # TAB 2: GOOGLE DRIVE CLOUD VIDEO BROWSER & YOUTUBE PUBLISHER
    # ------------------------------------------
    drive_folder_field = ft.TextField(
        label="Google Drive Folder Name / Filter",
        value=get_drive_folder(),
        hint_text="e.g. PocketAgent_Videos or 'all'",
        border_color="#10B981",
        bgcolor="#0F172A",
        expand=True,
    )

    drive_video_list = ft.Column(spacing=8)

    selected_video_badge = ft.Container(
        visible=False,
        bgcolor="#064E3B",
        border_radius=10,
        padding=10,
        border=ft.border.all(1, "#10B981"),
        content=ft.Row(
            controls=[
                ft.Icon(name=ft.Icons.CHECK_CIRCLE_ROUNDED, color="#34D399", size=20),
                ft.Text("Target Video Selected", weight=ft.FontWeight.BOLD, color="#ECFDF5", expand=True),
            ],
            spacing=8,
        ),
    )

    selected_video_name = ft.Text("", weight=ft.FontWeight.BOLD, color="#34D399", size=14)
    selected_video_meta = ft.Text("", color="#9CA3AF", size=12)

    selected_card = ft.Container(
        visible=False,
        bgcolor="#111827",
        border_radius=12,
        padding=12,
        border=ft.border.all(1, "#374151"),
        content=ft.Column(
            controls=[
                ft.Row([ft.Icon(name=ft.Icons.MOVIE_ROUNDED, color="#10B981", size=18), selected_video_name], spacing=8),
                selected_video_meta,
            ],
            tight=True,
            spacing=4,
        ),
    )

    account_dropdown = ft.Dropdown(
        label="Target YouTube & Media Account",
        border_color="#10B981",
        bgcolor="#0F172A",
        value="Waqar Analytics",
        options=[
            ft.dropdown.Option("Waqar Analytics"),
            ft.dropdown.Option("Personal / BPC Operations"),
            ft.dropdown.Option("Account 1"),
            ft.dropdown.Option("Account 2"),
        ],
    )

    target_filename_input = ft.TextField(
        label="Selected Drive Video File",
        hint_text="sample_video.mp4",
        border_color="#374151",
        bgcolor="#0F172A",
    )

    title_input = ft.TextField(
        label="Video Title",
        hint_text="Enter YouTube title or tap 'AI Magic Metadata'",
        border_color="#374151",
        bgcolor="#0F172A",
    )

    desc_input = ft.TextField(
        label="Description",
        multiline=True,
        min_lines=2,
        max_lines=4,
        hint_text="Compelling description with call to action",
        border_color="#374151",
        bgcolor="#0F172A",
    )

    hashtags_input = ft.TextField(
        label="Hashtags & Tags",
        hint_text="#SupplyChain #PowerBI #Excel #WaqarAnalytics",
        border_color="#374151",
        bgcolor="#0F172A",
    )

    chk_youtube = ft.Checkbox(label="YouTube Shorts / Video", value=True, active_color="#EF4444")
    chk_instagram = ft.Checkbox(label="Instagram Reels", value=True, active_color="#EC4899")
    chk_tiktok = ft.Checkbox(label="TikTok", value=True, active_color="#38BDF8")

    publish_result_card = ft.Container(
        visible=False,
        bgcolor="#064E3B",
        border_radius=12,
        padding=14,
        border=ft.border.all(1, "#10B981"),
        content=ft.Text("", size=13, color="#ECFDF5"),
    )

    def select_video_item(video_info: Dict[str, Any]):
        fn = video_info.get("name", "")
        size_mb = video_info.get("sizeMb", "0")
        updated = video_info.get("updatedAt", "")

        target_filename_input.value = fn
        title_input.value = fn.replace(".mp4", "").replace("_", " ").title()

        selected_video_name.value = fn
        selected_video_meta.value = f"Size: {size_mb} MB  •  Last Modified: {updated} (Google Drive)"
        selected_card.visible = True
        selected_video_badge.visible = True

        page.snack_bar = ft.SnackBar(content=ft.Text(f"Selected '{fn}' from Google Drive"), bgcolor="#047857")
        page.snack_bar.open = True
        page.update()

    def browse_drive_videos(e):
        folder = drive_folder_field.value.strip() or "all"
        page.client_storage.set(STORAGE_KEY_DRIVE_FOLDER, folder)
        url = get_robot_url()

        drive_video_list.controls.clear()
        drive_video_list.controls.append(
            ft.Row([ft.ProgressRing(width=16, height=16, stroke_width=2), ft.Text(f"Scanning Google Drive for videos in '{folder}'...", color="#9CA3AF")], spacing=8)
        )
        page.update()

        try:
            params = urllib.parse.urlencode({"action": "list_drive_videos", "folder": folder})
            req = urllib.request.Request(f"{url}?{params}", headers={"User-Agent": "WaqarSuperAgent-Android/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                videos = data.get("videos", [])

                drive_video_list.controls.clear()
                if not videos:
                    drive_video_list.controls.append(
                        ft.Container(
                            padding=12,
                            bgcolor="#1F2937",
                            border_radius=8,
                            content=ft.Text(f"No video files found in Google Drive folder '{folder}'. Place your .mp4 files into Google Drive and tap Scan again.", color="#FBBF24", size=13),
                        )
                    )
                    page.update()
                    return

                drive_video_list.controls.append(
                    ft.Text(f"Found {len(videos)} video file(s) in Google Drive (Tap to select):", size=13, weight=ft.FontWeight.BOLD, color="#34D399")
                )

                for v in videos:
                    fn = v.get("name", "video.mp4")
                    sz = v.get("sizeMb", "?")
                    dt = v.get("updatedAt", "")

                    # Create interactive card for each drive video
                    v_card = ft.Container(
                        bgcolor="#111827",
                        border_radius=10,
                        border=ft.border.all(1, "#374151"),
                        padding=12,
                        content=ft.Row(
                            controls=[
                                ft.Icon(name=ft.Icons.VIDEO_FILE_ROUNDED, color="#10B981", size=24),
                                ft.Column(
                                    controls=[
                                        ft.Text(fn, weight=ft.FontWeight.BOLD, size=13, color="#F9FAFB"),
                                        ft.Text(f"{sz} MB • {dt}", size=11, color="#9CA3AF"),
                                    ],
                                    spacing=2,
                                    expand=True,
                                ),
                                ft.ElevatedButton(
                                    "Select",
                                    icon=ft.Icons.TOUCH_APP_ROUNDED,
                                    style=ft.ButtonStyle(bgcolor="#047857", color="#FFFFFF"),
                                    on_click=lambda ev, vi=v: select_video_item(vi),
                                ),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=10,
                        ),
                    )
                    drive_video_list.controls.append(v_card)

                page.snack_bar = ft.SnackBar(content=ft.Text(f"Retrieved {len(videos)} videos from Google Drive!"), bgcolor="#047857")
                page.snack_bar.open = True
                page.update()
        except Exception as err:
            drive_video_list.controls.clear()
            drive_video_list.controls.append(
                ft.Text(f"⚠️ Drive Connection Error: {str(err)}\nMake sure you deployed google_drive_robot.gs and set your Web App URL in Settings.", color="#EF4444", size=12)
            )
            page.update()

    def generate_ai_metadata(e):
        api_key = get_api_key()
        if not api_key:
            open_settings(e)
            return

        target_name = target_filename_input.value.strip() or "Supply Chain Automation Video"
        page.snack_bar = ft.SnackBar(content=ft.Text("✨ Gemini 2.5 Flash analyzing video & crafting viral metadata..."), bgcolor="#10B981")
        page.snack_bar.open = True
        page.update()

        prompt = (
            f"You are a top viral YouTube Shorts and LinkedIn video strategist for Waqar Piracha "
            f"(Senior BI & Supply Chain Consultant). The video file is named: '{target_name}'. "
            "Write highly engaging, high-CTR viral metadata formatted as raw JSON with three keys: "
            "'title' (punchy 6-10 word title with an emoji), "
            "'description' (2 high-impact lines explaining the automated solution, business ROI, and CTA to connect on LinkedIn), "
            "'hashtags' (6-8 trending tags e.g. #SupplyChain #PowerBI #Excel #WaqarAnalytics #Kinaxis). "
            "Return raw JSON only, no markdown code block fences."
        )

        try:
            endpoint = f"{GEMINI_API_BASE}?key={api_key}"
            payload = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.3, "responseMimeType": "application/json"},
            }
            req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                txt = res["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(txt)

                title_input.value = parsed.get("title", title_input.value)
                desc_input.value = parsed.get("description", desc_input.value)
                hashtags_input.value = parsed.get("hashtags", hashtags_input.value)

                # Sync to Queue in Drive
                url = get_robot_url()
                sync_payload = json.dumps({
                    "action": "update_video_metadata",
                    "filename": target_filename_input.value,
                    "account": account_dropdown.value,
                    "title": title_input.value,
                    "description": desc_input.value,
                    "hashtags": hashtags_input.value,
                }).encode("utf-8")
                urllib.request.urlopen(urllib.request.Request(url, data=sync_payload, headers={"Content-Type": "application/json"}, method="POST"), timeout=8)

                page.snack_bar = ft.SnackBar(content=ft.Text("✨ AI Metadata generated & synced to Google Drive Sheet!"), bgcolor="#047857")
                page.snack_bar.open = True
                page.update()
        except Exception as err:
            page.snack_bar = ft.SnackBar(content=ft.Text(f"AI Error: {str(err)}"), bgcolor="#EF4444")
            page.snack_bar.open = True
            page.update()

    def publish_video_from_drive(e):
        fn = target_filename_input.value.strip()
        if not fn:
            page.snack_bar = ft.SnackBar(content=ft.Text("Please select a video file from Google Drive above."), bgcolor="#EF4444")
            page.snack_bar.open = True
            page.update()
            return

        platforms = []
        if chk_youtube.value:
            platforms.append("youtube")
        if chk_instagram.value:
            platforms.append("instagram")
        if chk_tiktok.value:
            platforms.append("tiktok")

        if not platforms:
            page.snack_bar = ft.SnackBar(content=ft.Text("Please select at least one publishing platform."), bgcolor="#EF4444")
            page.snack_bar.open = True
            page.update()
            return

        publish_result_card.visible = True
        publish_result_card.content = ft.Row([
            ft.ProgressRing(width=16, height=16, stroke_width=2, color="#34D399"),
            ft.Text(f"🚀 Google Drive Robot is uploading '{fn}' directly to {', '.join(platforms)}..."),
        ], spacing=10)
        page.update()

        url = get_robot_url()
        try:
            payload = json.dumps({
                "action": "publish_video",
                "filename": fn,
                "account": account_dropdown.value,
                "title": title_input.value,
                "description": desc_input.value,
                "hashtags": hashtags_input.value,
                "platforms": platforms,
            }).encode("utf-8")

            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", "User-Agent": "WaqarSuperAgent-Android/1.0"}, method="POST")
            with urllib.request.urlopen(req, timeout=60) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                status = res.get("status", "unknown")
                msg = res.get("message", "")
                p_results = res.get("platforms", {})

                res_lines = [f"**Status: {status.upper()}**\n{msg}\n"]
                for p, val in p_results.items():
                    res_lines.append(f"• **{p.title()}**: {val}")

                publish_result_card.content = ft.Markdown("\n".join(res_lines))
                page.update()
        except Exception as err:
            publish_result_card.content = ft.Text(f"⚠️ Upload Error: {str(err)}", color="#EF4444")
            page.update()

    tab2_content = ft.ListView(
        expand=True,
        padding=16,
        spacing=12,
        controls=[
            ft.Row([
                ft.Icon(name=ft.Icons.CLOUD_SYNC_ROUNDED, color="#10B981", size=22),
                ft.Text("Google Drive Video Browser & YouTube Publisher", size=16, weight=ft.FontWeight.BOLD),
            ], spacing=8),
            ft.Text("Pick videos stored directly in Google Drive and upload to YouTube with zero local storage requirements.", size=12, color="#9CA3AF"),
            
            ft.Row([
                drive_folder_field,
                ft.ElevatedButton(
                    "🔍 Scan Drive",
                    icon=ft.Icons.REFRESH_ROUNDED,
                    on_click=browse_drive_videos,
                    style=ft.ButtonStyle(bgcolor="#065F46", color="#FFFFFF"),
                    height=50,
                ),
            ], spacing=8),

            drive_video_list,
            selected_video_badge,
            selected_card,

            account_dropdown,
            target_filename_input,
            title_input,
            desc_input,
            hashtags_input,

            ft.Text("Publishing Channels:", size=13, weight=ft.FontWeight.BOLD),
            ft.Row([chk_youtube, chk_instagram, chk_tiktok], wrap=True, spacing=10),

            ft.Row([
                ft.OutlinedButton(
                    "✨ AI Magic Metadata",
                    icon=ft.Icons.AUTO_AWESOME_ROUNDED,
                    on_click=generate_ai_metadata,
                ),
            ]),

            ft.ElevatedButton(
                "🚀 Publish from Google Drive to YouTube",
                icon=ft.Icons.ROCKET_LAUNCH_ROUNDED,
                on_click=publish_video_from_drive,
                height=48,
                style=ft.ButtonStyle(bgcolor="#10B981", color="#FFFFFF"),
            ),
            publish_result_card,
            ft.Container(height=24),
        ],
    )

    # ------------------------------------------
    # SETTINGS MODAL
    # ------------------------------------------
    api_key_input = ft.TextField(label="Gemini API Key", password=True, can_reveal_password=True, hint_text="AIzaSy...", border_color="#10B981", bgcolor="#0F172A")
    robot_url_input = ft.TextField(label="Google Drive Robot Web App URL", hint_text="https://script.google.com/macros/s/.../exec", border_color="#10B981", bgcolor="#0F172A")
    sys_prompt_input = ft.TextField(label="System Persona", multiline=True, min_lines=2, max_lines=4, border_color="#10B981", bgcolor="#0F172A")

    def save_settings(e):
        page.client_storage.set(STORAGE_KEY_API_KEY, api_key_input.value.strip())
        page.client_storage.set(STORAGE_KEY_ROBOT_URL, robot_url_input.value.strip() or DEFAULT_ROBOT_URL)
        page.client_storage.set(STORAGE_KEY_SYSTEM_PROMPT, sys_prompt_input.value.strip() or DEFAULT_SYSTEM_INSTRUCTION)
        if page.dialog:
            page.dialog.open = False
        page.snack_bar = ft.SnackBar(content=ft.Text("Settings saved!"), bgcolor="#047857")
        page.snack_bar.open = True
        page.update()

    def open_settings(e):
        api_key_input.value = get_api_key()
        robot_url_input.value = get_robot_url()
        sys_prompt_input.value = get_system_prompt()

        settings_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row([ft.Icon(name=ft.Icons.TUNE_ROUNDED, color="#10B981"), ft.Text("App Settings", weight=ft.FontWeight.BOLD)], spacing=8),
            content=ft.Container(width=340, content=ft.Column([api_key_input, robot_url_input, sys_prompt_input], tight=True, spacing=10)),
            actions=[
                ft.TextButton("Cancel", on_click=lambda ev: close_dialog(ev)),
                ft.ElevatedButton("Save", icon=ft.Icons.CHECK_ROUNDED, on_click=save_settings, style=ft.ButtonStyle(bgcolor="#10B981", color="#FFFFFF")),
            ],
        )
        page.dialog = settings_dlg
        settings_dlg.open = True
        page.update()

    def confirm_clear_chat(e):
        def do_clear(ev):
            page.client_storage.remove(STORAGE_KEY_CHAT_HISTORY)
            close_dialog(ev)
            reload_chat_history()
            page.snack_bar = ft.SnackBar(content=ft.Text("Chat cleared."), bgcolor="#1F2937")
            page.snack_bar.open = True
            page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Clear Chat History?"),
            content=ft.Text("Erases chat history stored on this device."),
            actions=[
                ft.TextButton("Cancel", on_click=lambda ev: close_dialog(ev)),
                ft.TextButton("Clear All", on_click=do_clear, style=ft.ButtonStyle(color="#EF4444")),
            ],
        )
        page.dialog = dlg
        dlg.open = True
        page.update()

    def close_dialog(e):
        if page.dialog:
            page.dialog.open = False
            page.update()

    # ------------------------------------------
    # TOP HEADER & APPBAR (PERSONAL BRANDING)
    # ------------------------------------------
    page.appbar = ft.AppBar(
        leading=ft.Container(padding=ft.padding.only(left=12), content=ft.CircleAvatar(bgcolor="#064E3B", content=ft.Icon(name=ft.Icons.AUTO_AWESOME_ROUNDED, color="#34D399", size=22))),
        title=ft.Column([
            ft.Text("Waqar Aslam Piracha", size=15, weight=ft.FontWeight.BOLD, color="#F9FAFB"),
            ft.Text("Personal Intelligence & Automation Hub", size=11, color="#34D399"),
        ], spacing=1),
        bgcolor="#111827",
        elevation=2,
        actions=[
            ft.IconButton(icon=ft.Icons.DELETE_SWEEP_ROUNDED, tooltip="Clear Chat", icon_color="#9CA3AF", on_click=confirm_clear_chat),
            ft.IconButton(icon=ft.Icons.SETTINGS_ROUNDED, tooltip="Settings", icon_color="#9CA3AF", on_click=open_settings),
        ],
    )

    app_tabs = ft.Tabs(
        selected_index=0,
        animation_duration=250,
        tabs=[
            ft.Tab(text="🧠 Second Brain Hub", icon=ft.Icons.PSYCHOLOGY_ROUNDED, content=tab1_content),
            ft.Tab(text="🎬 YouTube & Media Uploader", icon=ft.Icons.VIDEO_LIBRARY_ROUNDED, content=tab2_content),
        ],
        expand=True,
    )

    page.add(app_tabs)
    reload_chat_history()


if __name__ == "__main__":
    ft.app(target=main)
