#!/usr/bin/env python3
"""
Claude Token Monitor — 低代码极简版
"""
import time
import tkinter as tk
import threading
import traceback
from datetime import datetime, timezone
from curl_cffi import requests

# ============================================================
#  配置区
# ============================================================
ORG_ID      = "c9c7cc79-dd59-458f-81c0-69e002b478b2"
SESSION_KEY = "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"
DEVICE_ID   = "cede9a57-c43e-4275-a7b4-c2fe1bf1e8d4"
ANON_ID     = "claudeai.v1.c05d1e10-fed3-4ef4-ac36-130c29ae4124"

REFRESH_INTERVAL = 20                       # 自动刷新间隔（秒）
MIN_REFRESH_GAP  = 10                       # 两次刷新之间最小间隔（秒），防忙轮询
BACKOFF_STEPS    = [5, 10, 30, 60, 120]     # 失败指数退避（秒）
PROXY            = "http://127.0.0.1:7890"  # 不使用代理则设为 None
# ============================================================

BG    = "#000000"
FG    = "#AAAAAA"
DIM   = "#777777"
FONT  = "Microsoft YaHei"
FSIZE = 9
ALPHA = 0.85


def color_for(pct: float) -> str:
    if pct >= 50:
        return FG
    elif pct >= 20:
        return "#AA8844"
    return "#AA4444"


def parse_reset(iso_str: str) -> str:
    if not iso_str:
        return "--"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        secs = max(0, int((dt - now).total_seconds()))
        if secs == 0:
            return "已重置"
        mins = secs // 60
        if mins < 60:
            return f"{mins}分钟"
        hrs = mins // 60
        if hrs < 24:
            return f"{hrs}小时{mins % 60}分钟"
        local_dt = dt.astimezone()
        return f"{local_dt.month}月{local_dt.day}日{local_dt.hour}时"
    except Exception:
        return iso_str


def reset_passed(iso_str: str) -> bool:
    if not iso_str:
        return False
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return datetime.now(timezone.utc) >= dt
    except Exception:
        return False


def fetch_data() -> dict:
    try:
        proxy = {"https": PROXY, "http": PROXY} if PROXY else None
        resp = requests.get(
            f"https://claude.ai/api/organizations/{ORG_ID}/usage",
            headers={
                "anthropic-anonymous-id":    ANON_ID,
                "anthropic-client-platform": "web_claude_ai",
                "anthropic-client-version":  "1.0.0",
                "anthropic-device-id":       DEVICE_ID,
                "content-type":              "application/json",
                "referer":                   "https://claude.ai/settings/usage",
            },
            cookies={
                "sessionKey":          SESSION_KEY,
                "anthropic-device-id": DEVICE_ID,
                "lastActiveOrg":       ORG_ID,
                "ajs_anonymous_id":    ANON_ID,
            },
            impersonate="chrome124",
            proxies=proxy,
            timeout=15,
        )
        if resp.status_code == 403:
            return {"error": "Session 已过期"}
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}"}

        data = resp.json()

        def parse_block(block):
            if not block:
                return None
            util = block.get("utilization") or 0
            return {
                "remaining_pct": max(0.0, 100.0 - util),
                "reset_iso":     block.get("resets_at", ""),
            }

        return {
            "hourly": parse_block(data.get("five_hour")),
            "weekly": parse_block(data.get("seven_day")),
            "error":  None,
        }
    except Exception as e:
        return {"error": str(e)}


