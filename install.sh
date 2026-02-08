#!/bin/bash

# Delta Agent - Magic Installer
# Installs dependencies, sets up environment, and launches the agent.

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${CYAN}"
cat << "EOF"
  _____       _ _        
 |  __ \     | | |       
 | |  | | ___| | |_ __ _ 
 | |  | |/ _ \ | __/ _` |
 | |__| |  __/ | || (_| |
 |_____/ \___|_|\__\__,_|
                         
   AI AGENT INSTALLER
EOF
echo -e "${NC}"

echo -e "${BLUE}[*] Checking system requirements...${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[!] Python 3 is not installed.${NC}"
    exit 1
fi

# Check Git
if ! command -v git &> /dev/null; then
    echo -e "${RED}[!] Git is not installed.${NC}"
    exit 1
fi

echo -e "${GREEN}[+] System checks passed.${NC}"

# Create Virtual Environment
if [ ! -d "venv" ]; then
    echo -e "${BLUE}[*] Creating virtual environment...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}[+] Virtual environment created.${NC}"
else
    echo -e "${YELLOW}[-] Virtual environment already exists. Skipping.${NC}"
fi

# Activate & Install
echo -e "${BLUE}[*] Installing dependencies...${NC}"
source venv/bin/activate
pip install --upgrade pip > /dev/null
pip install -r requirements.txt

# Install Playwright browsers (if needed for web browsing, user didn't ask but good for future)
# playwright install chromium 

echo -e "${GREEN}[+] Dependencies installed.${NC}"

# Setup Desktop Shortcut
echo -e "${BLUE}[*] Setting up desktop shortcut...${NC}"
PWD=$(pwd)
mkdir -p install
cat << EOF > install/delta.desktop
[Desktop Entry]
Name=Delta Agent
Comment=AI Agent Web Interface
Exec=bash -c "cd $PWD && ./venv/bin/python3 main.py --web"
Icon=utilities-terminal
Terminal=false
Type=Application
Categories=Utility;AI;
EOF

mkdir -p ~/.local/share/applications
cp install/delta.desktop ~/.local/share/applications/delta.desktop
echo -e "${GREEN}[+] Desktop shortcut created.${NC}"

# Launch Onboarding
echo -e "${CYAN}"
echo "========================================"
echo "      INSTALLATION COMPLETE! 🚀"
echo "========================================"
echo -e "${NC}"
echo "We will now launch the setup wizard to configure your agent."
echo "Press ENTER to continue..."
read

# Run Setup Wizard (we'll implement this next)
python3 src/cli/setup.py

echo -e "${GREEN}Done! You can now run Delta via the desktop icon or ./start.sh${NC}"
