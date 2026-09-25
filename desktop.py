# -*- coding: utf-8 -*-
"""
电脑休眠推迟工具 · 桌面窗口版
双击 exe 弹出独立小窗口，在指定时长内阻止电脑进入休眠，可自定义分钟数。
基于 Windows SetThreadExecutionState 系统 API + tkinter，无需浏览器。
"""
import ctypes
import time
import threading
import datetime
import tkinter as tk
from tkinter import ttk

ES_CONTINUOUS        = 0x80000000
ES_SYSTEM_REQUIRED   = 0x00000001
ES_DISPLAY_REQUIRED  = 0x00000002

STATE_DISPLAY_OFF = ES_SYSTEM_REQUIRED
STATE_DISPLAY_ON  = ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED

MAX_MINUTES = 1440


class Engine:
    """管理推迟会话：状态、倒计时、系统唤醒续期。"""
    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.mode = 0
        self.total_max = 60
        self.end_time = None
        self.stop_event = threading.Event()

    def start(self, minutes, mode):
        self.stop_event.set()
        self.stop_event = threading.Event()
        with self.lock:
            self.running = True
            self.mode = mode
            self.end_time = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        ev = self.stop_event
        flags = STATE_DISPLAY_ON if self.mode else STATE_DISPLAY_OFF
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | flags)
        try:
            while not ev.is_set():
                with self.lock:
                    expired = datetime.datetime.now() >= self.end_time
                if expired:
                    break
                ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | flags)
                ev.wait(30)
        finally:
            self._clear()

    def _clear(self):
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        with self.lock:
            self.running = False

    def stop(self):
        self.stop_event.set()
        self._clear()


