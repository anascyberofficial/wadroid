import os
from pathlib import Path

ROOT = Path(__file__).parent
OUTPUT_DIR = ROOT / "output"
SESSION_DIR = ROOT / "sessions"
STATIC_DIR = ROOT / "static"
TEMPLATE_DIR = ROOT / "templates"

for _d in [OUTPUT_DIR, SESSION_DIR, STATIC_DIR, TEMPLATE_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

WHATSAPP_URL = "https://web.whatsapp.com"

# Timing
QR_REFRESH_SEC = 3
SCRAPE_CYCLE_SEC = 25
LOGIN_WAIT_SEC = 180

# Server
LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 8585
FLASK_SECRET = os.urandom(16).hex()

# Tunnels
NGROK_AUTH_TOKEN = ""          # set via --ngrok-token
PREFERRED_TUNNEL = "serveo"    # serveo | localhostrun | ngrok | cloudflare

# Chrome paths (auto-detected, override here if needed)
TERMUX_CHROME = "/data/data/com.termux/files/usr/bin/chromium-browser"
LINUX_CHROME = "/usr/bin/google-chrome-stable"

# Scrape depth
MAX_CHATS_INITIAL = 25        # how many contacts to scrape on first pass
MAX_CHATS_LIVE = 12           # how many to cycle through on live passes
SCROLL_LOADS = 6              # how many scroll-ups per chat for history