"""
AI Coding Tool Process Monitor
Monitors the status of AI coding assistants (Claude Code, Gemini CLI, Codex, etc.)
"""

import os
import subprocess
import time
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ToolStatus(Enum):
    OFFLINE = "offline"
    IDLE = "idle"
    THINKING = "thinking"
    TOOL_EXECUTING = "tool_executing"
    WAITING_CONFIRM = "waiting_confirm"
    STREAMING = "streaming"
    ERROR = "error"


@dataclass
class StatusInfo:
    tool_name: str
    status: ToolStatus
    detail: str = ""
    model: str = ""
    pid: Optional[int] = None
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    elapsed_seconds: float = 0.0


class BaseMonitor(ABC):
    """Base class for AI tool monitors."""

    @property
    @abstractmethod
    def tool_name(self) -> str:
        ...

    @property
    @abstractmethod
    def process_pattern(self) -> str:
        """Regex pattern to match the process."""
        ...

    @abstractmethod
    def parse_status(self, pid: int, cpu: float, mem_mb: float) -> StatusInfo:
        """Determine detailed status from process metrics."""
        ...

    def find_process(self) -> Optional[dict]:
        """Find the AI tool process and return pid, cpu%, mem info."""
        try:
            result = subprocess.run(
                ["ps", "aux"], capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.strip().split("\n")[1:]:
                if re.search(self.process_pattern, line):
                    parts = line.split(None, 10)
                    if len(parts) >= 11:
                        pid = int(parts[1])
                        cpu = float(parts[2])
                        mem_kb = float(parts[5]) if parts[5].replace('.','').isdigit() else 0
                        return {"pid": pid, "cpu": cpu, "mem_mb": mem_kb / 1024, "cmd": parts[10]}
        except Exception:
            pass
        return None

    def get_status(self) -> StatusInfo:
        proc = self.find_process()
        if proc is None:
            return StatusInfo(
                tool_name=self.tool_name,
                status=ToolStatus.OFFLINE,
                detail="Not running",
            )
        return self.parse_status(proc["pid"], proc["cpu"], proc["mem_mb"])


class ClaudeCodeMonitor(BaseMonitor):
    """Monitor for Claude Code CLI."""

    def __init__(self):
        self._last_high_cpu_time = 0.0
        self._thinking_start = 0.0
        self._my_pid = os.getpid()
        self._had_activity = False       # True after we've seen high CPU
        self._idle_after_activity = 0.0  # timestamp when CPU first dropped after activity

    @property
    def tool_name(self) -> str:
        return "Claude Code"

    @property
    def process_pattern(self) -> str:
        return r"(?i)\bclaude\b"

    def find_process(self) -> Optional[dict]:
        """Find Claude Code CLI process, excluding Claude.app and self."""
        try:
            result = subprocess.run(
                ["ps", "aux"], capture_output=True, text=True, timeout=5
            )
            best = None
            for line in result.stdout.strip().split("\n")[1:]:
                if not re.search(r"(?i)\bclaude\b", line):
                    continue
                # Skip Claude.app desktop processes, helpers, grep, aisland
                if any(skip in line for skip in [
                    "Claude.app", "Claude Helper", "claude_crashpad",
                    "grep", "aisland", "test_ui.py",
                ]):
                    continue
                parts = line.split(None, 10)
                if len(parts) < 11:
                    continue
                pid = int(parts[1])
                if pid == self._my_pid:
                    continue
                cpu = float(parts[2])
                mem_str = parts[5]
                mem_kb = float(mem_str) if mem_str.replace('.', '').isdigit() else 0
                proc = {"pid": pid, "cpu": cpu, "mem_mb": mem_kb / 1024, "cmd": parts[10]}
                # Prefer the process with highest CPU (the active one)
                if best is None or cpu > best["cpu"]:
                    best = proc
            return best
        except Exception:
            pass
        return None

    def _get_model_info(self) -> str:
        """Detect model from the latest Claude Code session JSONL."""
        try:
            import json, glob
            # Find the most recent session JSONL
            pattern = os.path.expanduser("~/.claude/projects/*/[0-9a-f]*.jsonl")
            files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
            for fp in files[:3]:
                # Read last few lines to find model
                with open(fp, 'rb') as f:
                    f.seek(0, 2)
                    size = f.tell()
                    f.seek(max(0, size - 8192))
                    lines = f.read().decode('utf-8', errors='ignore').strip().split('\n')
                for line in reversed(lines):
                    try:
                        d = json.loads(line)
                        msg = d.get('message', '')
                        if isinstance(msg, dict) and 'model' in msg:
                            return msg['model']
                        if isinstance(msg, str) and "'model':" in msg:
                            # Parse stringified dict
                            import ast
                            try:
                                parsed = ast.literal_eval(msg)
                                if isinstance(parsed, dict) and 'model' in parsed:
                                    return parsed['model']
                            except Exception:
                                pass
                    except Exception:
                        continue
        except Exception:
            pass
        return ""

    def _check_waiting_confirm(self, pid: int) -> bool:
        """Check if Claude Code is waiting for user confirmation.

        Heuristic: the process must be in background-sleep state (S without +)
        which on macOS indicates it is NOT the foreground process group leader
        actively processing user input, but a background job blocked on I/O.
        We also require sustained low CPU across multiple consecutive polls
        (self._CONFIRM_THRESHOLD) to avoid false positives from normal idle gaps.
        """
        try:
            result = subprocess.run(
                ["ps", "-o", "state=", "-p", str(pid)],
                capture_output=True, text=True, timeout=3
            )
            state = result.stdout.strip()
            # "S" without "+" means sleeping in a background process group.
            # "S+" means foreground — that is normal idle between completions.
            # Only consider background-sleeping as a potential confirm state.
            if state == "S":
                self._confirm_ticks += 1
                return self._confirm_ticks >= self._CONFIRM_THRESHOLD
            else:
                self._confirm_ticks = 0
        except Exception:
            self._confirm_ticks = 0
        return False

    def get_tty(self) -> Optional[str]:
        """Get the tty device path for the Claude Code process."""
        proc = self.find_process()
        if proc is None:
            return None
        try:
            result = subprocess.run(
                ["ps", "-o", "tty=", "-p", str(proc["pid"])],
                capture_output=True, text=True, timeout=3
            )
            tty = result.stdout.strip()
            if tty and tty != "??" and tty != "":
                return f"/dev/{tty}"
        except Exception:
            pass
        return None

    def parse_status(self, pid: int, cpu: float, mem_mb: float) -> StatusInfo:
        now = time.time()
        model = self._get_model_info()

        base = StatusInfo(
            tool_name=self.tool_name,
            pid=pid,
            cpu_percent=cpu,
            memory_mb=mem_mb,
            model=model,
            status=ToolStatus.IDLE,
        )

        # High CPU → thinking or tool executing
        if cpu > 15.0:
            if self._thinking_start == 0:
                self._thinking_start = now
            self._last_high_cpu_time = now
            self._had_activity = True
            self._idle_after_activity = 0.0  # reset idle timer
            elapsed = now - self._thinking_start
            base.status = ToolStatus.THINKING
            base.detail = f"Thinking... ({elapsed:.0f}s)"
            base.elapsed_seconds = elapsed
            return base

        # Recently had high CPU but now low → might be executing tools or streaming
        if now - self._last_high_cpu_time < 3.0 and self._last_high_cpu_time > 0:
            self._idle_after_activity = 0.0  # still active
            base.status = ToolStatus.TOOL_EXECUTING
            base.detail = "Executing..."
            return base

        # Reset thinking timer
        self._thinking_start = 0.0

        # WAITING_CONFIRM heuristic:
        # After activity (high CPU), if CPU stays near 0 for 6-30s,
        # Claude is likely waiting for user confirmation.
        # After 30s we assume it's just idle (task completed).
        if cpu < 5.0:
            if self._had_activity:
                if self._idle_after_activity == 0:
                    self._idle_after_activity = now
                idle_dur = now - self._idle_after_activity
                if 6.0 <= idle_dur <= 30.0:
                    base.status = ToolStatus.WAITING_CONFIRM
                    base.detail = f"Waiting for approval ({idle_dur:.0f}s)"
                    base.elapsed_seconds = idle_dur
                    return base
                elif idle_dur > 30.0:
                    # Too long — probably just idle, reset
                    self._had_activity = False
                    self._idle_after_activity = 0.0

        base.status = ToolStatus.IDLE
        base.detail = "Ready"
        return base


# Registry of available monitors
MONITORS = {
    "claude": ClaudeCodeMonitor,
    # Future: "gemini": GeminiCLIMonitor,
    # Future: "codex": CodexMonitor,
}


class MultiMonitor:
    """Monitors multiple AI tools simultaneously."""

    def __init__(self, tool_names: list[str] | None = None):
        if tool_names is None:
            tool_names = list(MONITORS.keys())
        self.monitors = {}
        for name in tool_names:
            if name in MONITORS:
                self.monitors[name] = MONITORS[name]()

    def get_all_status(self) -> list[StatusInfo]:
        return [m.get_status() for m in self.monitors.values()]

    def get_active_status(self) -> list[StatusInfo]:
        """Return only tools that are currently running."""
        return [s for s in self.get_all_status() if s.status != ToolStatus.OFFLINE]


if __name__ == "__main__":
    monitor = MultiMonitor()
    while True:
        statuses = monitor.get_all_status()
        for s in statuses:
            print(f"[{s.tool_name}] {s.status.value}: {s.detail} | CPU: {s.cpu_percent:.1f}% | MEM: {s.memory_mb:.0f}MB")
        print("---")
        time.sleep(2)
