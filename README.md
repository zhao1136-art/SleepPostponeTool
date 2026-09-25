# 电脑休眠推迟工具

一个轻量的 Windows 桌面小工具：在指定的时长内阻止电脑进入休眠，到期后自动恢复系统的休眠策略。适用于下载、渲染、跑批任务等不希望电脑中途睡着的场景。

基于 Windows 系统 API `SetThreadExecutionState` 实现，使用 `tkinter` 构建独立图形窗口，无需浏览器。

## 功能特性

- **自定义推迟时长**：从 1 分钟到 24 小时（1440 分钟），支持输入框和滑杆两种调节方式
- **两种工作模式**：
  - 仅阻止睡眠 —— 允许屏幕关闭，更省电
  - 阻止睡眠并保持屏幕常亮 —— 适合接电视 / 远程查看
- **实时倒计时**：窗口内显示剩余时间、结束时刻和进度条
- **到期自动恢复**：任务结束后自动清空系统睡眠限制，不影响后续正常休眠
- **单文件 EXE**：基于 PyInstaller 打包，双击即用，无需安装 Python

## 使用方法

### 方式一：直接运行 EXE

运行打包好的 `dist/SleepPostponeTool.exe`，弹出独立小窗口：

1. 设置「推迟时长」（分钟）
2. 选择「工作模式」
3. 点击「开始推迟」→ 任务启动并开始倒计时
4. 需要提前结束时点击「停止」

> 提示：点击「停止」或任务到期后，系统会立即恢复正常休眠策略。

### 方式二：源码运行

需要 Python 3.9+ 环境（Windows），无需第三方依赖：

```bash
python desktop.py
```

## 构建打包

在项目根目录执行：

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --name SleepPostponeTool desktop.py
```

生成的可执行文件位于 `dist/SleepPostponeTool.exe`。

## 项目结构

```
.
├── desktop.py          # 桌面窗口版主程序（推荐）
├── app.py              # 网页版实现（演示 / 备用）
├── sleep_postpone.py   # 早期 GUI 原型
└── dist/               # 打包输出目录
```

## 工作原理

程序通过 `ctypes` 调用 `SetThreadExecutionState`，在会话期间持续保持 `ES_CONTINUOUS | ES_SYSTEM_REQUIRED`（可加 `ES_DISPLAY_REQUIRED` 保持屏幕常亮）来阻止系统休眠；任务到期或手动停止时，恢复仅 `ES_CONTINUOUS` 状态，解除限制。

## License

[MIT](LICENSE)