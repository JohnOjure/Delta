#!/usr/bin/env python3
"""
Delta Agent - Cross-Platform Installer
Installs dependencies, sets up environment, and configures launchers.
"""

import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path

# Colors
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

if platform.system() == "Windows":
    pass

def print_banner():
    print(f"{Colors.CYAN}")
    print(r"""
  _____       _ _        
 |  __ \     | | |       
 | |  | | ___| | |_ __ _ 
 | |  | |/ _ \ | __/ _` |
 | |__| |  __/ | || (_| |
 |_____/ \___|_|\__\__,_|
                         
   AI AGENT INSTALLER
""")
    print(f"{Colors.ENDC}")

def check_python():
    print(f"{Colors.BLUE}[*] Checking Python version...{Colors.ENDC}")
    if sys.version_info < (3, 10):
        print(f"{Colors.RED}[!] Python 3.10+ is required. You have {sys.version}.{Colors.ENDC}")
        sys.exit(1)
    print(f"{Colors.GREEN}[+] Python version ok.{Colors.ENDC}")

def create_venv():
    venv_dir = Path("venv")
    if venv_dir.exists():
        print(f"{Colors.YELLOW}[-] Virtual environment 'venv' already exists.{Colors.ENDC}")
        return

    print(f"{Colors.BLUE}[*] Creating virtual environment...{Colors.ENDC}")
    subprocess.check_call([sys.executable, "-m", "venv", "venv"])
    print(f"{Colors.GREEN}[+] Virtual environment created.{Colors.ENDC}")

def get_venv_python():
    if platform.system() == "Windows":
        return Path("venv") / "Scripts" / "python.exe"
    else:
        return Path("venv") / "bin" / "python"

def install_dependencies():
    print(f"{Colors.BLUE}[*] Installing dependencies...{Colors.ENDC}")
    python_exec = get_venv_python()
    
    try:
        subprocess.check_call([str(python_exec), "-m", "pip", "install", "--upgrade", "pip"], stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print(f"{Colors.YELLOW}[!] Warning: Failed to upgrade pip. Continuing...{Colors.ENDC}")
    
    try:
        subprocess.check_call([str(python_exec), "-m", "pip", "install", "-r", "requirements.txt"])
        print(f"{Colors.GREEN}[+] Dependencies installed.{Colors.ENDC}")
    except subprocess.CalledProcessError as e:
        print(f"{Colors.RED}[!] Failed to install dependencies.{Colors.ENDC}")
        sys.exit(1)

def create_windows_shortcut(target, shortcut_path, arguments="", icon=""):
    """Create a Windows shortcut using VBScript."""
    vbs_script = f"""
    Set oWS = WScript.CreateObject("WScript.Shell")
    sLinkFile = "{shortcut_path}"
    Set oLink = oWS.CreateShortcut(sLinkFile)
    oLink.TargetPath = "{target}"
    oLink.Arguments = "{arguments}"
    oLink.IconLocation = "{icon}"
    oLink.Save
    """
    vbs_file = Path("create_shortcut.vbs")
    with open(vbs_file, "w") as f:
        f.write(vbs_script)
    
    try:
        subprocess.check_call(["cscript", "//Nologo", str(vbs_file)])
    finally:
        if vbs_file.exists():
            vbs_file.unlink()

def add_to_path_windows(path_to_add):
    """Add a directory to the User PATH environment variable on Windows."""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS)
        try:
            current_path, _ = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current_path = ""
            
        if str(path_to_add) not in current_path:
            new_path = f"{current_path};{path_to_add}" if current_path else str(path_to_add)
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
            print(f"{Colors.GREEN}[+] Added {path_to_add} to User PATH.{Colors.ENDC}")
            print(f"{Colors.YELLOW}[!] You MUST restart your terminal for changes to take effect.{Colors.ENDC}")
            return True
        else:
            print(f"{Colors.GREEN}[-] Path already in User PATH.{Colors.ENDC}")
            return False
    except Exception as e:
        print(f"{Colors.RED}[!] Failed to update PATH: {e}{Colors.ENDC}")
        return False

