#!/usr/bin/env python3
"""
Claude Token Monitor — 基于 Claude.ai 会话的 Token 用量监控
使用 curl_cffi 模拟浏览器 TLS 指纹，无需手动维护 cf_clearance
"""
import tkinter as tk
import threading
from datetime import datetime, timezone
from curl_cffi import requests

# ============================================================
#  配置区 — 仅需维护 SESSION_KEY（长期有效，一般无需更换）
# ============================================================
ORG_ID      = "c9c7cc79-dd59-458f-81c0-69e002b478b2"
SESSION_KEY = "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"
DEVICE_ID   = "cede9a57-c43e-4275-a7b4-c2fe1bf1e8d4"
ANON_ID     = "claudeai.v1.c05d1e10-fed3-4ef4-ac36-130c29ae4124"

# Claude Max 套餐 Token 上限（如实际上限不同请修改）
FIVE_HOUR_TOTAL = 20_000
SEVEN_DAY_TOTAL = 1_000_000

REFRESH_INTERVAL = 300  # 自动刷新间隔（秒）
# ============================================================

BG       = "#000000"
FG_WHITE = "#FFFFFF"
FG_GRAY  = "#888888"
BAR_FG   = "#DDDDDD"
BAR_BG   = "#2A2A2A"
FONT     = "Microsoft YaHei"


def token_color(remaining: int, total: int) -> str:
    if total <= 0:
        return FG_WHITE
    pct = remaining / total * 100
    if pct >= 50:
        return FG_WHITE
    elif pct >= 20:
        return "#FFA040"
    else:
        return "#FF4444"


def parse_reset(iso_str: str) -> str:
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        secs = max(0, int((dt - now).total_seconds()))
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


def fetch_data() -> dict:
    try:
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
            timeout=15,
        )

        if resp.status_code == 403:
            return {"error": "Session 已过期，请更新 SESSION_KEY"}
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}"}

        data = resp.json()

        def parse_block(block, total):
            if not block:
                return None
            utilization = block.get("utilization") or 0
            remaining = max(0, int(total * (1 - utilization / 100)))
            return {
                "remaining": remaining,
                "total":     total,
                "reset_str": parse_reset(block.get("resets_at", "")),
            }

        hourly = parse_block(data.get("five_hour"), FIVE_HOUR_TOTAL)
        weekly = parse_block(data.get("seven_day"), SEVEN_DAY_TOTAL)

        if not hourly:
            return {"error": "未获取到用量数据"}

        return {"hourly": hourly, "weekly": weekly, "error": None}

    except Exception as e:
        return {"error": str(e)}


class ProgressBar:
    H = 20

    def __init__(self, parent: tk.Widget, width: int):
        self.width = width
        self.canvas = tk.Canvas(
            parent, width=width, height=self.H,
            bg=BG, highlightthickness=0,
        )

    def pack(self, **kw):
        self.canvas.pack(**kw)

    def draw(self, remaining: int, total: int):
        self.canvas.delete("all")
        self.canvas.create_rectangle(0, 0, self.width, self.H, fill=BAR_BG, outline="")
        if total > 0 and remaining > 0:
            fw = max(1, int(self.width * remaining / total))
            self.canvas.create_rectangle(0, 0, fw, self.H, fill=BAR_FG, outline="")


class Section:
    def __init__(self, parent: tk.Widget, title: str, bar_width: int):
        self.frame = tk.Frame(parent, bg=BG)

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

        self.lbl_tot = tk.Label(frm_num, text="/—", bg=BG, fg=FG_WHITE,
                                 font=(FONT, 14))
        self.lbl_tot.pack(side="left", anchor="s", pady=(0, 3))

    def update(self, remaining: int, total: int, reset_str: str):
        self.bar.draw(remaining, total)
        self.lbl_reset.config(text=f"重置时间: {reset_str}")
        self.lbl_val.config(text=f"{remaining:,}", fg=token_color(remaining, total))
        self.lbl_tot.config(text=f"/{total:,}")

    def pack(self, **kw):
        self.frame.pack(**kw)

    def pack_forget(self):
        self.frame.pack_forget()


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

        self._countdown = REFRESH_INTERVAL
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

        self.lbl_status = tk.Label(
            self.root, text="正在获取数据…", bg=BG, fg=FG_GRAY,
            font=(FONT, 8)
        )
        self.lbl_status.pack(side="bottom", pady=(0, 10))

    def _update(self, data: dict):
        if data.get("error"):
            self.lbl_status.config(text=f"错误：{data['error']}", fg="#FF6666")
            return

        self.lbl_status.config(
            text=f"更新于 {datetime.now().strftime('%H:%M:%S')}",
            fg=FG_GRAY
        )

        h = data["hourly"]
        self.sec_hourly.update(h["remaining"], h["total"], h["reset_str"])

        w = data.get("weekly")
        if w:
            self.spacer.pack()
            self.sec_weekly.pack(fill="x")
            self.sec_weekly.update(w["remaining"], w["total"], w["reset_str"])
        else:
            self.spacer.pack_forget()
            self.sec_weekly.pack_forget()

    def _refresh(self):
        self._countdown = REFRESH_INTERVAL

        def worker():
            result = fetch_data()
            self.root.after(0, lambda: self._update(result))

        threading.Thread(target=worker, daemon=True).start()

    def _tick(self):
        self._countdown -= 1
        if self._countdown <= 0:
            self._refresh()
        self.root.after(1000, self._tick)


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
