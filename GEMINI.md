# AiModding-Companion

**AiModding-Companion** is a modular, AI-powered desktop application designed to assist with coding, refactoring, and project management. It leverages a swarm of AI agents (Google Gemini, DeepSeek) and a robust RAG (Retrieval-Augmented Generation) system to provide context-aware assistance.

## 🚀 Getting Started

### Prerequisites
*   Python 3.10+
*   Windows (primary target OS based on `Start.bat` and `win32` dependencies)

### Installation
1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd AiModding-Companion
    ```
2.  **Install dependencies:**
    (Ensure you have a virtual environment active)
    ```bash
    pip install -r requirements.txt
    ```
    *Key dependencies include:* `customtkinter`, `google-generativeai`, `litellm`, `pydantic`.

### Running the Application
*   **Quick Start (Windows):**
    Double-click `Start.bat` or run it from the terminal:
    ```cmd
    Start.bat
    ```
*   **Manual Start:**
    ```bash
    python run.py
    ```

## 🏗️ Architecture Overview

The project follows a modular architecture separating the UI, background processing, and feature logic.

### Core Directories

*   **`ui/` (User Interface):**
    *   Built with `customtkinter`.
    *   `main_window.py`: The main application entry point and layout.
    *   `widgets.py`: Custom UI components (Text editors, API status, etc.).
    *   Handles user input and displays updates via a `result_queue`.

*   **`worker/` (Background Processing):**
    *   `core.py`: Contains the `Worker` class which runs in a separate thread.
    *   Manages the `task_queue` to process AI requests without freezing the UI.

*   **`features/` (Modular Functionality):**
    *   **`context/` & `rag.py`:** Implements the Hybrid RAG system (Vector + FTS5) and Google Drive synchronization for the knowledge base.
    *   **`audio.py`:** Handles Speech-to-Text (ASR) and Text-to-Speech (TTS).
    *   **`BackupManager.py`:** Manages local backups of modified files.
    *   **`GitActions.py`:** Interfaces with Git for version control.

*   **`agents/` (AI Swarm):**
    *   `swarm_manager.py`: Orchestrates interaction between different agent personas.
    *   `agent_personas.py`: Defines system prompts for agents like "Coder", "Architect", "Manager".

*   **`config/` (Configuration):**
    *   `settings.py`: Central configuration (API keys, model selection, paths).
    *   `constants.py`: Global constants.

## 🧠 Key Systems

### RAG (Retrieval-Augmented Generation)
The system uses a **Hybrid RAG** approach:
1.  **Vector Search:** For semantic understanding.
2.  **FTS5 (SQLite):** For keyword-based precision.
3.  **Knowledge Base:** Can sync with a specific Google Drive folder (`AiModding_KnowledgeBase`) to index external documents.

### AI Agents & Models
The application is designed to be model-agnostic (via `litellm`) but currently emphasizes:
*   **Google Gemini:** Primary model for general tasks and context window.
*   **DeepSeek:** Utilized for "Reasoning" and complex coding tasks ("Coder", "Architect" personas).

## 🛠️ Development & Testing

### Configuration
Adjust settings in `config/settings.py` or via the UI "Paramètres" menu.
*   **API Keys:** Managed in `app_settings.json` (created on first run) or environment variables.

### Testing
Tests are located in the `tests/` directory.
Run tests using `pytest`:
```bash
pytest tests/
```

### Logging
*   **Unified Logger:** Used throughout the app (`features.UnifiedLogger`).
*   **Logs:** stored in `logs/` or `global_debug.log`.
*   **UI:** Log channels can be toggled via the "Logs 🛠️" menu in the application.

## 📝 Contribution Guidelines
*   **Modular Design:** When adding a new feature, place it in `features/` and expose a clean API.
*   **UI Updates:** Never block the main thread. Use `task_queue` to offload work and `result_queue` to send updates back to the UI.