def check_path_visibility(install_path):
    """Check if the installation path is in the user's PATH and warn if not."""
    print(f"{Colors.BLUE}[*] Verifying PATH configuration...{Colors.ENDC}")
    
    system_path = os.environ.get("PATH", "")
    install_path_str = str(install_path).rstrip(os.sep)
    
    if platform.system() == "Windows":
        system_paths = [p.strip().lower() for p in system_path.split(";")]
        install_check = install_path_str.lower()
    else:
        system_paths = [p.strip() for p in system_path.split(":")]
        install_check = install_path_str
        
    if any(os.path.normpath(p).lower() == os.path.normpath(install_check).lower() for p in system_paths):
        print(f"{Colors.GREEN}[+] '{install_path}' is in your PATH. Global commands should work.{Colors.ENDC}")
    else:
        print(f"{Colors.YELLOW}[!] WARNING: '{install_path}' is NOT in your PATH.{Colors.ENDC}")
        print(f"{Colors.YELLOW}    You may not be able to run 'delta' from any directory.{Colors.ENDC}")
        if platform.system() == "Windows":
            print(f"    Rest assured, the installer attempted to add it. You MUST restart your terminal.")
        else:
            print(f"    Please add it to your shell configuration (e.g. ~/.bashrc or ~/.zshrc).")

