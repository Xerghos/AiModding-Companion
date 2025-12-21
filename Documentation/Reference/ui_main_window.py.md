```json
[
  {
    "subsystem": "UI",
    "component": "MainWindow",
    "functionality": "Main Application Window",
    "description": "Handles the creation and management of the main application window, including the layout, widgets, event handling, and interaction with the worker thread. It orchestrates the user interface for code editing, chat, file exploration, and application settings.",
    "files": [
      "ui/main_window.py"
    ],
    "dependencies": [
      "config/constants",
      "config/settings",
      "config/paths",
      "config/logs",
      "worker/core",
      "features/audio",
      "ui/syntax",
      "ui/widgets",
      "ui/windows",
      "features/UnifiedLogger",
      "features/Decorators"
    ],
    "widgets": [
      "CTkFrame",
      "CTkLabel",
      "CTkButton",
      "ttk.Treeview",
      "ttk.Scrollbar",
      "CTkTabview",
      "CTkTextbox",
      "CTkOptionMenu",
      "CTkFrame",
      "CTkButton",
      "CTkTextbox",
      "CTkButton",
      "CTkOptionMenu",
      "CTkLabel",
      "ApiKeyStatusMenu",
      "ReasoningModeSwitch",
      "TextEditorWithLineNumbers"
    ],
    "events": [
      "Key-<Return>",
      "Key-<Up>",
      "Key-<Down>",
      "<Double-1>",
      "<Button-3>",
      "<<TreeviewOpen>>",
      "Key-<Delete>"
    ],
    "state_variables": [
      "current_file_path",
      "status_var",
      "is_working",
      "is_streaming",
      "windows",
      "prompt_history",
      "history_index",
      "sidebar_visible"
    ],
    "methods": [
      "_setup_layout",
      "_create_toolbar_buttons",
      "_on_file_menu_action",
      "_on_save_file",
      "_on_open_file",
      "_open_settings",
      "_open_db_manager",
      "_open_backup_manager",
      "_open_waiting_list",
      "_setup_log_menu",
      "_toggle_log_channel",
      "_init_worker",
      "_setup_bindings",
      "_on_stop_shortcut",
      "_on_enter",
      "_on_send_click",
      "_refresh_explorer",
      "_populate_tree",
      "_on_tree_open",
      "_on_tree_double_click",
      "_open_file_in_tab",
      "_on_reasoning_mode_change",
      "_configure_chat_tags",
      "_log_chat",
      "_get_last_response",
      "_clear_chat",
      "check_result_queue",
      "_handle_asr_done",
      "_start_animation",
      "_stop_animation",
      "_show_context_menu",
      "_on_quick_action",
      "_history_up",
      "_history_down",
      "_load_prompt_history",
      "_save_prompt_history"
    ],
    "technical_debt": {
      "todos": [],
      "fixmes": []
    },
    "metrics": {
      "loc": 859,
      "complexity": 58,
      "todo_count": 0,
      "fixme_count": 0
    }
  }
]
```