# -*- coding: utf-8 -*-
"""
电脑休眠推迟工具 · 本地网页版
双击运行(exe)后自动在浏览器打开操作界面，在指定时长内阻止电脑进入休眠，
可自定义推迟分钟数，并选择是否保持屏幕常亮。
依赖：仅 Windows 系统 API + Python 标准库，后端内嵌前端页面，单文件即可。

用法（源码直接运行）：
    python sleep_postpone.py
打包：
    pyinstaller --onefile --noconsole --name SleepPostponeTool sleep_postpone.py
"""
import ctypes
import json
import threading
import datetime
import webbrowser
import os
import socket
import sys
import traceback
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# SetThreadExecutionState 相关常量
ES_CONTINUOUS        = 0x80000000
ES_SYSTEM_REQUIRED   = 0x00000001
ES_DISPLAY_REQUIRED  = 0x00000002

STATE_DISPLAY_OFF = ES_SYSTEM_REQUIRED                        # 仅阻止睡眠，允许关屏
STATE_DISPLAY_ON  = ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED   # 阻止睡眠且保持屏幕常亮

MAX_MINUTES = 1440  # 最长 24 小时


class Engine:
    """管理推迟会话：状态、倒计时、系统唤醒状态续期。"""

    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.mode = 0                 # 0=允许关屏 1=保持常亮
        self.total_seconds = 0
        self.end_timestamp = 0.0      # time.time() 秒
        self.stop_event = threading.Event()

    def start(self, minutes: int, mode: int):
        minutes = min(max(int(minutes), 1), MAX_MINUTES)
        with self.lock:
            self.stop_event.set()
            self.stop_event = threading.Event()
            self.running = True
            self.mode = 1 if mode == 1 else 0
            self.total_seconds = minutes * 60
            self.end_timestamp = time.time() + self.total_seconds
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        ev = self.stop_event
        flags = STATE_DISPLAY_ON if self._mode() else STATE_DISPLAY_OFF
        # ES_CONTINUOUS 使其持续生效
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | flags)
        try:
            while not ev.is_set():
                # 到期自动结束
                with self.lock:
                    expired = time.time() >= self.end_timestamp
                if expired:
                    break
                # 每 30 秒续期一次，防止个别场景被重置
                ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | flags)
                ev.wait(30)
        finally:
            self._clear_state()
            ev.set()

    def _mode(self):
        with self.lock:
            return self.mode

    def _clear_state(self):
        # 清除唤醒状态，恢复系统正常省电/休眠策略
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        with self.lock:
            self.running = False

    def stop(self):
        self.stop_event.set()
        self._clear_state()

    def snapshot(self) -> dict:
        with self.lock:
            if not self.running:
                return {"running": False}
            now = time.time()
            remaining = max(0, int(self.end_timestamp - now))
            return {
                "running": True,
                "remaining": remaining,
                "total": self.total_seconds,
                "mode": self.mode,
                "end": datetime.datetime.fromtimestamp(self.end_timestamp).strftime("%H:%M:%S"),
            }


engine = Engine()

