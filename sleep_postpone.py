# -*- coding: utf-8 -*-
"""
电脑休眠推迟工具
在指定时长内阻止电脑进入休眠/睡眠，可选项控制是否保持屏幕常亮。
基于 Windows 的 SetThreadExecutionState 系统 API。
运行环境：Windows + Python 3（仅标准库，无需安装额外依赖）。
"""
import ctypes
import sys
import time
import threading
import datetime
import tkinter as tk
from tkinter import ttk

# SetThreadExecutionState 相关常量
ES_CONTINUOUS        = 0x80000000
ES_SYSTEM_REQUIRED   = 0x00000001
ES_DISPLAY_REQUIRED  = 0x00000002
ES_AWAYMODE_REQUIRED = 0x00000040

# 三种可用状态
STATE_DISPLAY_OFF   = ES_SYSTEM_REQUIRED                      # 只阻止睡眠，允许关屏
STATE_DISPLAY_ON    = ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED # 阻止睡眠且保持屏幕常亮


def set_exec_state(flags: int) -> int:
    """调用系统 API 设置执行状态，返回旧状态。"""
    return ctypes.windll.kernel32.SetThreadExecutionState(flags)


class PostponeApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("电脑休眠推迟工具")
        root.geometry("480x620")
        root.resizable(False, False)
        root.configure(bg="#f4f6fb")

        self.running = False
        self.end_time = None          # 倒计时结束时间（datetime）
        self.countdown_job = None
        self.stop_event = threading.Event()

        self._build_ui()
        self._update_status_ui()

    # ---------- 界面构建 ----------
    def _build_ui(self):
        c = ttk.Style()
        c.theme_use("clam")
        c.configure("TFrame", background="#f4f6fb")
        c.configure("Card.TFrame", background="#ffffff")
        c.configure("TLabel", background="#f4f6fb", foreground="#1a2333", font=("Microsoft YaHei UI", 11))
        c.configure("Title.TLabel", background="#f4f6fb", foreground="#1a2333",
                    font=("Microsoft YaHei UI", 18, "bold"))
        c.configure("Sub.TLabel", background="#f4f6fb", foreground="#8a94a6",
                    font=("Microsoft YaHei UI", 10))
        c.configure("Card.TLabel", background="#ffffff", foreground="#1a2333",
                    font=("Microsoft YaHei UI", 11))
        c.configure("Big.TLabel", background="#ffffff", foreground="#1a2333",
                    font=("Microsoft YaHei UI", 26, "bold"))
        c.configure("Period.TLabel", background="#ffffff", foreground="#8a94a6",
                    font=("Microsoft YaHei UI", 10))
        c.configure("Run.TButton", background="#2f6feb", foreground="#ffffff",
                    font=("Microsoft YaHei UI", 12, "bold"), borderwidth=0)
        c.map("Run.TButton", background=[("active", "#1f5fd7"), ("disabled", "#b9c2d4")],
              foreground=[("disabled", "#eef1f7")])
        c.configure("Stop.TButton", background="#e5484d", foreground="#ffffff",
                    font=("Microsoft YaHei UI", 12, "bold"), borderwidth=0)
        c.map("Stop.TButton", background=[("active", "#c93a3f")])
        c.configure("Card.TRadiobutton", background="#ffffff", foreground="#1a2333",
                    font=("Microsoft YaHei UI", 11))
        c.map("Card.TRadiobutton", background=[("active", "#ffffff")])
        c.configure("Card.Horizontal.TProgressbar", background="#2f6feb", troughcolor="#eef1f7")
        c.configure("Card.TScale", background="#ffffff", troughcolor="#eef1f7")

        # --- 顶部标题 ---
        title = ttk.Label(root, text="休眠推迟", style="Title.TLabel")
        title.pack(anchor="w", padx=24, pady=(22, 0))
        sub = ttk.Label(root, text="在指定时间内阻止电脑进入休眠状态", style="Sub.TLabel")
        sub.pack(anchor="w", padx=24, pady=(2, 12))

        # --- 主卡片 ---
        card = ttk.Frame(root, style="Card.TFrame")
        card.pack(fill="x", padx=24, pady=6)

        # 状态大标题
        self.status_text = tk.StringVar(value="当前：无任务")
        self.status_label = ttk.Label(card, textvariable=self.status_text,
                                      style="Big.TLabel", anchor="center")
        self.status_label.pack(fill="x", pady=(20, 4))

        self.period_text = tk.StringVar(value="系统可正常进入休眠")
        self.period_label = ttk.Label(card, textvariable=self.period_text,
                                      style="Period.TLabel", anchor="center")
        self.period_label.pack(fill="x", pady=(0, 16))

        # 倒计时进度条
        self.progress = ttk.Progressbar(card, style="Card.Horizontal.TProgressbar",
                                        maximum=100)
        self.progress.pack(fill="x", padx=24, pady=(0, 20))

        # --- 时长选择 ---
        dur_frame = ttk.Frame(card, style="Card.TFrame")
        dur_frame.pack(fill="x", padx=24)
        row = ttk.Frame(dur_frame, style="Card.TFrame")
        row.pack(fill="x")
        ttk.Label(row, text="推迟时长", style="Card.TLabel").pack(side="left")
        # 可精确输入自定义分钟数的输入框（带上下箭头）
        self.minute_str = tk.StringVar(value="30")
        self.spin = ttk.Spinbox(row, from_=1, to=1440, increment=1,
                                textvariable=self.minute_str, width=7,
                                font=("Microsoft YaHei UI", 11), justify="right",
                                command=self._sync_from_spinbox)
        self.spin.pack(side="right")
        self.minute_label = ttk.Label(dur_frame, text="分钟", style="Period.TLabel")
        self.minute_label.pack(anchor="e")
        # 与输入框联动的时间标签（显示“x 分钟 / x 小时 x 分钟”）
        self.duration_label = ttk.Label(dur_frame, text="30 分钟",
                                        style="Card.TLabel", foreground="#2f6feb")
        self.duration_label.pack(anchor="e", pady=(0, 4))
        # 快捷滑块，随输入框同步
        self.duration_var = tk.IntVar(value=30)
        slider = ttk.Scale(dur_frame, from_=1, to=1440, variable=self.duration_var,
                           style="Card.TScale", command=self._on_slider)
        slider.pack(fill="x")
        # 绑定输入事件：输入时实时联动，失焦时校验修正
        self.spin.bind("<KeyRelease>", lambda e: self._sync_from_spinbox(silent=True))
        self.spin.bind("<FocusOut>", lambda e: self._validate_spinbox())
        self.spin.bind("<Return>", lambda e: self._validate_spinbox())

        # --- 工作模式 ---
        mode_frame = ttk.Frame(card, style="Card.TFrame")
        mode_frame.pack(fill="x", padx=24, pady=(16, 4))
        ttk.Label(mode_frame, text="工作模式", style="Card.TLabel").pack(anchor="w")
        self.mode_var = tk.IntVar(value=0)
        modes = [
            (0, "仅阻止睡眠（允许屏幕关闭，省电）"),
            (1, "阻止睡眠并保持屏幕常亮"),
        ]
        for val, text in modes:
            ttk.Radiobutton(mode_frame, text=text, value=val,
                            variable=self.mode_var, style="Card.TRadiobutton"
                            ).pack(anchor="w", pady=2)
        ttk.Label(mode_frame, text="提示：接电视/投影/远程时建议保持屏幕常亮",
                  style="Period.TLabel").pack(anchor="w", pady=(4, 12))

        # --- 按钮区 ---
        btn_frame = ttk.Frame(root, style="TFrame")
        btn_frame.pack(fill="x", padx=24, pady=20)
        self.start_btn = ttk.Button(btn_frame, text="开始推迟", command=self.start,
                                    style="Run.TButton")
        self.start_btn.pack(side="left", expand=True, fill="x", padx=(0, 6), ipady=8)
        self.stop_btn = ttk.Button(btn_frame, text="停止", command=self.stop,
                                   style="Stop.TButton", state="disabled")
        self.stop_btn.pack(side="right", expand=True, fill="x", padx=(6, 0), ipady=8)

    # ---------- 行为 ----------
    def _format_minutes(self, minutes: int) -> str:
        h, m = divmod(minutes, 60)
        if h and m:
            return f"{h} 小时 {m} 分钟"
        if h:
            return f"{h} 小时"
        return f"{m} 分钟"

    def _refresh_duration_label(self, minutes: int):
        self.duration_label.configure(text=self._format_minutes(minutes))

    def _on_slider(self, _):
        minutes = self.duration_var.get()
        self.minute_str.set(str(minutes))
        self._refresh_duration_label(minutes)

    def _read_minutes(self):
        """从输入框读取分钟数，非法时返回当前值。"""
        try:
            v = int(self.minute_str.get().strip())
        except ValueError:
            return self.duration_var.get()
        return min(max(v, 1), 1440)

    def _sync_from_spinbox(self, silent=False):
        """输入或箭头变化时实时联动滑块与标签。"""
        mn = self._read_minutes()
        self.duration_var.set(mn)
        if not silent:
            self.duration_label.configure(text=self._format_minutes(mn))
        else:
            # 输入过程中显示用户正在填写的值（若有效）
            try:
                self.duration_label.configure(text=self._format_minutes(mn))
            except Exception:
                pass

    def _validate_spinbox(self):
        """失焦/回车时强制修正为合法值。"""
        self.minute_str.set(str(self._read_minutes()))
        self._refresh_duration_label(self.duration_var.get())

    def start(self):
        self._validate_spinbox()
        minutes = self.duration_var.get()
        if minutes <= 0:
            return
        self.running = True
        self.end_time = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
        self.stop_event.clear()
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")

        flags = STATE_DISPLAY_ON if self.mode_var.get() == 1 else STATE_DISPLAY_OFF
        # ES_CONTINUOUS 使状态持续生效；在结束后需自行清除
        set_exec_state(ES_CONTINUOUS | flags)

        threading.Thread(target=self._watch_display, daemon=True).start()
        self._tick_countdown()

    def _watch_display(self):
        """在工作期间周期性续期显示器常亮状态（防止个别场景被重置）。"""
        on = self.mode_var.get() == 1
        flags = STATE_DISPLAY_ON if on else STATE_DISPLAY_OFF
        while not self.stop_event.is_set():
            set_exec_state(ES_CONTINUOUS | flags)
            self.stop_event.wait(30)

    def _tick_countdown(self):
        if not self.running:
            return
        remain = (self.end_time - datetime.datetime.now()).total_seconds()
        if remain <= 0:
            self._finish_from_expire()
            return
        m, s = int(remain // 60), int(remain % 60)
        self.status_text.set("正在推迟休眠")
        self.period_text.set(f"剩余 {m:02d}:{s:02d}  结束时间 {self.end_time.strftime('%H:%M:%S')}")
        self.progress["value"] = (1 - remain / (self.duration_var.get() * 60)) * 100
        self.countdown_job = self.root.after(500, self._tick_countdown)

    def _finish_from_expire(self):
        self.run_finish(reset_state=True)

    def stop(self):
        self.run_finish(reset_state=True)

    def run_finish(self, reset_state=True):
        self.running = False
        self.stop_event.set()
        if self.countdown_job:
            self.root.after_cancel(self.countdown_job)
            self.countdown_job = None
        if reset_state:
            # 清除系统/屏幕唤醒状态，恢复正常省电策略
            set_exec_state(ES_CONTINUOUS)
        self.progress["value"] = 0
        self._update_status_ui()

    def _update_status_ui(self):
        if self.running:
            return
        self.status_text.set("当前：无任务")
        self.period_text.set("系统可正常进入休眠")

    def on_close(self):
        self.run_finish(reset_state=True)
        self.root.destroy()


def main():
    root = tk.Tk()
    app = PostponeApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()