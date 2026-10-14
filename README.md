# Pocket Agent 🤖📱

**Pocket Agent** is a production-grade, native Android mobile application featuring an embedded autonomous AI Agent powered by Google's `gemini-2.5-flash` model. Built with Python Flet (`flet>=0.24.0`), it combines Flutter's high-performance native rendering on mobile with the Python `google-genai` SDK.

---

## 🌟 Key Features

1. **Modern Dark-Mode Mobile UI:**
   - Obsidian dark UI (`#0D1117`) tailored for AMOLED mobile screens.
   - Dual-style chat view: right-aligned accent user bubbles and left-aligned dark card agent bubbles with rich GitHub-flavored Markdown (tables, code blocks, math).
   - Real-time tool execution status pill badge when the agent invokes background functions.
   - Expandable input bar with multi-line support and instant send.

2. **Autonomous Toolset (Automatic Function Calling):**
   - `get_device_datetime()`: Fetches the local system clock and date.
   - `save_note(title, content)`: Stores notes and tasks securely to device local storage.
   - `read_notes()`: Retrieves all saved notes/tasks from local storage.
   - `trigger_webhook(url, payload_json)`: Executes HTTP POST requests to trigger external n8n workflows, APIs, or automations.
   - `quick_calculator(expression)`: AST-based safe mathematical and load formula evaluator without code execution risks.

3. **Offline Client Storage:**
   - Gemini API key, system prompt/persona, chat history, and notes are persisted directly on the device using `page.client_storage`.

4. **Zero-Setup Cloud APK Build:**
   - GitHub Actions CI/CD automatically compiles release APKs using `flet build apk --include-packages google-genai`.

---

## 📁 Project Structure

```text
pocket-agent/
├── .github/
│   └── workflows/
│       └── build-apk.yml     # Automated cloud build pipeline
├── .gitignore
├── pyproject.toml            # Flet app configuration & Android permissions
├── requirements.txt          # Python dependencies (flet, google-genai)
├── main.py                   # Complete mobile app UI and Agent runtime
└── README.md
```
