#!/usr/bin/env python3
"""
Delta Setup Wizard
Interactive CLI for configuring the agent.
"""

import os
import sys
import json
import time
from pathlib import Path

# Colors for TUI
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header():
    print(Colors.CYAN)
    print(r"""
  _____       _ _        
 |  __ \     | | |       
 | |  | | ___| | |_ __ _ 
 | |  | |/ _ \ | __/ _` |
 | |__| |  __/ | || (_| |
 |_____/ \___|_|\__\__,_|
                         
    SETUP WIZARD
    """)
    print(Colors.ENDC)

def type_writer(text, speed=0.01):
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(speed)
    print()

def get_config_path():
    return Path.home() / ".delta" / "config.json"

def load_existing_config():
    path = get_config_path()
    if path.exists():
        try:
            with open(path, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_config(config):
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"\n{Colors.GREEN}✓ Configuration saved to {path}{Colors.ENDC}")

def setup_wizard():
    print_header()
    
    current_config = load_existing_config()
    
    type_writer(f"{Colors.BOLD}Welcome to Delta.{Colors.ENDC}")
    type_writer("I am an autonomous agent designed to help you accomplish tasks.\n")
    
    print(f"{Colors.YELLOW}Let's get you set up.{Colors.ENDC}\n")
    
    # 1. User Name
    default_name = current_config.get("user_name", os.getlogin().capitalize())
    name = input(f"{Colors.BLUE}[?] What should I call you?{Colors.ENDC} ({default_name}): ").strip()
    if not name:
        name = default_name
        
    # 2. AI Model Provider (Gemini only for now)
    print(f"\n{Colors.BLUE}[?] AI Model Configuration:{Colors.ENDC}")
    print("Delta uses Google Gemini (Fast, Smart, Multimodal).")
    
    api_key = current_config.get("api_key", "")
    if api_key:
        mask = api_key[:4] + "*" * (len(api_key)-8) + api_key[-4:]
        print(f"Current Key: {mask}")
        keep = input("Keep this key? [Y/n]: ").lower().strip()
        if keep == 'n':
            api_key = ""
            
    if not api_key:
        print(f"\n{Colors.BOLD}You need a Google Gemini API Key.{Colors.ENDC}")
        print("Get one here: https://aistudio.google.com/app/apikey")
        while not api_key:
            api_key = input(f"{Colors.GREEN}Enter your API Key:{Colors.ENDC} ").strip()
            
    # 3. Model Selection
    print(f"\n{Colors.BLUE}[?] Select Model:{Colors.ENDC}")
    models = [
        "gemini-3-pro-preview (Recommended - Latest & Most Capable)",
        "gemini-2.0-flash (Fast & Efficient)"
    ]
    for i, m in enumerate(models):
        print(f"{i+1}. {m}")
        
    choice = input("Select [1-2] (Default: 1): ").strip()
    model_name = "gemini-3-pro-preview"
    if choice == "2":
        model_name = "gemini-2.0-flash"
        
    # 4. Voice
    print(f"\n{Colors.BLUE}[?] Voice Interaction:{Colors.ENDC}")
    voice_enabled = current_config.get("voice_enabled", False)
    v_choice = input(f"Enable voice mode ('Hey Delta')? [y/N] ({'yes' if voice_enabled else 'no'}): ").lower().strip()
    if v_choice == 'y':
        voice_enabled = True
    elif v_choice == 'n':
        voice_enabled = False
        
    # 5. Save
    config = {
        "user_name": name,
        "api_key": api_key,
        "model_name": model_name,
        "voice_enabled": voice_enabled,
        "usage_limit": current_config.get("usage_limit", 100),
        "auto_switch_model": True
    }
    
    save_config(config)
    
    print(f"\n{Colors.CYAN}========================================{Colors.ENDC}")
    print(f"{Colors.BOLD}🎉 Setup Complete!{Colors.ENDC}")
    print(f"{Colors.CYAN}========================================{Colors.ENDC}")
    print("\nYou can now:")
    print(f"1. Run {Colors.GREEN}./install.sh{Colors.ENDC} again to launch")
    print(f"2. Or run {Colors.GREEN}python main.py --web{Colors.ENDC}")
    print(f"3. Or click the {Colors.BOLD}Delta Agent{Colors.ENDC} icon in your menu")
    
    # Prompt to launch now
    launch = input(f"\n{Colors.YELLOW}Launch Web UI now? [Y/n]:{Colors.ENDC} ").lower().strip()
    if launch != 'n':
        import subprocess
        # Assuming we are in project root or src/cli
        # We need to find main.py relative to here
        root = Path(__file__).parent.parent.parent
        main_py = root / "main.py"
        try:
            print(f"🚀 Launching at http://127.0.0.1:8000 ...")
            # Using sys.executable to ensure we use the same python (venv)
            subprocess.run([sys.executable, str(main_py), "--web"])
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    try:
        setup_wizard()
    except KeyboardInterrupt:
        print("\nSetup cancelled.")
