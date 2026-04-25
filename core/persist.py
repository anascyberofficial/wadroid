import json
import shutil
from pathlib import Path
from datetime import datetime


class SessionKeeper:
    """Saves and restores attack state for the --resume feature."""

    def __init__(self, sess_dir: str):
        self.base = Path(sess_dir)
        self.base.mkdir(parents=True, exist_ok=True)
        self._meta = self.base / "state.json"

    def snapshot(self, blob: dict):
        blob["saved_at"] = datetime.now().isoformat()
        self._meta.write_text(json.dumps(blob, indent=2))

    def restore(self) -> dict | None:
        if self._meta.exists():
            try:
                return json.loads(self._meta.read_text())
            except Exception:
                return None
        return None

    def profile_exists(self) -> bool:
        return (self.base / "chrome_profile" / "Default").exists()

    def wipe(self):
        if self.base.exists():
            shutil.rmtree(self.base, ignore_errors=True)
        self.base.mkdir(parents=True, exist_ok=True)