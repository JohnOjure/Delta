# Global Delta CLI Usage Guide

Delta is designed to be accessible from anywhere in your terminal, acting like a system-wide tool.

## Verification

To verify that Delta is correctly installed globally, open a **NEW** terminal window and run:

```bash
delta --help
```

If you see the Delta help message, you are all set! 🚀

## Troubleshooting "Command Not Found"

If you see `command not found: delta` or similar errors, it means the installation directory is not in your system's `PATH`.

### Windows

1.  **Restart your Terminal**: Windows requires a new terminal session to pick up PATH changes.
2.  **Manual Fix**:
    - Search for "Edit the system environment variables".
    - Click "Environment Variables".
    - Under "User variables", find `Path` and edit it.
    - Add the full path to your Delta project folder (e.g., `C:\Users\YourName\Projects\Delta`).

### macOS and Linux

You need to ensure `~/.local/bin` is in your `$PATH`.

1.  **Check your shell**:

    ```bash
    echo $SHELL
    ```

2.  **Add to configuration**:

    **For Bash (`/bin/bash`)**:

    ```bash
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    source ~/.bashrc
    ```

    **For Zsh (`/bin/zsh`)** (Default on macOS):

    ```bash
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
    source ~/.zshrc
    ```

3.  **Verify**:
    ```bash
    delta --help
    ```

## Running the Web UI Globally

You can also start the Web UI from anywhere:

```bash
delta --web
```

Or run the background daemon:

````bash
```bash
delta --daemon
````

## Proactive Optimization

Delta includes a built-in optimization engine that analyzes its own logs to identify performance bottlenecks and reliability issues.

To trigger a proactive self-improvement cycle:

```bash
delta optimize
```

This will:

1. Analyze audit logs for failures or slow tools.
2. Formulate an optimization plan.
3. Automatically refactor code to improve performance.
