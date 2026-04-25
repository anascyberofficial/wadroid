import json
import threading
from pathlib import Path
from datetime import datetime


class DataWriter:
    """Thread-safe file writer for all extracted data."""

    def __init__(self, out_dir: str):
        self.root = Path(out_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

        self.f_chats = self.root / "chats.txt"
        self.f_live = self.root / "live_feed.txt"
        self.f_contacts = self.root / "contacts.txt"
        self.f_target = self.root / "target_info.txt"
        self.f_json = self.root / "dump.json"

    # ── chats ──────────────────────────────────────────────
    def save_chats(self, chat_map: dict[str, list[dict]], tag: str = "initial"):
        with self._lock:
            dest = self.f_chats if tag == "initial" else self.f_live
            with open(dest, "a", encoding="utf-8") as fh:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                fh.write(f"\n{'#'*55}\n")
                fh.write(f"# [{tag.upper()}] {now}\n")
                fh.write(f"{'#'*55}\n")

                for contact, msgs in chat_map.items():
                    fh.write(f"\n┌── {contact} ──┐\n")
                    for m in msgs:
                        arrow = ">>>" if m.get("dir") == "out" else "<<<"
                        ts = m.get("time", "??")
                        txt = m.get("text", "")
                        fh.write(f"│ {arrow} [{ts}] {txt}\n")
                    fh.write(f"└── /{contact} ──┘\n")

    # ── single live message append ─────────────────────────
    def append_msg(self, contact: str, text: str, direction: str, stamp: str):
        with self._lock:
            with open(self.f_live, "a", encoding="utf-8") as fh:
                a = ">>>" if direction == "out" else "<<<"
                t = datetime.now().strftime("%H:%M:%S")
                fh.write(f"[{t}] {contact} {a} [{stamp}] {text}\n")

    # ── contacts list ──────────────────────────────────────
    def save_contacts(self, contacts: list[dict]):
        with self._lock:
            with open(self.f_contacts, "w", encoding="utf-8") as fh:
                fh.write(f"Contact List — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                fh.write(f"{'─'*40}\n")
                for i, c in enumerate(contacts, 1):
                    line = f"{i:>3}. {c['name']}"
                    if c.get("snippet"):
                        line += f"  ▸ {c['snippet'][:55]}"
                    fh.write(line + "\n")

    # ── target info ────────────────────────────────────────
    def save_target(self, info: dict):
        with self._lock:
            with open(self.f_target, "a", encoding="utf-8") as fh:
                fh.write(f"\n{'─'*40}\n")
                fh.write(f"Target @ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                for k, v in info.items():
                    fh.write(f"  {k}: {v}\n")

    # ── raw JSON dump ──────────────────────────────────────
    def dump_raw(self, data: dict):
        with self._lock:
            old = {}
            if self.f_json.exists():
                try:
                    old = json.loads(self.f_json.read_text())
                except Exception:
                    pass
            old[datetime.now().isoformat()] = data
            self.f_json.write_text(json.dumps(old, indent=2, ensure_ascii=False))