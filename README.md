# Aisland

macOS 灵动岛风格的像素游戏悬浮组件，监控 Vibe Coding 时 AI 工具的运行状态。

**守护模式运行** — 后台常驻，打开任意 AI CLI 自动弹出，全部退出自动隐藏。

```
  ╔═══════════════════════════════════════════╗
  ║  [像素小人]  Claude Code   THINKING...    ║
  ╚═══════════════════════════════════════════╝
```

## Quick Start

```bash
# 安装依赖
pip3 install pyobjc-framework-Cocoa pyobjc-framework-Quartz

# 启动守护进程
python3 main.py

# 设为开机自启（推荐）
python3 main.py install
```

就这样。打开终端运行 `claude` / `gemini` / `codex`，灵动岛会自动出现。

## Commands

| Command | Description |
|---------|-------------|
| `python3 main.py` | 启动守护进程 |
| `python3 main.py install` | 安装为 macOS 登录自启服务 |
| `python3 main.py uninstall` | 移除自启服务 |
| `python3 main.py status` | 查看守护进程状态 |

## How It Works

```
打开终端 → 运行 claude → Aisland 自动弹出像素岛
                          ↓
                 AI 思考中 → 像素小人眼睛朝上 + 气泡动画
                 执行工具 → 像素小人奔跑 + 闪电
                 需要确认 → 灵动岛自动展开 + 小人挥手
                 确认完成 → 自动收起
                          ↓
              退出 claude → Aisland 自动隐藏
```

## Pixel Avatar States

| Status | Avatar | Overlay | Auto Action |
|--------|--------|---------|-------------|
| SLEEPING | Eyes closed, dimmed | Z z z | — |
| READY | Standing, blinking | — | — |
| THINKING | Eyes up | Thought bubble | — |
| EXECUTING | Running pose | Lightning | — |
| ! ACTION ! | Arms waving | Exclamation ! | **Auto expand** |
| ERROR | X eyes | — | — |

## Supported Tools

| Tool | Status |
|------|--------|
| Claude Code | ✅ |
| Gemini CLI | 🔜 |
| Codex | 🔜 |

## Architecture

```
main.py        — Daemon entry, LaunchAgent install, auto show/hide
island_ui.py   — Dynamic Island window + pixel renderer
pixel_art.py   — Pixel art frames, palettes, animation defs
monitor.py     — AI tool process monitors (extensible)
```

## Adding a New AI Tool

1. Design pixel art frames in `pixel_art.py` (12×14 grid, 7-color palette)
2. Register in `TOOL_ASSETS`
3. Subclass `BaseMonitor` in `monitor.py`
4. Register in `MONITORS` dict
