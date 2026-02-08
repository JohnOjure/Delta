# Delta Agent: Autonomous Recursive Intelligence System

## Overview
Delta is an advanced, self-evolving artificial intelligence agent designed for autonomous task execution and recursive self-improvement. Built upon a modular architecture, the system leverages Google's Gemini 3.0 Pro models to reason, plan, and execute complex workflows within a local computing environment.

Distinguished from traditional conversational interfaces, Delta operates with full agency. It possesses the capability to manipulate files, execute arbitrary code, interact with network resources, and continuously refine its own toolset through a recursive extension mechanism.

## Architecture
The system is engineered around a tripartite "Kernel-Cortex" design:

1.  **Cortex (Reasoning Engine)**: The cognitive core, powered by Gemini 3.0, responsible for high-level planning, decision-making, and error analysis.
2.  **Kernel (Execution Engine)**: A secure, sandboxed runtime environment that manages memory, executes actions, and enforces resource limits.
3.  **Peripherals (Adapters)**: Modular interfaces that bridge the refined logic of the Cortex with the raw capabilities of the host operating system.

## Capabilities
Delta is equipped with a comprehensive suite of native capabilities, extensible through dynamic runtime generation.

### Core Capabilities
-   **Filesystem operations**: Read, write, and list files with granular permission control.
-   **Shell Execution**: Execute system commands and scripts (Bash, Python) within a controlled environment.
-   **Network Access**: Perform HTTP/HTTPS requests to retrieve data or interact with external APIs.
-   **Persistent Storage**: Maintain state across sessions using an integrated SQLite-backed key-value store.
-   **Computer Vision**: Capture and analyze screen content to debug visual errors or interpret UI elements.

### Cognitive Features
-   **Recursive Planning**: Deconstructs abstract goals into executable, step-by-step plans.
-   **Self-Correction**: Automatically detects execution failures (e.g., syntax errors, API timeouts) and reformulates strategies dynamically.
-   **Persistent Memory ("Soul")**: Maintains a continuous identity via `SOUL.md` and learns user preferences (`USER.md`) over time to adapt its behavior.
-   **Proactive Monitoring ("Heartbeat")**: Periodically evaluates system health and user-defined constraints (e.g., disk usage, schedule conflicts) to preemptively address issues.

### Safety Net Extensions
Delta includes hardcoded "Safety Net" extensions that are always available, ensuring basic functionality even if LLM code generation fails:
-   `fs_read` - Read file contents
-   `fs_write` - Write/create files
-   `fs_list` - List directory contents
-   `fs_search` - Search for files by pattern
-   `system_stats` - Get system resource usage

### Security Features
-   **API Key Masking**: API keys are never exposed in the Web UI configuration endpoint.
-   **Sandboxed Execution**: All generated code runs in a restricted Python environment with resource limits.

## Installation

### Prerequisites
-   **Operating System**: Linux (Ubuntu/Debian recommended) or macOS.
-   **Runtime**: Python 3.10 or higher.
-   **Version Control**: Git.

### Installation Procedure
To install Delta, execute the following commands in your terminal:

## Installation

For detailed instructions, troubleshooting, and manual setup, please see [INSTALLATION.md](INSTALLATION.md).

### Quick Start
```bash
git clone https://github.com/fluxx/delta.git
cd delta
./install.sh
```
This single command handles dependencies, configuration, and launches the onboarding wizard.

## Configuration
The Onboarding Wizard will guide you through the initial setup. Configuration data is stored securely in `~/.delta/config.json`.

### Manual Configuration
You may manually edit the configuration file to adjust system parameters:

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `model_name` | string | The Gemini model identifier (e.g., `gemini-3-pro-preview`). |
| `api_key` | string | Your Google Gemini API key. |
| `voice_enabled` | boolean | Toggles text-to-speech output. |
| `usage_limit` | integer | Maximum number of API requests allowed per day. |

## Usage

### Web Interface
For the optimal user experience, launch the Delta Web Interface:
1.  Run `./install.sh` (or click the desktop shortcut).
2.  The interface provides real-time chat, visual indicators of the agent's thought process ("Thinking"), and direct access to system settings.

### Command Line Interface (CLI)
For headless operation or system integration, use the CLI:

```bash
# Start interactive mode
python3 main.py

# Execute a single goal
python3 main.py --goal "Analyze system logs for errors"
```

### Daemon Mode
To run Delta as a background service for proactive monitoring:
```bash
python3 src/daemon/service.py
```
This enables the "Heartbeat" functionality defined in `~/.delta/HEARTBEAT.md`.

## Project Status & Roadmap

Delta is currently in **Beta (v0.9)**. The core reasoning and execution engines are stable.

### Current Roadmap
-   [ ] **WhatsApp/Telegram Integration**: Native support for chat apps via QR code scanning (Planned v1.1).
-   [ ] **Docker Support**: Containerized deployment for enhanced security.
-   [ ] **Voice Input (Linux)**: Advanced voice recognition improvements.

---

## FAQ

### Does it remember me?
**Yes.** Delta uses a persistent SQLite database (`~/.delta/memory.db`) and Markdown files (`SOUL.md`, `USER.md`). It remembers your conversations, preferences, and the tools it creates across restarts.

### Is this useful?
Unlike standard chatbots that only *talk*, Delta can **act**. It creates its own Python scripts to solve problems.
-   **Example**: "Find all large PDF files in Downloads and move them to a new folder." -> Delta writes and runs a script to do this.
-   **Example**: "Check the weather every morning." -> Delta creates a cron job.
-   **Value**: It automates real local tasks without sending your data to a third-party server (besides the LLM inference).

---

## Disclaimer
Delta is an experimental autonomous system with the capability to execute code and modify files. While built with safety sandboxes, users are advised to review the code and use the system within a controlled environment.