# ---------------- 前端页面 ----------------
INDEX_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>电脑休眠推迟工具</title>
<style>
  :root{
    --bg:#f2f5fb; --card:#ffffff; --ink:#1a2333; --muted:#8a94a6;
    --brand:#2f6feb; --brand-dark:#1f5fd7; --danger:#e5484d; --track:#eef1f7;
    --dot:#c9d2e0;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--ink);
    font-family:"Microsoft YaHei UI","PingFang SC",system-ui,sans-serif;
    display:flex;justify-content:center;padding:32px 16px}
  .wrap{width:100%;max-width:440px}
  .head .title{font-size:26px;font-weight:700;letter-spacing:.5px}
  .head .sub{color:var(--muted);font-size:13px;margin-top:4px}
  .card{background:var(--card);border-radius:16px;margin-top:20px;
    box-shadow:0 8px 30px rgba(20,40,90,.06)}
  .card .pad{padding:20px 24px}

  /* 状态区 */
  .status{padding:26px 24px 4px;text-align:center}
  .status .big{font-size:30px;font-weight:700;display:flex;align-items:center;
    justify-content:center;gap:10px}
  .pulse{width:12px;height:12px;border-radius:50%;background:var(--danger);display:inline-block}
  .pulse.on{background:#16a34a;box-shadow:0 0 0 0 rgba(22,163,74,.6);animation:beat 1.6s infinite}
  @keyframes beat{70%{box-shadow:0 0 0 10px rgba(22,163,74,0)}100%{box-shadow:0 0 0 0 rgba(22,163,74,0)}}
  .status .sub{color:var(--muted);font-size:13px;margin-top:6px}
  .count{font-size:15px;color:var(--brand);font-weight:600;margin:14px 0 16px}
  .bar{height:10px;border-radius:6px;background:var(--track);overflow:hidden;
    margin:0 24px 26px}
  .bar i{display:block;height:100%;width:0%;background:linear-gradient(90deg,#2f6feb,#5b8cf5);
    border-radius:6px;transition:width .4s linear}

  /* 表单 */
  .field label{font-size:14px;font-weight:600;display:block}
  .field .hint{color:var(--muted);font-size:12px;margin-top:2px}
  .dur{display:flex;align-items:center;gap:8px;margin:10px 0 18px}
  .dur input{width:120px;padding:10px 12px;font-size:17px;font-weight:700;text-align:center;
    border:2px solid var(--track);border-radius:10px;color:var(--ink);
    font-family:inherit;outline:none;transition:border-color .15s}
  .dur input:focus{border-color:var(--brand)}
  .dur span{color:var(--muted);font-size:14px}
  .slider{width:100%;height:5px;border-radius:4px;background:var(--track);
    outline:none;-webkit-appearance:none;appearance:none;margin-top:2px}
  .slider::-webkit-slider-thumb{-webkit-appearance:none;appearance:none;width:18px;height:18px;
    border-radius:50%;background:var(--brand);cursor:pointer;border:3px solid #fff;
    box-shadow:0 1px 4px rgba(20,40,90,.3)}
  .mode{margin:16px 0 4px}
  .mode .item{display:flex;align-items:flex-start;gap:10px;padding:10px 12px;margin-top:8px;
    border:2px solid var(--track);border-radius:10px;cursor:pointer;transition:.15s;background:#fff}
  .mode .item.on{border-color:var(--brand);background:#f0f5ff}
  .mode .item .dot{width:16px;height:16px;border-radius:50%;border:2px solid var(--dot);
    margin-top:2px;flex:none}
  .mode .item.on .dot{border:5px solid var(--brand)}
  .mode .item .t{font-size:14px;font-weight:600}
  .mode .item .d{font-size:12px;color:var(--muted);margin-top:2px}

  /* 按钮 */
  .btns{display:flex;gap:10px;margin:22px 24px 20px}
  .btn{border:none;border-radius:12px;padding:13px;font-size:16px;font-weight:700;color:#fff;
    cursor:pointer;flex:1;font-family:inherit;transition:.15s;letter-spacing:1px}
  .btn.start{background:var(--brand)}
  .btn.start:hover{background:var(--brand-dark)}
  .btn.start:disabled{background:var(--track);color:#bdbdcc;cursor:not-allowed}
  .btn.stop{background:var(--danger)}
  .btn.stop:hover{filter:brightness(.92)}
  .btn.stop:disabled{background:var(--track);color:#bdbdcc;cursor:not-allowed}
  .foot{text-align:center;color:var(--muted);font-size:12px;margin-top:14px}
</style>
</head>
<body>
  <div class="wrap">
    <div class="head">
      <div class="title">休眠推迟</div>
      <div class="sub">在指定时间内阻止电脑进入休眠 · 本地运行</div>
    </div>

    <div class="card">
      <div class="status">
        <div class="big"><span class="pulse" id="pulse"></span><span id="big">无任务</span></div>
        <div class="sub" id="sub">系统可正常进入休眠</div>
        <div class="count" id="count"></div>
        <div class="bar"><i id="bar"></i></div>
      </div>

      <div class="pad">
        <div class="field">
          <label>自定义推迟时长</label>
          <div class="hint">支持输入任意分钟数，最长 1440 分钟（24 小时）</div>
          <div class="dur">
            <input id="min" type="number" min="1" max="1440" value="30">
            <span id="readable">30 分钟</span>
          </div>
          <input id="slider" class="slider" type="range" min="1" max="1440" value="30">
        </div>

        <div class="field mode">
          <label>工作模式</label>
          <div class="item on" data-mode="0" onclick="pickMode(this)">
            <div class="dot"></div>
            <div><div class="t">仅阻止睡眠</div><div class="d">允许屏幕关闭，更省电</div></div>
          </div>
          <div class="item" data-mode="1" onclick="pickMode(this)">
            <div class="dot"></div>
            <div><div class="t">保持屏幕常亮</div><div class="d">接电视 / 投影 / 远程时建议</div></div>
          </div>
        </div>
      </div>

      <div class="btns">
        <button class="btn start" id="start" onclick="start()">开始推迟</button>
        <button class="btn stop" id="stop" onclick="stop()" disabled>停止</button>
      </div>
    </div>
    <div class="foot">到期后自动恢复系统默认休眠策略</div>
  </div>

<script>
  let mode = 0;
  const $ = id => document.getElementById(id);
  const min = $("min"), slider = $("slider"), readable = $("readable");

  function fmt(s){
    s = Math.max(0, s);
    const h = Math.floor(s/3600), m = Math.floor(s%3600/60), sec = s%60;
    if(h) return h+" 小时 "+m+" 分钟";
    if(m) return m+" 分钟";
    return sec+" 秒";
  }
  function syncReadable(){
    const v = clamp(min.value);
    readable.textContent = mm(v);
    slider.value = v;
  }
  function clamp(v){ v = parseInt(v)||1; return Math.min(Math.max(v,1),1440); }
  function mm(v){ const h=Math.floor(v/60), m=v%60; return h? (h+" 小时"+(m?" "+m+" 分钟":"")) : v+" 分钟"; }

  min.oninput = syncReadable;
  min.onchange = ()=>{ min.value = clamp(min.value); syncReadable(); };
  slider.oninput = ()=>{ min.value = slider.value; syncReadable(); };

  function pickMode(el){
    document.querySelectorAll(".mode .item").forEach(i=>i.classList.remove("on"));
    el.classList.add("on"); mode = el.dataset.mode;
  }

  async function api(path, body){
    const r = await fetch(path, {method: body?"POST":"GET",
      headers: body?{"Content-Type":"application/json"}:undefined,
      body: body?JSON.stringify(body):undefined});
    return r.json();
  }

  async function start(){
    const minutes = clamp(min.value);
    await api("/api/start", {minutes, mode});
    setRunning(true);
  }
  async function stop(){
    await api("/api/stop");
    setRunning(false);
  }

  function setRunning(on){
    $("start").disabled = on;
    $("stop").disabled = !on;
    $("pulse").classList.toggle("on", on);
    $("big").textContent = on ? "正在推迟休眠" : "无任务";
    $("sub").textContent = on ? "" : "系统可正常进入休眠";
  }

  async function poll(){
    try{
      const s = await api("/api/state");
      if(s.running){
        setRunning(true);
        const pct = (1 - s.remaining/s.total)*100;
        $("bar").style.width = pct+"%";
        $("count").textContent = "剩余 " + fmt(s.remaining) +
          "　·　预计结束 " + s.end;
      } else {
        const bar = $("bar"); bar.style.width="0%";
        $("count").textContent = "";
      }
    }catch(e){ console.log(e); }
  }
  setInterval(poll, 500);
  poll();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"     # 使浏览器可长连接复用

    def log_message(self, *a):          # 关闭默认日志
        pass

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        try:
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        except Exception:
            traceback.print_exc()

    def do_GET(self):
        try:
            if self.path in ("/", "/index.html"):
                return self._send(200, INDEX_HTML)
            if self.path == "/api/state":
                return self._send(200, json.dumps(engine.snapshot(), ensure_ascii=False),
                                  "application/json; charset=utf-8")
            self._send(404, "not found", "text/plain")
        except Exception:
            traceback.print_exc()

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            payload = {}
        try:
            if self.path == "/api/start":
                engine.start(int(payload.get("minutes", 30)), int(payload.get("mode", 0)))
            elif self.path == "/api/stop":
                engine.stop()
            else:
                return self._send(404, "not found", "text/plain")
        except Exception:
            traceback.print_exc()
            return
        self._send(200, json.dumps({"ok": True}), "application/json; charset=utf-8")


BASE_PORT = 13479   # 固定端口，保证 exe 每次启动后网页地址不变


def pick_port():
    """优先用固定端口，被占用时向后顺延，确保 exe 重启后网址稳定可复用。"""
    for p in range(BASE_PORT, BASE_PORT + 100):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    return free_port()


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def main():
    # 允许通过命令行指定端口（便于调试）：python app.py <port>
    port = int(sys.argv[1]) if len(sys.argv) > 1 else pick_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print("Serving on", url, flush=True)
    # 稍后自动打开浏览器（后台线程，避免阻塞服务）
    threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        engine.stop()


if __name__ == "__main__":
    main()