#!/usr/bin/env python3
"""
Claude Token Monitor — 基于 Claude.ai 会话的 Token 用量监控
"""
import tkinter as tk
import threading
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
PROXY            = "http://127.0.0.1:7890"  # 不使用代理则设为 None
# ============================================================

BG       = "#000000"
FG_WHITE = "#FFFFFF"
FG_GRAY  = "#888888"
BAR_FG   = "#DDDDDD"
BAR_BG   = "#2A2A2A"
FONT     = "Microsoft YaHei"


def color_for(pct: float) -> str:
    """剩余百分比 → 字色"""
    if pct >= 50:
        return FG_WHITE
    elif pct >= 20:
        return "#FFA040"
    else:
        return "#FF4444"


def parse_reset(iso_str: str) -> str:
    """ISO 时间 → 中文友好显示"""
    if not iso_str:
        return "—"
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
    """重置时间是否已到"""
    if not iso_str:
        return False
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return datetime.now(timezone.utc) >= dt
    except Exception:
        return False


def fetch_data() -> dict:
    """请求 Claude.ai usage 接口，返回剩余百分比"""
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
            return {"error": "Session 已过期，请更新 SESSION_KEY"}
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


# ─── 视图组件 ──────────────────────────────────────────────
class ProgressBar:
    H = 20

    def __init__(self, parent: tk.Widget, width: int):
        self.width = width
        self.canvas = tk.Canvas(parent, width=width, height=self.H,
                                 bg=BG, highlightthickness=0)

    def pack(self, **kw):
        self.canvas.pack(**kw)

    def draw(self, pct: float):
        self.canvas.delete("all")
        self.canvas.create_rectangle(0, 0, self.width, self.H,
                                      fill=BAR_BG, outline="")
        if pct > 0:
            fw = max(1, int(self.width * pct / 100))
            self.canvas.create_rectangle(0, 0, fw, self.H,
                                          fill=BAR_FG, outline="")


class Section:
    def __init__(self, parent: tk.Widget, title: str, bar_width: int):
        self.frame = tk.Frame(parent, bg=BG)
        self._reset_iso = ""

        tk.Label(self.frame, text=title, bg=BG, fg=FG_WHITE,
                 font=(FONT, 13, "bold")).pack(anchor="w")

        self.bar = ProgressBar(self.frame, bar_width)
        self.bar.pack(fill="x", pady=(6, 4))

        row = tk.Frame(self.frame, bg=BG)
        row.pack(fill="x")

        self.lbl_reset = tk.Label(row, text="重置时间: —", bg=BG, fg=FG_GRAY,
                                   font=(FONT, 10))
        self.lbl_reset.pack(side="left")

        frm_num = tk.Frame(row, bg=BG)
        frm_num.pack(side="right")

        self.lbl_val = tk.Label(frm_num, text="—", bg=BG, fg=FG_WHITE,
                                 font=(FONT, 26, "bold"))
        self.lbl_val.pack(side="left", anchor="s")

        self.lbl_unit = tk.Label(frm_num, text="%", bg=BG, fg=FG_WHITE,
                                  font=(FONT, 14))
        self.lbl_unit.pack(side="left", anchor="s", pady=(0, 3))

    def update(self, remaining_pct: float, reset_iso: str):
        self._reset_iso = reset_iso
        self.bar.draw(remaining_pct)
        self.lbl_val.config(text=f"{int(round(remaining_pct))}",
                             fg=color_for(remaining_pct))
        self.refresh_reset_label()

    def refresh_reset_label(self):
        self.lbl_reset.config(text=f"重置时间: {parse_reset(self._reset_iso)}")

    def is_expired(self) -> bool:
        return bool(self._reset_iso) and reset_passed(self._reset_iso)

    def pack(self, **kw):
        self.frame.pack(**kw)

    def pack_forget(self):
        self.frame.pack_forget()


# ─── 主应用 ───────────────────────────────────────────────
class App:
    PAD = 40
    W   = 600
    H   = 330

    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Claude Token Monitor")
        root.configure(bg=BG)
        root.resizable(False, False)
        root.geometry(f"{self.W}x{self.H}")

        self._countdown      = REFRESH_INTERVAL
        self._refreshing     = False
        self._weekly_visible = False

        self._build()
        self._refresh()
        self._tick()

    def _build(self):
        bar_w = self.W - self.PAD * 2
        outer = tk.Frame(self.root, bg=BG)
        outer.pack(fill="both", expand=True, padx=self.PAD, pady=(self.PAD, 0))

        self.sec_hourly = Section(outer, "时余量", bar_w)
        self.sec_hourly.pack(fill="x")

        self.spacer = tk.Frame(outer, bg=BG, height=18)
        self.spacer.pack()

        self.sec_weekly = Section(outer, "周余量", bar_w)
        self.sec_weekly.pack_forget()

        self.lbl_status = tk.Label(self.root, text="正在获取数据…", bg=BG, fg=FG_GRAY,
                                    font=(FONT, 8))
        self.lbl_status.pack(side="bottom", pady=(0, 10))

    def _on_data(self, data: dict):
        self._refreshing = False

        if data.get("error"):
            self.lbl_status.config(text=f"错误：{data['error']}", fg="#FF6666")
            return

        self.lbl_status.config(
            text=f"更新于 {datetime.now().strftime('%H:%M:%S')}",
            fg=FG_GRAY,
        )

        h = data.get("hourly")
        if h:
            self.sec_hourly.update(h["remaining_pct"], h["reset_iso"])

        w = data.get("weekly")
        if w:
            if not self._weekly_visible:
                self.spacer.pack()
                self.sec_weekly.pack(fill="x")
                self._weekly_visible = True
            self.sec_weekly.update(w["remaining_pct"], w["reset_iso"])
        else:
            if self._weekly_visible:
                self.spacer.pack_forget()
                self.sec_weekly.pack_forget()
                self._weekly_visible = False

    def _refresh(self):
        if self._refreshing:
            return
        self._refreshing = True
        self._countdown = REFRESH_INTERVAL

        def worker():
            result = fetch_data()
            self.root.after(0, lambda: self._on_data(result))

        threading.Thread(target=worker, daemon=True).start()

    def _tick(self):
        # 每秒刷新重置时间倒计时显示
        self.sec_hourly.refresh_reset_label()
        if self._weekly_visible:
            self.sec_weekly.refresh_reset_label()

        # 重置时间已到 → 立即拉取新数据
        expired = self.sec_hourly.is_expired() or (
            self._weekly_visible and self.sec_weekly.is_expired()
        )

        if expired:
            self._refresh()
        else:
            self._countdown -= 1
            if self._countdown <= 0:
                self._refresh()

        self.root.after(1000, self._tick)


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
