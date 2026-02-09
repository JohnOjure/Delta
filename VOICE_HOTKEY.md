# Voice and Hotkey Features

Delta supports hands-free interaction via voice commands and keyboard shortcuts.

## Voice Command (Wake Word: "Hey Delta")

**Requirements:**

- Python packages: `SpeechRecognition`, `pyaudio`
- A working microphone

**Install Dependencies:**

```bash
pip install SpeechRecognition pyaudio
```

**Usage:**

1. Start Delta with the daemon or web UI: `delta --daemon` or `delta --web`
2. Say **"Hey Delta"** followed by your command
3. Example: "Hey Delta, what's the weather today?"

**Troubleshooting:**

- If voice doesn't work, ensure your microphone is the default input device
- On macOS, you may need to grant Terminal or Python microphone access in System Preferences
- On Linux, `pyaudio` may require `portaudio19-dev`: `sudo apt install portaudio19-dev`

## Hotkey (Ctrl+Shift+D)

**Requirements:**

- Python package: `pynput`

**Install Dependencies:**

```bash
pip install pynput
```

**Usage:**

1. Start Delta with the daemon: `delta --daemon`
2. Press **Ctrl+Shift+D** anywhere to invoke Delta
3. The default hotkey opens a text input prompt

**Troubleshooting:**

- On macOS, you may need to grant Terminal "Input Monitoring" permission in System Preferences > Security & Privacy
- On Linux, Wayland desktops may block global hotkeys; consider using X11

## Platform Notes

| Feature | Windows  | macOS                             | Linux                        |
| ------- | -------- | --------------------------------- | ---------------------------- |
| Voice   | ✅ Works | ✅ Works (grant mic access)       | ✅ Works (install portaudio) |
| Hotkey  | ✅ Works | ✅ Works (grant input monitoring) | ✅ Works (X11 only)          |
