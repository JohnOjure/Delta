# Installation & Usage Guide

## Prerequisites

Before installing Delta, ensure your system meets the following requirements:

*   **Operating System**: Linux (Ubuntu 22.04+ / Debian 12+ recommended) or macOS (Ventura+).
    *   *Note: Windows is supported via WSL2.*
*   **Python**: Version 3.10 or higher.
*   **Git**: Required for version control and updates.
*   **Browser**: Chrome or Brave (optional, for web browsing capabilities).

## Automatic Installation (Recommended)

The "Magic Installer" handles all dependencies, virtual environment creation, and configuration.

1.  **Clone the Repository**
    Open your terminal and run:
    ```bash
    git clone https://github.com/JohnOjure/Delta.git
    cd Delta
    ```

2.  **Run the Installer**
    Execute the setup script:
    ```bash
    ./install.sh
    ```

    **What this script does:**
    *   Checks for Python 3 and Git.
    *   Creates a `venv` (virtual environment) to keep your system clean.
    *   Installs Python dependencies from `requirements.txt`.
    *   Launches the **Onboarding Wizard**.
    *   Creates a Desktop Entry (Linux) for easy access.

3.  **Onboarding Wizard**
    The script will automatically launch `src/cli/setup.py`. Follow the prompts to:
    *   Enter your **Google Gemini API Key**.
    *   Choose your preferred model (Default: `gemini-3-pro-preview`).
    *   Set up your User Name (for `USER.md`).

## Manual Installation

If you prefer to set up everything manually:

1.  **Clone & Verify**
    ```bash
    git clone https://github.com/fluxx/delta.git
    cd delta
    ```

2.  **Create Virtual Environment**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configuration**
    Copy the example config (or create one):
    ```bash
    mkdir -p ~/.delta
    nano ~/.delta/config.json
    ```
    Content of `config.json`:
    ```json
    {
        "api": {
            "gemini_api_key": "YOUR_KEY_HERE"
        },
        "llm": {
            "model_name": "gemini-3-pro-preview"
        },
        "user": {
            "name": "User"
        }
    }
    ```

## Usage

### 1. Web Interface (GUI)
*   **Launch**: Run `./install.sh` (it detects existing installs and just launches) or run:
    ```bash
    ./venv/bin/python3 src/web/server.py
    ```
*   **Access**: Open `http://localhost:8000` in your browser.

### 2. Command Line Interface (CLI)
*   **Interactive Mode**:
    ```bash
    ./venv/bin/python3 main.py
    ```
*   **Single Command**:
    ```bash
    ./venv/bin/python3 main.py --goal "Research quantum computing"
    ```

### 3. Background Daemon (Ghost Mode)
To enable proactive monitoring (Heartbeat):
```bash
./venv/bin/python3 src/daemon/service.py
```
*   Checks `~/.delta/HEARTBEAT.md` every 30 minutes.
*   Monitors Downloads/Documents for new files to file.

## Troubleshooting

*   **`ModuleNotFoundError`**: Ensure you activated the venv (`source venv/bin/activate`).
*   **`403/401 API Error`**: specificy a valid API key in `~/.delta/config.json`.
*   **`404 Model Not Found`**: Ensure your API key has access to `gemini-3-pro-preview` or switch to `gemini-1.5-flash` in config.
