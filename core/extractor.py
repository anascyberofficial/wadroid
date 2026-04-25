import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


class ChatExtractor:
    """Pulls contacts and messages out of a live WhatsApp Web session."""

    def __init__(self, driver):
        self.drv = driver
        self.known_ids: set[str] = set()
        self.cumulative: dict[str, list[dict]] = {}

    # ── contacts ───────────────────────────────────────────
    def list_contacts(self) -> list[dict]:
        out = []
        try:
            rows = self.drv.find_elements(
                By.CSS_SELECTOR, "div[data-testid='cell-frame-container']"
            )
            for row in rows:
                try:
                    name_el = row.find_element(
                        By.CSS_SELECTOR, "span[dir='auto'][title]"
                    )
                    name = name_el.get_attribute("title") or name_el.text
                    snippet = ""
                    try:
                        snip_el = row.find_element(By.CSS_SELECTOR, "span[dir='ltr']")
                        snippet = snip_el.text
                    except Exception:
                        pass
                    out.append({"name": name, "snippet": snippet})
                except Exception:
                    continue
        except Exception:
            pass
        return out

    # ── open a specific chat ───────────────────────────────
    def tap_chat(self, contact_name: str) -> bool:
        try:
            search_box = self.drv.find_element(
                By.CSS_SELECTOR,
                "div[data-testid='chat-list-search'] div[contenteditable='true']",
            )
            search_box.click()
            time.sleep(0.3)
            # clear
            search_box.send_keys(Keys.CONTROL + "a")
            search_box.send_keys(Keys.DELETE)
            time.sleep(0.2)
            search_box.send_keys(contact_name)
            time.sleep(1.8)

            hits = self.drv.find_elements(
                By.CSS_SELECTOR, "div[data-testid='cell-frame-container']"
            )
            if hits:
                hits[0].click()
                time.sleep(1.2)
                return True
        except Exception:
            pass
        return False

    def dismiss_search(self):
        """Close search overlay / go back."""
        for sel in [
            "button[data-testid='back']",
            "span[data-testid='x-alt']",
            "button[aria-label='Back']",
        ]:
            try:
                self.drv.find_element(By.CSS_SELECTOR, sel).click()
                time.sleep(0.3)
                return
            except Exception:
                continue

    # ── read messages from currently open chat ─────────────
    def read_open_chat(self) -> tuple[str, list[dict]]:
        header = ""
        messages: list[dict] = []

        try:
            hdr = self.drv.find_element(
                By.CSS_SELECTOR,
                "div[data-testid='conversation-header'] span[dir='auto']",
            )
            header = hdr.text.strip()
        except Exception:
            pass

        try:
            containers = self.drv.find_elements(
                By.CSS_SELECTOR, "div[data-testid='msg-container']"
            )
        except Exception:
            return header, messages

        for box in containers:
            try:
                cls = box.get_attribute("class") or ""
                direction = "out" if "message-out" in cls else "in"

                body = ""
                for txt_sel in [
                    "span.selectable-text",
                    "div[data-testid='msg-text']",
                    "span[dir='ltr']",
                ]:
                    try:
                        body = box.find_element(By.CSS_SELECTOR, txt_sel).text
                        if body:
                            break
                    except Exception:
                        continue
                if not body:
                    body = "[media]"

                stamp = ""
                try:
                    stamp = box.find_element(
                        By.CSS_SELECTOR, "div[data-testid='msg-meta'] span"
                    ).text
                except Exception:
                    pass

                uid = f"{header}|{stamp}|{body[:80]}"
                if uid in self.known_ids:
                    continue
                self.known_ids.add(uid)

                messages.append(
                    {
                        "contact": header,
                        "dir": direction,
                        "time": stamp,
                        "text": body,
                    }
                )
            except Exception:
                continue

        return header, messages

    # ── scroll up to load older messages ───────────────────
    def scroll_history(self, rounds: int = 5):
        try:
            pane = self.drv.find_element(
                By.CSS_SELECTOR,
                "div[data-testid='conversation-panel-messages']",
            )
            for _ in range(rounds):
                self.drv.execute_script("arguments[0].scrollTop=0;", pane)
                time.sleep(0.6)
        except Exception:
            pass

    # ── high-level: full scrape of N chats ─────────────────
    def harvest_all(self, limit: int = 25, scroll: int = 6) -> dict[str, list[dict]]:
        contacts = self.list_contacts()
        bucket: dict[str, list[dict]] = {}

        for entry in contacts[:limit]:
            cname = entry["name"]
            if self.tap_chat(cname):
                self.scroll_history(scroll)
                time.sleep(0.4)
                hdr, msgs = self.read_open_chat()
                tag = hdr or cname
                if msgs:
                    bucket[tag] = msgs
                    self.cumulative.setdefault(tag, []).extend(msgs)
                self.dismiss_search()
                time.sleep(0.3)

        return bucket

    # ── quick live pass (fewer chats, no deep scroll) ──────
    def live_pass(self, limit: int = 12) -> dict[str, list[dict]]:
        contacts = self.list_contacts()
        fresh: dict[str, list[dict]] = {}

        for entry in contacts[:limit]:
            cname = entry["name"]
            if self.tap_chat(cname):
                time.sleep(0.5)
                hdr, msgs = self.read_open_chat()
                tag = hdr or cname
                if msgs:
                    fresh[tag] = msgs
                    self.cumulative.setdefault(tag, []).extend(msgs)
                self.dismiss_search()
                time.sleep(0.2)

        return fresh