class App:
    W = 220
    H = 72

    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Token Monitor")
        root.configure(bg=BG)
        root.resizable(False, False)
        root.geometry(f"{self.W}x{self.H}")
        root.attributes("-topmost", True)
        root.attributes("-alpha", ALPHA)
        root.overrideredirect(True)

        self._topmost = True
        self._countdown = REFRESH_INTERVAL
        self._refreshing = False
        self._hourly_iso = ""
        self._weekly_iso = ""
        self._weekly_pct = None
        self._drag_x = 0
        self._drag_y = 0
        self._fail_count = 0
        self._last_refresh_ts = 0.0

        self._build()
        self._refresh()
        self._tick()

    def _build(self):
        # 顶栏
        top = tk.Frame(self.root, bg="#000000", height=20)
        top.pack(fill="x")
        top.pack_propagate(False)

        top.bind("<Button-1>", self._start_drag)
        top.bind("<B1-Motion>", self._do_drag)

        self.lbl_status = tk.Label(
            top, text="...", bg="#000000", fg=DIM, font=(FONT, FSIZE),
        )
        self.lbl_status.pack(side="left", padx=(6, 0))

        self.btn_pin = tk.Label(
            top, text="◆", bg="#000000", fg=DIM,
            font=(FONT, FSIZE), cursor="hand2",
        )
        self.btn_pin.pack(side="right", padx=(0, 4))
        self.btn_pin.bind("<Button-1>", self._toggle_topmost)

        btn_close = tk.Label(
            top, text="×", bg="#000000", fg=DIM,
            font=(FONT, FSIZE), cursor="hand2",
        )
        btn_close.pack(side="right", padx=(0, 2))
        btn_close.bind("<Button-1>", lambda _: self.root.destroy())

        # 主体
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=8, pady=(2, 6))

        # 时余量
        r1 = tk.Frame(body, bg=BG)
        r1.pack(fill="x", pady=(2, 0))
        tk.Label(r1, text="时", bg=BG, fg=DIM, font=(FONT, FSIZE)).pack(side="left")
        self.lbl_hourly = tk.Label(r1, text="--%", bg=BG, fg=FG, font=(FONT, FSIZE))
        self.lbl_hourly.pack(side="left", padx=(4, 0))
        self.lbl_hourly_reset = tk.Label(r1, text="--", bg=BG, fg=DIM, font=(FONT, FSIZE), anchor="e")
        self.lbl_hourly_reset.pack(side="right")

        # 周余量
        r2 = tk.Frame(body, bg=BG)
        r2.pack(fill="x", pady=(2, 0))
        tk.Label(r2, text="周", bg=BG, fg=DIM, font=(FONT, FSIZE)).pack(side="left")
        self.lbl_weekly = tk.Label(r2, text="--%", bg=BG, fg=FG, font=(FONT, FSIZE))
        self.lbl_weekly.pack(side="left", padx=(4, 0))
        self.lbl_weekly_reset = tk.Label(r2, text="--", bg=BG, fg=DIM, font=(FONT, FSIZE), anchor="e")
        self.lbl_weekly_reset.pack(side="right")

    def _start_drag(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _do_drag(self, event):
        x = self.root.winfo_x() + event.x - self._drag_x
        y = self.root.winfo_y() + event.y - self._drag_y
        self.root.geometry(f"+{x}+{y}")

    def _toggle_topmost(self, _event=None):
        self._topmost = not self._topmost
        self.root.attributes("-topmost", self._topmost)
        self.btn_pin.config(fg=DIM if self._topmost else "#444444")

    def _on_data(self, data: dict):
        try:
            if data.get("error"):
                self._fail_count += 1
                msg = data["error"]
                if len(msg) > 24:
                    msg = msg[:24] + "…"
                self.lbl_status.config(text=msg, fg="#AA4444")
                return

            self._fail_count = 0
            self.lbl_status.config(
                text=datetime.now().strftime("%H:%M:%S"), fg=DIM,
            )
            self._apply_data(data)
        except Exception:
            traceback.print_exc()
        finally:
            self._refreshing = False

    def _apply_data(self, data: dict):
        h = data.get("hourly")
        if h:
            pct = h["remaining_pct"]
            self._hourly_iso = h["reset_iso"]
            self.lbl_hourly.config(text=f"{int(round(pct))}%", fg=color_for(pct))
            self.lbl_hourly_reset.config(text=parse_reset(self._hourly_iso))

        w = data.get("weekly")
        if w:
            pct = w["remaining_pct"]
            self._weekly_pct = pct
            self._weekly_iso = w["reset_iso"]
            self.lbl_weekly.config(text=f"{int(round(pct))}%", fg=color_for(pct))
            self.lbl_weekly_reset.config(text=parse_reset(self._weekly_iso))
        else:
            self._weekly_pct = None
            self.lbl_weekly.config(text="N/A", fg=DIM)
            self.lbl_weekly_reset.config(text="")

    def _refresh(self, force: bool = False):
        if self._refreshing:
            return
        now = time.monotonic()
        if not force and (now - self._last_refresh_ts) < MIN_REFRESH_GAP:
            return
        self._refreshing = True
        self._last_refresh_ts = now
        self._countdown = REFRESH_INTERVAL

        def worker():
            try:
                result = fetch_data()
            except Exception as e:
                result = {"error": f"worker: {e}"}
            try:
                self.root.after(0, lambda: self._on_data(result))
            except Exception:
                # Tk 已销毁等情况，确保状态不卡死
                self._refreshing = False

        threading.Thread(target=worker, daemon=True).start()

    def _current_interval(self) -> int:
        if self._fail_count <= 0:
            return REFRESH_INTERVAL
        idx = min(self._fail_count - 1, len(BACKOFF_STEPS) - 1)
        return BACKOFF_STEPS[idx]

    def _tick(self):
        try:
            self.lbl_hourly_reset.config(text=parse_reset(self._hourly_iso))
            if self._weekly_pct is not None:
                self.lbl_weekly_reset.config(text=parse_reset(self._weekly_iso))

            expired = reset_passed(self._hourly_iso) or (
                self._weekly_pct is not None and reset_passed(self._weekly_iso)
            )
            if expired:
                self._refresh()  # 受 MIN_REFRESH_GAP 保护，不会忙轮询

            self._countdown -= 1
            if self._countdown <= 0:
                self._countdown = self._current_interval()
                self._refresh()
        except Exception:
            traceback.print_exc()
        finally:
            self.root.after(1000, self._tick)


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
