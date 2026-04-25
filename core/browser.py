import time
import json
import shutil
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class WhatsEngine:
    """Headless Chrome controller for WhatsApp Web."""

    QR_SELECTORS = [
        "canvas[aria-label='Scan this QR code to link a device!']",
        "canvas[aria-label='Scan me!']",
        "div[data-testid='qrcode'] canvas",
        "div._akau canvas",
    ]

    LOGGED_IN_SELECTORS = [
        "#pane-side",
        "div[data-testid='chat-list']",
        "div[data-testid='default-user']",
    ]

    def __init__(self, profile_path: str, headless: bool = True):
        self.profile_path = Path(profile_path)
        self.profile_path.mkdir(parents=True, exist_ok=True)
        self.headless = headless
        self.driver = None
        self.authenticated = False

    # ── platform detection ─────────────────────────────────
    @staticmethod
    def _on_termux() -> bool:
        return Path("/data/data/com.termux/files/usr").exists()

    def _chrome_binary(self) -> str | None:
        if self._on_termux():
            p = Path("/data/data/com.termux/files/usr/bin/chromium-browser")
            return str(p) if p.exists() else None
        for candidate in [
            "/usr/bin/google-chrome-stable",
            "/usr/bin/google-chrome",
            "/usr/bin/chromium-browser",
            "/usr/bin/chromium",
            "/snap/bin/chromium",
        ]:
            if Path(candidate).exists():
                return candidate
        return None

    # ── option builder ─────────────────────────────────────
    def _build_opts(self) -> Options:
        opts = Options()
        chrome_bin = self._chrome_binary()
        if chrome_bin:
            opts.binary_location = chrome_bin

        if self.headless:
            opts.add_argument("--headless=new")

        flags = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-extensions",
            "--disable-infobars",
            "--window-size=1366,900",
            f"--user-data-dir={self.profile_path}",
            "--disable-blink-features=AutomationControlled",
            "--lang=en-US",
        ]
        for f in flags:
            opts.add_argument(f)

        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        return opts

    # ── lifecycle ──────────────────────────────────────────
    def ignite(self):
        opts = self._build_opts()
        self.driver = webdriver.Chrome(options=opts)

        # stealth patches
        self.driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": """
                Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
                window.chrome = {runtime: {}};
            """},
        )
        self.driver.get("https://web.whatsapp.com")
        time.sleep(4)
        return self.driver

    def kill(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    # ── QR capture ─────────────────────────────────────────
    def grab_qr_png(self, dest_path: str) -> bool:
        for sel in self.QR_SELECTORS:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, sel)
                raw = el.screenshot_as_png
                if raw and len(raw) > 500:
                    Path(dest_path).write_bytes(raw)
                    return True
            except Exception:
                continue
        # fallback: full-page crop is unreliable, skip
        return False

    # ── login check ────────────────────────────────────────
    def check_logged_in(self) -> bool:
        for sel in self.LOGGED_IN_SELECTORS:
            try:
                self.driver.find_element(By.CSS_SELECTOR, sel)
                self.authenticated = True
                return True
            except Exception:
                continue
        return False

    def wait_login(self, timeout: int = 180) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.check_logged_in():
                return True
            time.sleep(2)
        return False

    # ── session persistence ────────────────────────────────
    def dump_session_meta(self):
        meta_path = self.profile_path / "wa_session.json"
        try:
            cookies = self.driver.get_cookies()
            ls = self.driver.execute_script(
                "try{return JSON.stringify(localStorage)}catch(e){return '{}'}"
            )
            blob = {
                "cookies": cookies,
                "localStorage": ls,
                "ts": time.time(),
            }
            meta_path.write_text(json.dumps(blob, indent=2))
        except Exception:
            pass

    def session_exists(self) -> bool:
        return (self.profile_path / "Default").exists() or (
            self.profile_path / "wa_session.json"
        ).exists()

    # ── profile info ───────────────────────────────────────
    def get_profile_name(self) -> str:
        try:
            el = self.driver.find_element(
                By.CSS_SELECTOR, "div[data-testid='default-user'] span[dir='auto']"
            )
            return el.text.strip()
        except Exception:
            return ""