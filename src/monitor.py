#!/usr/bin/env python3
"""
Claude Token Monitor
监控 Claude API 账号的 Token 剩余量
"""
import tkinter as tk
import httpx
import threading
from datetime import datetime, timezone

# ============================================================
#  配置区 — 填入你的 API Key
# ============================================================
API_KEY          = "sk-ant-XXXXXXXXXXXXXXXX"   # ← 填入你的 Anthropic API Key
REFRESH_INTERVAL = 300                          # 自动刷新间隔（秒），默认 5 分钟
# ============================================================

BG       = "#000000"
FG_WHITE = "#FFFFFF"
FG_GRAY  = "#888888"
BAR_FG   = "#DDDDDD"
BAR_BG   = "#2A2A2A"
FONT     = "Microsoft YaHei"


def token_color(remaining: int, total: int) -> str:
    """根据剩余百分比返回数字颜色"""
    if total <= 0:
        return FG_WHITE
    pct = remaining / total * 100
    if pct >= 50:
        return FG_WHITE    # 充足
    elif pct >= 20:
        return "#FFA040"   # 警告（橙）
    else:
        return "#FF4444"   # 危险（红）


def parse_reset(iso_str: str) -> str:
    """ISO 时间字符串 → 中文友好显示"""
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
    """向 Anthropic API 发送最小请求，从响应头读取 rate limit 数据"""
    try:
        with httpx.Client(timeout=15) as c:
            resp = c.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "1"}],
                },
            )

        h = resp.headers

        def get_int(key: str) -> int:
            v = h.get(key, "").strip()
            return int(v) if v.isdigit() else 0

        # 收集所有可用的 token rate limit 窗口
        windows = []
        for prefix in (
            "anthropic-ratelimit-tokens",
            "anthropic-ratelimit-input-tokens",
            "anthropic-ratelimit-output-tokens",
        ):
            limit     = get_int(f"{prefix}-limit")
            remaining = get_int(f"{prefix}-remaining")
            reset_raw = h.get(f"{prefix}-reset", "")
            if limit > 0:
                windows.append({
                    "limit":     limit,
                    "remaining": remaining,
                    "reset_str": parse_reset(reset_raw),
                })

        if not windows:
            return {"error": "未获取到 rate limit 信息，请检查 API Key 是否正确"}

        # 按 limit 升序：最小窗口 = 时余量，最大窗口 = 周余量
        windows.sort(key=lambda x: x["limit"])
        hourly = windows[0]
        weekly = windows[-1] if len(windows) > 1 else None

        return {"hourly": hourly, "weekly": weekly, "error": None}

    except Exception as e:
        return {"error": str(e)}


class ProgressBar:
    """用 Canvas 绘制的平面进度条"""
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
        # 背景轨道
        self.canvas.create_rectangle(0, 0, self.width, self.H,
                                      fill=BAR_BG, outline="")
        # 剩余填充
        if total > 0 and remaining > 0:
            fw = max(1, int(self.width * remaining / total))
            self.canvas.create_rectangle(0, 0, fw, self.H,
                                          fill=BAR_FG, outline="")


class Section:
    """一个展示区块（时余量 / 周余量）"""
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
        self.lbl_val.config(
            text=f"{remaining:,}",
            fg=token_color(remaining, total)
        )
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
        self._refresh()   # 启动时立即获取数据
        self._tick()      # 启动倒计时

    def _build(self):
        bar_w = self.W - self.PAD * 2
        outer = tk.Frame(self.root, bg=BG)
        outer.pack(fill="both", expand=True, padx=self.PAD, pady=(self.PAD, 0))

        self.sec_hourly = Section(outer, "时余量", bar_w)
        self.sec_hourly.pack(fill="x")

        self.spacer = tk.Frame(outer, bg=BG, height=18)
        self.spacer.pack()

        self.sec_weekly = Section(outer, "周余量", bar_w)
        # 初始隐藏，有数据时再显示
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

        now_str = datetime.now().strftime("%H:%M:%S")
        self.lbl_status.config(text=f"更新于 {now_str}", fg=FG_GRAY)

        h = data["hourly"]
        self.sec_hourly.update(h["remaining"], h["limit"], h["reset_str"])

        w = data.get("weekly")
        if w:
            self.sec_weekly.pack(fill="x")
            self.spacer.pack()
            self.sec_weekly.update(w["remaining"], w["limit"], w["reset_str"])
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
