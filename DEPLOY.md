# Deploying Delta Agent

Delta is designed to be a self-contained, intelligent agent that lives on your system.

## Prerequisites

- Python 3.10+
- Google Gemini API Key ([Get one here](https://aistudio.google.com/app/apikey))

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-repo/delta.git
    cd delta
    ```

2.  **Create a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run Setup:**
    ```bash
    python main.py
    ```
    This will launch the interactive setup wizard where you can enter your API key, choose your preferred model, and set usage limits.

## running Delta

### Interactive Mode (CLI)
Start talking to Delta directly in your terminal:
```bash
python main.py --interactive
```

### Background Service (Daemon)
Start Delta as a background service:
```bash
delta start
```
Check status:
```bash
delta status
```

## Configuration

You can change your settings at any time:
```bash
delta config --show
```

To update settings:
```bash
# Change model
delta config --model gemini-1.5-pro

# Update user name
delta config --name "Your Name"

# Update API Key
delta config --api-key YOUR_NEW_KEY
```

## Features

-   **Self-Correction**: If Delta encounters an error (like a model being overloaded), it will automatically try to switch to a different model to keep working.
-   **Extensions**: Delta writes its own Python extensions to solve tasks. These are saved in `data/extensions.db`.
-   **Ghost Mode**: Runs in the background (if enabled) to proactively monitor and assist.

## Troubleshooting

-   **"Model not found"**: Delta should auto-switch, but you can manually set a different model via `delta config`.
-   **Permission errors**: Ensure you have read/write access to the `data/` directory.
