# Delta: A Self-Extensible Autonomous Agent System

Delta is a desktop-native autonomous agent framework that enables persistent, proactive AI assistance through self-generated code extensions. Unlike conventional chatbot interfaces, Delta operates as a background system service with full access to local resources, allowing it to execute tasks, learn from interactions, and provide contextual assistance without explicit invocation.

---

## Abstract

Modern AI assistants are constrained by stateless, request-response interaction models that limit their utility for complex, ongoing tasks. Delta addresses this limitation by implementing a self-extensible agent architecture that:

1. **Persists across sessions** through SQLite-backed episodic and semantic memory
2. **Generates executable code** to solve novel problems dynamically
3. **Monitors system state** to provide proactive, context-aware assistance
4. **Enforces security boundaries** through capability-based sandboxed execution

The system demonstrates that practical desktop autonomy is achievable with current LLM capabilities when combined with appropriate architectural constraints.

---

## Table of Contents

- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Architecture](#architecture)
- [Security Model](#security-model)
- [API Reference](#api-reference)
- [Testing](#testing)
- [Contributing](#contributing)
- [License](#license)

---

## System Requirements

| Requirement | Specification |
|-------------|---------------|
| Python | 3.11 or higher |
| Operating System | Linux (primary), macOS, Windows |
| Memory | 512 MB minimum |
| API Access | Google Gemini API key |

### Optional Dependencies

| Feature | Requirement |
|---------|-------------|
| Voice activation | PortAudio system library |
| Global hotkeys | X11 or Wayland compositor |
| System tray | GTK3 or Qt5 |

---

## Installation

```bash
git clone https://github.com/yourusername/delta.git
cd delta
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Verify Installation

```bash
python -m pytest tests/ -v
```

Expected output: `78 passed`

---

## Configuration

### API Key Setup

```bash
python -m src.cli.cli config --api-key <GEMINI_API_KEY>
```

Configuration is stored in `~/.delta/.env`. Alternative: set the `GEMINI_API_KEY` environment variable directly.

### Configuration Options

| Parameter | Description | Default |
|-----------|-------------|---------|
| `GEMINI_API_KEY` | Google Gemini API authentication | Required |
| `DELTA_DATA_DIR` | Data storage location | `~/.delta` |
| `DELTA_LOG_LEVEL` | Logging verbosity | `INFO` |

---

## Usage

### Command-Line Interface

```bash
# Execute a single goal
python -m src.cli.cli ask "List Python files in the current directory"

# Interactive session
python -m src.cli.cli shell

# Daemon management
python -m src.cli.cli start [--foreground]
python -m src.cli.cli stop
python -m src.cli.cli status
python -m src.cli.cli logs [-n LINES]
```

### Web Interface

```bash
python run_server.py
```

Access at `http://localhost:8000`. The web interface provides real-time status updates during task execution.

### Invocation Methods

| Method | Trigger | Requirements |
|--------|---------|--------------|
| CLI | `python -m src.cli.cli ask "..."` | None |
| Interactive Shell | `python -m src.cli.cli shell` | None |
| Global Hotkey | `Ctrl+Shift+D` | pynput, daemon running |
| Voice | "Hey Delta" followed by command | SpeechRecognition, microphone |
| Web UI | HTTP request | FastAPI server running |

### Daemon Installation (systemd)

```bash
mkdir -p ~/.config/systemd/user
cp install/delta.service ~/.config/systemd/user/

# Edit paths in service file as needed
systemctl --user daemon-reload
systemctl --user enable delta
systemctl --user start delta
```

---

## Architecture

### System Overview

```
                    ┌─────────────────────────────────────────┐
                    │              User Interface             │
                    │  CLI │ Web UI │ Hotkey │ Voice │ Tray   │
                    └─────────────────┬───────────────────────┘
                                      │
                    ┌─────────────────▼───────────────────────┐
                    │            Daemon Service               │
                    │         (Background Process)            │
                    └─────────────────┬───────────────────────┘
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        │                             │                             │
        ▼                             ▼                             ▼
┌───────────────┐           ┌─────────────────┐           ┌─────────────────┐
│  Ghost Mode   │           │   Core Agent    │           │    Memory       │
│  (Proactive)  │           │   (Reactive)    │           │   (Persistent)  │
└───────────────┘           └────────┬────────┘           └─────────────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │                │                │
                    ▼                ▼                ▼
            ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
            │   Planner   │  │  Generator  │  │   Executor  │
            └─────────────┘  └─────────────┘  └──────┬──────┘
                                                     │
                                              ┌──────▼──────┐
                                              │   Sandbox   │
                                              │  (Isolated) │
                                              └─────────────┘
```

### Module Descriptions

#### Core (`src/core/`)

| Module | Purpose |
|--------|---------|
| `agent.py` | Main control loop implementing goal decomposition and execution |
| `gemini_client.py` | LLM interface with structured output parsing and function calling |
| `memory.py` | Persistent storage of interactions, learnings, and user preferences |
| `ghost.py` | Background monitoring for proactive assistance triggers |
| `planner.py` | Task decomposition and strategy selection |
| `generator.py` | Python code generation for novel capabilities |

#### Capabilities (`src/capabilities/`)

Capabilities define the agent's permitted operations. Each capability implements an async interface with explicit parameter validation.

| Capability | Operations |
|------------|------------|
| `filesystem` | Read, write, list, search files and directories |
| `shell` | Execute system commands with output capture |
| `network` | HTTP requests (GET, POST) with response parsing |
| `storage` | Persistent key-value storage for extensions |
| `vision` | Screenshot capture and image analysis |

#### Virtual Machine (`src/vm/`)

| Module | Purpose |
|--------|---------|
| `sandbox.py` | RestrictedPython-based execution environment |
| `executor.py` | Process isolation with timeout enforcement |

#### Extensions (`src/extensions/`)

Extensions are agent-generated Python modules stored in SQLite with versioning support.

| Module | Purpose |
|--------|---------|
| `registry.py` | Extension storage, retrieval, and version management |
| `loader.py` | Capability binding and extension execution |

### Data Flow

1. **Input Processing**: User goal received via any interface
2. **Planning**: Agent decomposes goal into executable steps
3. **Capability Check**: Required capabilities identified and validated
4. **Extension Lookup**: Existing extensions searched for reuse
5. **Code Generation**: New extension generated if needed
6. **Sandboxed Execution**: Extension runs in isolated process
7. **Result Processing**: Output validated and returned to user
8. **Memory Update**: Interaction stored for future reference

---

## Security Model

Delta implements defense-in-depth through multiple isolation layers.

### Execution Sandbox

Extensions execute in a RestrictedPython environment that:

- Disables arbitrary imports (`__import__` blocked)
- Prevents direct builtin access
- Restricts attribute and item access via guards
- Limits available operations to a safe subset

### Process Isolation

```python
# Extensions run in separate processes with enforced timeouts
process = multiprocessing.Process(target=execute_extension, args=(code, bindings))
process.start()
process.join(timeout=CPU_TIME_LIMIT)
if process.is_alive():
    process.terminate()
```

### Capability-Based Access Control

Extensions must declare required capabilities. The loader validates declarations against available capabilities before execution.

```python
# Extension metadata
{
    "name": "file_organizer",
    "required_capabilities": ["fs.read", "fs.write", "fs.list"]
}
```

### Blocked Operations

| Category | Examples |
|----------|----------|
| System | `os.system`, `subprocess`, `eval`, `exec` |
| Network (unsafe) | Raw sockets, direct DNS |
| Filesystem (unsafe) | Path traversal, symlink following outside sandbox |
| Introspection | `__class__`, `__bases__`, `__subclasses__` |

---

## API Reference

### CLI Commands

| Command | Arguments | Description |
|---------|-----------|-------------|
| `ask` | `GOAL` | Execute a single goal |
| `shell` | — | Start interactive session |
| `start` | `[--foreground]` | Start daemon |
| `stop` | — | Stop daemon |
| `restart` | — | Restart daemon |
| `status` | — | Display daemon status |
| `logs` | `[-n LINES]` | Display recent logs |
| `config` | `--api-key KEY` or `--show` | Manage configuration |

### WebSocket Protocol

The web interface communicates via WebSocket at `/ws`.

**Client to Server:**
```json
{"type": "goal", "goal": "string"}
```

**Server to Client:**
```json
{"type": "status", "status": "started|thinking|complete", ...}
{"type": "thinking", "state": "string", "activity": "string", ...}
{"type": "result", "success": boolean, "response": "string", ...}
{"type": "error", "error": "string"}
```

---

## Testing

### Run Full Test Suite

```bash
python -m pytest tests/ -v
```

### Run Specific Test Categories

```bash
# Core functionality
python -m pytest tests/test_executor.py tests/test_sandbox.py -v

# System agent features
python -m pytest tests/test_daemon.py tests/test_cli.py tests/test_ghost.py -v
```

### Test Coverage

```bash
python -m pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html
```

### Current Test Status

| Test File | Tests | Status |
|-----------|-------|--------|
| `test_executor.py` | 10 | Passing |
| `test_sandbox.py` | 9 | Passing |
| `test_capabilities.py` | 7 | Passing |
| `test_registry.py` | 7 | Passing |
| `test_daemon.py` | 12 | Passing |
| `test_cli.py` | 10 | Passing |
| `test_ghost.py` | 14 | Passing |
| `test_hotkey.py` | 5 | Passing |
| `test_voice.py` | 5 | Passing |
| **Total** | **78** | **Passing** |

---

## Project Status

| Component | Implementation | Tests |
|-----------|----------------|-------|
| Core Agent Loop | Complete | Partial |
| LLM Integration (Gemini) | Complete | — |
| Sandboxed Execution | Complete | Complete |
| Persistent Memory | Complete | — |
| Extension Registry | Complete | Complete |
| CLI Interface | Complete | Complete |
| Web Interface | Complete | — |
| Background Daemon | Complete | Complete |
| Global Hotkey | Complete | Complete |
| Voice Activation | Complete | Complete |
| Ghost Mode (Proactive) | Complete | Complete |
| System Tray | Complete | — |

---

## Dependencies

### Required

| Package | Purpose | Version |
|---------|---------|---------|
| google-genai | Gemini API client | >=1.0.0 |
| RestrictedPython | Sandboxed execution | >=7.0 |
| pydantic | Data validation | >=2.0 |
| aiosqlite | Async SQLite | >=0.19.0 |
| httpx | HTTP client | >=0.27.0 |
| click | CLI framework | >=8.1.0 |
| fastapi | Web framework | >=0.115.0 |
| uvicorn | ASGI server | >=0.34.0 |
| psutil | System monitoring | >=5.9.0 |
| watchdog | File system events | >=4.0.0 |

### Optional

| Package | Purpose | Version |
|---------|---------|---------|
| pynput | Global hotkeys | >=1.7.6 |
| pystray | System tray | >=0.19.5 |
| Pillow | Image processing | >=10.0.0 |
| SpeechRecognition | Voice input | >=3.10.0 |

---

## Contributing

Contributions are welcome. Please ensure:

1. All tests pass: `python -m pytest tests/ -v`
2. New features include corresponding tests
3. Code follows existing style conventions
4. Documentation is updated as needed

---

## License

MIT License. See LICENSE file for details.

---

## Acknowledgments

- Google DeepMind for the Gemini API
- The RestrictedPython project for secure execution primitives
- The FastAPI project for the web framework

---

## Citation

If you use Delta in academic work, please cite:

```bibtex
@software{delta2024,
  title={Delta: A Self-Extensible Autonomous Agent System},
  author={[Author]},
  year={2024},
  url={https://github.com/yourusername/delta}
}
```
