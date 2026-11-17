# JARVIS — Windows AI Desktop Assistant

An autonomous personal AI assistant inspired by Iron Man's J.A.R.V.I.S., engineered specifically for Windows 10 & 11 with local-first intelligence, full PC automation, speech input/output, and persistent SQLite memory.

---

## 1. System Architecture & Features

- **Local AI Brain**: Powered by local Ollama (`llama3.2:3b` default, switchable to `llama3.1:8b`, `gemma4:12b`, etc.) with streaming responses, zero cloud APIs, and zero subscription costs.
- **Voice Interaction**:
  - Offline Voice Activity Detection (VAD) & SoundDevice microphone capture.
  - Speech-to-Text integration via `faster-whisper`.
  - Offline Text-to-Speech via native Windows SAPI voices with real-time speech interrupt support.
  - Push-to-Talk and continuous listening modes.
- **Windows PC Automation**:
  - **App Management**: Launch/close VS Code, Chrome, Notepad, Calculator, File Explorer, Task Manager, Paint, and any custom executable.
  - **File Operations**: Search files, create directories, create/read/rename/copy/move text files within secure allowed directory scopes.
  - **System & Hardware**: Real-time CPU, RAM, disk, battery monitoring, master volume control, mute/unmute, screenshot capture, and PC locking.
  - **Web & Media**: Google Search, YouTube search, URL launching.
- **Security & Safety Guardrails**:
  - LLM commands are strictly routed through a validated Command Router with predefined tool schemas.
  - Destructive operations (lock PC, file overwrites) require explicit confirmation.
  - Dedicated **Emergency Stop** halts any active speech, worker threads, and pending actions immediately.
- **Persistent Memory**:
  - SQLite database (`data/jarvis.db`) with SQLAlchemy ORM.
  - Complete multi-turn conversation logs, user preference notes, and session history management.
- **Futuristic Desktop UI**:
  - PySide6 (Qt) dark theme (#0a0e1a charcoal/navy with #00bcd4 cyan accents).
  - Central animated pulsing voice orb and dynamic audio waveform visualizer.
  - Live hardware monitoring cards and quick-action toolbars.
  - Windows System Tray integration (minimize to tray, restore, quit).

---

## 2. Target Hardware Requirements

- **Operating System**: Windows 10 / Windows 11 (64-bit)
- **Target Hardware**:
  - Intel i5-13450HX or equivalent
  - 16 GB System RAM
  - NVIDIA RTX 3050 (6 GB VRAM) / CUDA support
  - 512 GB SSD

---

## 3. Quick Start Guide

### Step 1: Verify Ollama Service
Ollama runs automatically in the background on Windows.
> **Note on `ollama serve`:** If running `ollama serve` yields `bind: Only one usage of each socket address is normally permitted`, Ollama is **already running** as a Windows background service! You do not need to start it manually.

Verify Ollama is responding:
```powershell
curl http://127.0.0.1:11434/api/tags
```

Ensure the recommended lightweight model is pulled:
```powershell
ollama pull llama3.2:3b
```

### Step 2: Run Setup Script
Run the automated Windows setup script:
```cmd
setup.bat
```
Or manually install dependencies:
```powershell
python -m pip install -r requirements.txt
```

### Step 3: Launch JARVIS
Double-click `start_jarvis.bat` or run:
```powershell
python main.py
```

---

## 4. Project Directory Structure

```
JARVIS/
│
├── main.py                    # Application entry point & Qt lifecycle
├── config.py                  # Environment settings, constants & logging
├── requirements.txt           # Python package requirements
├── setup.bat                  # Automated setup script
├── start_jarvis.bat           # Desktop launcher script
├── install_dependencies.bat   # Dependency installer
├── jarvis.spec                # PyInstaller packaging configuration
├── README.md                  # System manual and architecture reference
│
├── core/                      # Assistant brain & coordination
│   ├── ai_engine.py           # Ollama client, streaming, model management
│   ├── assistant.py           # Master assistant orchestrator
│   ├── command_router.py      # Validated tool routing & security barrier
│   ├── execution_engine.py    # Multi-step task execution engine
│   ├── permission_manager.py  # Permission policies and allow/denylists
│   └── task_planner.py        # Task decomposition and dependency tracking
│
├── voice/                     # Audio I/O and speech subsystem
│   ├── audio_manager.py       # Master voice state machine (Idle/Listen/Think/Speak)
│   ├── microphone.py          # SoundDevice audio capture & VAD monitoring
│   ├── speech_to_text.py      # Whisper STT engine with fallback
│   ├── text_to_speech.py      # Non-blocking pyttsx3 Windows SAPI speech engine
│   └── wake_word.py           # Wake word detection & keyword spotting
│
├── automation/                # Windows PC automation toolset
│   ├── app_launcher.py        # App registry, search & process launching
│   ├── browser_control.py     # Web search, URL navigation, YouTube
│   ├── file_manager.py        # Directory & file operations with path sanitization
│   ├── screenshot.py          # Multi-monitor & window screen capture
│   └── system_control.py      # Volume, system lock, hardware inspection
│
├── memory/                    # Persistent storage layer
│   ├── database.py            # SQLite engine & session management
│   ├── conversation.py        # SQLAlchemy models (Sessions & Messages)
│   └── memory_manager.py      # High-level memory CRUD & query API
│
├── services/                  # Background services
│   ├── system_monitor.py      # Real-time CPU, RAM, battery, network metrics
│   └── notification_service.py# Windows desktop toast notifications
│
├── ui/                        # PySide6 desktop interface
│   ├── main_window.py         # Master QMainWindow with sidebar navigation
│   ├── dashboard.py           # Central orb, waveform, system stats, quick tools
│   ├── chat_page.py           # Multi-turn streaming chat interface
│   ├── voice_page.py          # Voice controls, sensitivity, STT selector
│   ├── automation_page.py     # Direct Windows automation action center
│   ├── history_page.py        # Task and conversation session history table
│   ├── memory_page.py         # Stored memories, preferences, and notes
│   ├── settings_page.py       # Multi-tab preference and permissions manager
│   ├── about_page.py          # Hardware specifications & system diagnostics
│   └── widgets/               # Custom futuristic UI components
│       ├── orb_widget.py      # Animated pulsing JARVIS central orb
│       ├── waveform_widget.py # Live audio waveform bars
│       ├── message_bubble.py  # User & Assistant chat bubbles
│       ├── stat_card.py       # Futuristic hardware metric cards
│       └── sidebar_button.py  # Glowing navigation sidebar buttons
│
├── tests/                     # Unit & integration test suite
│   ├── test_ai_engine.py      # Ollama inference & intent extraction tests
│   ├── test_automation.py     # Automation tools & file manager tests
│   ├── test_memory.py         # Database persistence & session tests
│   └── test_agent_and_security.py # Security permissions & UI tests
│
├── data/                      # Local SQLite database (jarvis.db)
└── logs/                      # Application execution logs (jarvis.log)
```

---

## 5. Running the Test Suite

Execute the full suite of unit and integration tests:
```powershell
python -m unittest discover -s tests -v
```
All 17 tests covering the AI engine, automation tools, database persistence, permission security, task planning, and UI components execute in <10 seconds.

---

## 6. Building the Windows Executable (.exe)

To package JARVIS into a standalone Windows executable:
```powershell
python -m pip install pyinstaller
pyinstaller jarvis.spec
```
The resulting executable will be generated in `dist/JARVIS/JARVIS.exe`.