class App:
    def __init__(self, root):
        self.root = root
        root.title("电脑休眠推迟工具")
        root.geometry("460x520")
        root.resizable(False, False)
        root.configure(bg="#f4f6fb")

        self.engine = Engine()
        self.tick_job = None

        self._build_ui()
        self._ui_idle()

    def _build_ui(self):
        c = ttk.Style()
        c.theme_use("clam")
        c.configure("TFrame", background="#f4f6fb")
        c.configure("Card.TFrame", background="#ffffff")
        c.configure("TLabel", background="#f4f6fb", foreground="#1a2333",
                    font=("Microsoft YaHei UI", 11))
        c.configure("Title.TLabel", background="#f4f6fb", foreground="#1a2333",
                    font=("Microsoft YaHei UI", 17, "bold"))
        c.configure("Sub.TLabel", background="#f4f6fb", foreground="#8a94a6",
                    font=("Microsoft YaHei UI", 10))
        c.configure("Card.TLabel", background="#ffffff", foreground="#1a2333",
                    font=("Microsoft YaHei UI", 11))
        c.configure("Big.TLabel", background="#ffffff", foreground="#1a2333",
                    font=("Microsoft YaHei UI", 24, "bold"))
        c.configure("Period.TLabel", background="#ffffff", foreground="#8a94a6",
                    font=("Microsoft YaHei UI", 10))
        c.configure("Run.TButton", background="#2f6feb", foreground="#ffffff",
                    font=("Microsoft YaHei UI", 12, "bold"), borderwidth=0)
        c.map("Run.TButton", background=[("active", "#1f5fd7"), ("disabled", "#b9c2d4")],
              foreground=[("disabled", "#eef1f7")])
        c.configure("Stop.TButton", background="#e5484d", foreground="#ffffff",
                    font=("Microsoft YaHei UI", 12, "bold"), borderwidth=0)
        c.map("Stop.TButton", background=[("active", "#c93a3f"), ("disabled", "#b9c2d4")],
              foreground=[("disabled", "#eef1f7")])
        c.configure("Card.TRadiobutton", background="#ffffff", foreground="#1a2333",
                    font=("Microsoft YaHei UI", 11))
        c.map("Card.TRadiobutton", background=[("active", "#ffffff")])
        c.configure("TProgressbar", background="#2f6feb", troughcolor="#eef1f7")
        c.configure("Card.TScale", background="#ffffff", troughcolor="#eef1f7")
        c.layout("Card.TScale", c.layout("Horizontal.TScale"))

        title = ttk.Label(self.root, text="休眠推迟", style="Title.TLabel")
        title.pack(anchor="w", padx=24, pady=(20, 0))
        ttk.Label(self.root, text="在指定时间内阻止电脑进入休眠", style="Sub.TLabel"
                  ).pack(anchor="w", padx=24, pady=(2, 12))

        card = ttk.Frame(self.root, style="Card.TFrame")
        card.pack(fill="x", padx=24, pady=6)

        self.status_text = tk.StringVar(value="无任务")
        ttk.Label(card, textvariable=self.status_text, style="Big.TLabel",
                  anchor="center").pack(fill="x", pady=(18, 2))
        self.period_text = tk.StringVar(value="系统可正常进入休眠")
        ttk.Label(card, textvariable=self.period_text, style="Period.TLabel",
                  anchor="center").pack(fill="x", pady=(0, 14))
        self.progress = ttk.Progressbar(card, maximum=100)
        self.progress.pack(fill="x", padx=24, pady=(0, 18))

        dur = ttk.Frame(card, style="Card.TFrame")
        dur.pack(fill="x", padx=24)
        row = ttk.Frame(dur, style="Card.TFrame")
        row.pack(fill="x")
        ttk.Label(row, text="推迟时长", style="Card.TLabel").pack(side="left")
        self.minute_str = tk.StringVar(value="30")
        self.spin = ttk.Spinbox(row, from_=1, to=MAX_MINUTES, increment=1,
                                textvariable=self.minute_str, width=6,
                                font=("Microsoft YaHei UI", 11), justify="right",
                                command=self._sync)
        self.spin.pack(side="right")
        self.summary = ttk.Label(dur, text="30 分钟", style="Card.TLabel", foreground="#2f6feb")
        self.summary.pack(anchor="e", pady=(0, 4))
        self.duration_var = tk.IntVar(value=30)
        ttk.Scale(dur, from_=1, to=MAX_MINUTES, variable=self.duration_var,
                  style="Card.TScale", command=self._on_slider).pack(fill="x")
        self.spin.bind("<KeyRelease>", lambda e: self._sync())
        self.spin.bind("<FocusOut>", lambda e: self._validate())
        self.spin.bind("<Return>", lambda e: self._validate())

        mode = ttk.Frame(card, style="Card.TFrame")
        mode.pack(fill="x", padx=24, pady=(14, 4))
        ttk.Label(mode, text="工作模式", style="Card.TLabel").pack(anchor="w")
        self.mode_var = tk.IntVar(value=0)
        for v, t in [(0, "仅阻止睡眠（允许屏幕关闭，省电）"),
                     (1, "阻止睡眠并保持屏幕常亮（接电视/远程）")]:
            ttk.Radiobutton(mode, text=t, value=v, variable=self.mode_var,
                            style="Card.TRadiobutton").pack(anchor="w", pady=2)
        ttk.Label(mode, text="到期后自动恢复系统休眠策略", style="Period.TLabel"
                  ).pack(anchor="w", pady=(6, 12))

        btns = ttk.Frame(self.root, style="TFrame")
        btns.pack(fill="x", padx=24, pady=16)
        self.start_btn = ttk.Button(btns, text="开始推迟", command=self.start,
                                    style="Run.TButton")
        self.start_btn.pack(side="left", expand=True, fill="x", padx=(0, 6), ipady=8)
        self.stop_btn = ttk.Button(btns, text="停止", command=self.stop,
                                   style="Stop.TButton", state="disabled")
        self.stop_btn.pack(side="right", expand=True, fill="x", padx=(6, 0), ipady=8)

    def _fmt(self, minutes):
        h, m = divmod(minutes, 60)
        if h and m:
            return f"{h} 小时 {m} 分钟"
        if h:
            return f"{h} 小时"
        return f"{m} 分钟"

    def _read_minutes(self):
        try:
            v = int(self.minute_str.get().strip())
        except ValueError:
            v = self.duration_var.get()
        return min(max(v, 1), MAX_MINUTES)

    def _sync(self):
        v = self._read_minutes()
        self.duration_var.set(v)
        self.summary.configure(text=self._fmt(v))

    def _on_slider(self, _):
        v = self.duration_var.get()
        self.minute_str.set(str(v))
        self.summary.configure(text=self._fmt(v))

    def _validate(self):
        self.minute_str.set(str(self._read_minutes()))
        self.summary.configure(text=self._fmt(self.duration_var.get()))

    def start(self):
        self._validate()
        minutes = self.duration_var.get()
        self.engine.start(minutes, self.mode_var.get())
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self._tick()

    def stop(self):
        self.engine.stop()
        self._ui_idle()

    def _tick(self):
        if not self.engine.running:
            self._ui_idle()
            return
        remain = (self.engine.end_time - datetime.datetime.now()).total_seconds()
        if remain <= 0:
            self.engine.stop()
            self._ui_idle()
            return
        m, s = int(remain // 60), int(remain % 60)
        total = (self.duration_var.get() * 60)
        self.status_text.set("正在推迟休眠")
        self.period_text.set(f"剩余 {m:02d}:{s:02d}  至 {self.engine.end_time.strftime('%H:%M:%S')}")
        self.progress["value"] = (1 - remain / total) * 100
        self.tick_job = self.root.after(500, self._tick)

    def _ui_idle(self):
        if self.tick_job:
            self.root.after_cancel(self.tick_job)
            self.tick_job = None
        self.engine.stop()
        self.status_text.set("无任务")
        self.period_text.set("系统可正常进入休眠")
        self.progress["value"] = 0
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    def on_close(self):
        self.engine.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()