def setup_launchers():
    print(f"{Colors.BLUE}[*] Setting up launchers and integrations...{Colors.ENDC}")
    project_root = Path.cwd().resolve()
    assets_dir = project_root / "assets"
    
    if platform.system() == "Windows":
        # 1. Create delta.bat
        batch_content = f"""@echo off
setlocal
cd /d "{project_root}"
call venv\\Scripts\\activate.bat
python main.py %*
endlocal
"""
        with open("delta.bat", "w") as f:
            f.write(batch_content)
        print(f"{Colors.GREEN}[+] Created 'delta.bat'.{Colors.ENDC}")
        
        # 2. Create delta-web.vbs (Hidden Web UI)
        vbs_web = f"""
Set WshShell = CreateObject("WScript.Shell") 
WshShell.Run chr(34) & "{project_root}\\delta.bat" & chr(34) & " --web", 0
Set WshShell = Nothing 
"""
        with open("delta-web.vbs", "w") as f:
            f.write(vbs_web)
        print(f"{Colors.GREEN}[+] Created 'delta-web.vbs' (Hidden Web UI).{Colors.ENDC}")

        # 3. Create delta-daemon.vbs (Hidden Daemon)
        vbs_daemon = f"""
Set WshShell = CreateObject("WScript.Shell") 
WshShell.Run chr(34) & "{project_root}\\delta.bat" & chr(34) & " --daemon", 0
Set WshShell = Nothing 
"""
        with open("delta-daemon.vbs", "w") as f:
            f.write(vbs_daemon)
        print(f"{Colors.GREEN}[+] Created 'delta-daemon.vbs' (Hidden Daemon).{Colors.ENDC}")

        # 4. Add to PATH
        add_to_path_windows(project_root)
        check_path_visibility(project_root)
        
        # 5. Setup Shortcuts with Icons
        icon_path = assets_dir / "delta.ico"
        icon_arg = str(icon_path) if icon_path.exists() else ""
        
        # Robust Desktop & Startup Detection
        if platform.system() == "Windows":
            try:
                import winreg
                shell_folders_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
                desktop_path_str, _ = winreg.QueryValueEx(shell_folders_key, "Desktop")
                startup_path_str, _ = winreg.QueryValueEx(shell_folders_key, "Startup")
                
                # Expand environment variables like %USERPROFILE%
                desktop_dir = Path(os.path.expandvars(desktop_path_str))
                startup_dir = Path(os.path.expandvars(startup_path_str))
            except Exception:
                # Fallback
                desktop_dir = Path(os.path.expandvars(r"%USERPROFILE%\Desktop"))
                startup_dir = Path(os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"))

        if startup_dir.exists():
            shortcut_path = startup_dir / "Delta Agent.lnk"
            target = Path(os.path.expandvars(r"%SystemRoot%\System32\wscript.exe"))
            arguments = f'"{project_root}\\delta-web.vbs"'
            try:
                create_windows_shortcut(str(target), str(shortcut_path), arguments=arguments, icon=icon_arg)
                print(f"{Colors.GREEN}[+] Created Hidden Startup shortcut with icon.{Colors.ENDC}")
            except Exception as e:
                print(f"{Colors.RED}[!] Failed to create startup shortcut: {e}{Colors.ENDC}")
            
            # Desktop Shortcut
            if desktop_dir.exists():
                desktop_shortcut = desktop_dir / "Delta Agent.lnk"
                try:
                    create_windows_shortcut(str(target), str(desktop_shortcut), arguments=arguments, icon=icon_arg)
                    print(f"{Colors.GREEN}[+] Created Desktop shortcut with icon.{Colors.ENDC}")
                except Exception as e:
                    print(f"{Colors.RED}[!] Failed to create desktop shortcut: {e}{Colors.ENDC}")
        
    else:
        # Linux/Mac logic
        shell_content = f"""#!/bin/bash
cd "{project_root}"
source venv/bin/activate
python3 main.py "$@"
"""
        with open("delta", "w") as f:
            f.write(shell_content)
        os.chmod("delta", 0o755)
        print(f"{Colors.GREEN}[+] Created 'delta' launcher.{Colors.ENDC}")
        
        # macOS .command launcher (Double-click support)
        if platform.system() == "Darwin":
            command_content = f"""#!/bin/bash
cd "{project_root}"
source venv/bin/activate
python3 main.py --web
"""
            command_file = project_root / "Delta Web UI.command"
            with open(command_file, "w") as f:
                f.write(command_content)
            os.chmod(command_file, 0o755)
            print(f"{Colors.GREEN}[+] Created 'Delta Web UI.command' for macOS.{Colors.ENDC}")

        # Symlink
        local_bin = Path.home() / ".local" / "bin"
        local_bin.mkdir(parents=True, exist_ok=True)
        target_link = local_bin / "delta"
        
        try:
            if target_link.exists() or target_link.is_symlink():
                target_link.unlink()
            target_link.symlink_to(project_root / "delta")
            print(f"{Colors.GREEN}[+] Symlinked 'delta' to {local_bin}.{Colors.ENDC}")
            check_path_visibility(local_bin)
        except Exception as e:
            print(f"{Colors.YELLOW}[!] Could not symlink: {e}{Colors.ENDC}")

        # Linux .desktop with Icon
        if platform.system() == "Linux":
            icon_path = assets_dir / "delta.png"
            desktop_dir = Path.home() / ".local" / "share" / "applications"
            desktop_dir.mkdir(parents=True, exist_ok=True)
            desktop_file = desktop_dir / "delta.desktop"
            
            icon_setting = f"Icon={icon_path}" if icon_path.exists() else "Icon=utilities-terminal"
            
            content = f"""[Desktop Entry]
Name=Delta Agent
Comment=AI Agent Web Interface
Exec={target_link} --web
{icon_setting}
Terminal=false
Type=Application
Categories=Utility;AI;
"""
            with open(desktop_file, "w") as f:
                f.write(content)
            print(f"{Colors.GREEN}[+] Created Linux desktop entry with icon.{Colors.ENDC}")


def main():
    print_banner()
    check_python()
    create_venv()
    install_dependencies()
    setup_launchers()
    
    print(f"\n{Colors.CYAN}========================================{Colors.ENDC}")
    print(f"{Colors.CYAN}      INSTALLATION COMPLETE! 🚀{Colors.ENDC}")
    print(f"{Colors.CYAN}========================================{Colors.ENDC}")
    
    python_exec = get_venv_python()
    setup_script = Path("src/cli/setup.py")
    
    if setup_script.exists():
        print("Launching setup wizard...")
        try:
            subprocess.check_call([str(python_exec), str(setup_script)])
        except KeyboardInterrupt:
            print("\nSetup cancelled.")
    
    print(f"\n{Colors.GREEN}You can now use 'delta' (or './delta.bat') to run the agent.{Colors.ENDC}")

if __name__ == "__main__":
    main()
