import re
import time
import subprocess
import requests


class TunnelBridge:
    """Manages public tunnel to expose the local Flask server."""

    def __init__(self):
        self.url: str | None = None
        self.proc: subprocess.Popen | None = None
        self.kind: str = ""

    # ── serveo (free) ──────────────────────────────────────
    def open_serveo(self, port: int) -> str | None:
        try:
            self.proc = subprocess.Popen(
                ["ssh", "-o", "StrictHostKeyChecking=no",
                 "-o", "ServerAliveInterval=60",
                 "-R", f"80:localhost:{port}", "serveo.net"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            deadline = time.time() + 20
            while time.time() < deadline:
                line = self.proc.stdout.readline()
                m = re.search(r"(https?://[a-z0-9]+\.serveo\.net)", line)
                if m:
                    self.url = m.group(1)
                    self.kind = "serveo"
                    return self.url
        except FileNotFoundError:
            pass
        return None

    # ── localhost.run (free) ───────────────────────────────
    def open_lhr(self, port: int) -> str | None:
        try:
            self.proc = subprocess.Popen(
                ["ssh", "-o", "StrictHostKeyChecking=no",
                 "-R", f"80:localhost:{port}",
                 "nokey@localhost.run"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            deadline = time.time() + 20
            while time.time() < deadline:
                line = self.proc.stdout.readline()
                for pat in [
                    r"(https://[a-z0-9]+\.lhr\.life)",
                    r"(https://[^\s]+\.localhost\.run)",
                ]:
                    m = re.search(pat, line)
                    if m:
                        self.url = m.group(1)
                        self.kind = "lhr"
                        return self.url
        except FileNotFoundError:
            pass
        return None

    # ── ngrok (paid) ───────────────────────────────────────
    def open_ngrok(self, port: int, token: str = "") -> str | None:
        try:
            if token:
                subprocess.run(
                    ["ngrok", "config", "add-authtoken", token],
                    capture_output=True, timeout=15,
                )

            self.proc = subprocess.Popen(
                ["ngrok", "http", str(port), "--log=stdout"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            time.sleep(4)

            # API probe first
            try:
                r = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=5)
                for t in r.json().get("tunnels", []):
                    u = t.get("public_url", "")
                    if u.startswith("https"):
                        self.url = u
                        self.kind = "ngrok"
                        return self.url
                if r.json().get("tunnels"):
                    self.url = r.json()["tunnels"][0]["public_url"]
                    self.kind = "ngrok"
                    return self.url
            except Exception:
                pass

            # stdout fallback
            deadline = time.time() + 12
            while time.time() < deadline:
                line = self.proc.stdout.readline()
                m = re.search(r"url=(https?://[^\s]+\.ngrok[^\s]*)", line)
                if m:
                    self.url = m.group(1)
                    self.kind = "ngrok"
                    return self.url
        except FileNotFoundError:
            pass
        return None

    # ── cloudflared (paid/free quick tunnel) ───────────────
    def open_cloudflare(self, port: int) -> str | None:
        try:
            self.proc = subprocess.Popen(
                ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            deadline = time.time() + 25
            while time.time() < deadline:
                line = self.proc.stdout.readline()
                m = re.search(r"(https://[^\s]+\.trycloudflare\.com)", line)
                if m:
                    self.url = m.group(1)
                    self.kind = "cloudflare"
                    return self.url
        except FileNotFoundError:
            pass
        return None

    # ── teardown ───────────────────────────────────────────
    def close(self):
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=5)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
        self.url = None
        self.kind = ""