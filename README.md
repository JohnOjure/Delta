# Delta: Self-Extensible Agent System

A portable agent core that reasons and plans, paired with a sandboxed execution runtime that allows the agent to dynamically write, load, introspect, and execute its own extension code.

## Architecture

```
Layer 1: Agent Core (Gemini-powered reasoning)
    ↓
Layer 2: Execution VM (RestrictedPython sandbox)
    ↓
Layer 3: Environment Adapter (platform-specific capabilities)
```

## Quick Start

1. **Install dependencies:**

```bash
pip install -r requirements.txt
```

2. **Set your Gemini API key:**

```bash
# Windows
set GEMINI_API_KEY=your-key-here

# Linux/Mac
export GEMINI_API_KEY=your-key-here
```

3. **Run with a goal:**

```bash
python main.py "Create a tool that reads a file and counts the words"
```

4. **Or run interactively:**

```bash
python main.py --interactive
```

## Commands (Interactive Mode)

- `goal <description>` - Give the agent a goal to accomplish
- `list` - List all registered extensions
- `show <name>` - View extension source code
- `run <name>` - Execute an extension
- `quit` - Exit

## How It Works

1. **You give the agent a goal** (natural language)
2. **Agent plans** how to achieve it using available capabilities
3. **Agent creates extensions** (Python code) when needed
4. **Extensions run in sandbox** with only allowed capabilities
5. **Agent reflects** on results and improves

## Capabilities

The desktop adapter provides:

| Capability       | Description                                |
| ---------------- | ------------------------------------------ |
| `fs.read`        | Read file contents                         |
| `fs.write`       | Write to files                             |
| `fs.list`        | List directory contents                    |
| `net.fetch`      | Make HTTP requests                         |
| `storage.get`    | Get from key-value store                   |
| `storage.set`    | Save to key-value store                    |
| `storage.delete` | Delete from key-value store                |
| `shell.exec`     | Execute shell commands (safety reviewed)   |
| `python.exec`    | Run Python code directly (safety reviewed) |

> **Note:** Shell commands are reviewed by an AI safety agent before execution. Dangerous operations (deleting system files, privilege escalation, etc.) are automatically blocked.

## Extension Example

Extensions are Python functions that receive capabilities as parameters:

```python
def extension_main(fs_read, fs_write):
    """Read a file and save it uppercased."""
    content = fs_read(path="input.txt")
    result = content.upper()
    fs_write(path="output.txt", content=result)
    return {"status": "done", "chars": len(result)}
```

## Project Structure

```
delta/
├── src/
│   ├── core/           # Agent intelligence (Gemini)
│   ├── vm/             # Sandboxed execution
│   ├── adapters/       # Environment interfaces
│   ├── capabilities/   # Capability implementations
│   ├── extensions/     # Extension management
│   └── models/         # Data models
├── data/               # SQLite databases
├── main.py             # Entry point
└── requirements.txt
```
