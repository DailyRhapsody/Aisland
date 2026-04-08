#!/usr/bin/env python3
"""
Aisland - AI Coding Dynamic Island for macOS
Daemon mode: always running in background, auto-shows when AI CLI detected.

Usage:
    python3 main.py                # Daemon mode (recommended)
    python3 main.py install        # Install as login auto-start service
    python3 main.py uninstall      # Remove auto-start service
    python3 main.py status         # Check daemon status
"""

import argparse
import os
import plistlib
import signal
import subprocess
import sys

import objc
from AppKit import (
    NSApplication,
    NSApp,
    NSApplicationActivationPolicyAccessory,
    NSTimer,
    NSEvent,
    NSLeftMouseUp,
)
from Foundation import NSObject
from PyObjCTools import AppHelper

from monitor import MultiMonitor, ToolStatus, ClaudeCodeMonitor
from island_ui import IslandWindowController

PLIST_LABEL = "com.aisland.daemon"
PLIST_PATH = os.path.expanduser(f"~/Library/LaunchAgents/{PLIST_LABEL}.plist")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PID_FILE = os.path.join(SCRIPT_DIR, ".aisland.pid")


# ============================================================
# App Delegate — daemon with auto show/hide
# ============================================================

class AislandAppDelegate(NSObject):

    def init(self):
        self = objc.super(AislandAppDelegate, self).init()
        if self is None:
            return None
        self._controller = None
        self._monitor = None
        self._poll_timer = None
        self._anim_timer = None
        self._island_visible = False
        return self

    def applicationDidFinishLaunching_(self, notification):
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

        # Write PID for status check
        try:
            with open(PID_FILE, "w") as f:
                f.write(str(os.getpid()))
        except OSError:
            pass

        self._monitor = MultiMonitor()
        self._controller = IslandWindowController()
        # Wire up approve/deny callbacks
        self._controller.on_approve = self._send_approval
        self._controller.on_deny = self._send_denial
        # Start hidden — will show when AI CLI detected
        self._island_visible = False

        # Click handler for the pill window
        NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            NSLeftMouseUp, lambda e: self._handle_click(e)
        )
        NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            NSLeftMouseUp, self._handle_local_click
        )

        # Poll every 2s (also handles show/hide logic)
        self._poll_timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            2.0, self, b"pollStatus:", None, True
        )
        # Animation every 400ms
        self._anim_timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.4, self, b"animTick:", None, True
        )

        self.pollStatus_(None)
        print("\033[1;36m")
        print("  ╔════════════════════════════════════════╗")
        print("  ║  Aisland daemon running                ║")
        print("  ║  Waiting for AI CLI...                 ║")
        print("  ║  Open Claude/Gemini/Codex to activate  ║")
        print("  ║  Ctrl+C to stop                        ║")
        print("  ╚════════════════════════════════════════╝")
        print("\033[0m")

    @objc.typedSelector(b"v@:@")
    def pollStatus_(self, timer):
        if not self._monitor:
            return

        statuses = self._monitor.get_all_status()
        active = [s for s in statuses if s.status != ToolStatus.OFFLINE]

        if active:
            # AI CLI detected — show island
            if not self._island_visible:
                self._controller.show()
                self._controller._apply_collapsed()
                self._island_visible = True
                print(f"\033[32m  ▸ Detected: {active[0].tool_name}\033[0m")
            self._controller.update_status(active[0])
        else:
            # No AI CLI running — hide island
            if self._island_visible:
                self._controller.hide()
                self._island_visible = False
                print("\033[33m  ▸ All AI CLIs exited, island hidden\033[0m")

    @objc.typedSelector(b"v@:@")
    def animTick_(self, timer):
        if self._controller and self._island_visible:
            self._controller.tick_animation()

    def _handle_click(self, event):
        if not self._controller or not self._island_visible:
            return
        screen_pt = NSEvent.mouseLocation()
        f = self._controller.window.frame()
        inside = (f.origin.x <= screen_pt.x <= f.origin.x + f.size.width and
                  f.origin.y <= screen_pt.y <= f.origin.y + f.size.height)
        if inside:
            if self._controller.expanded:
                # Only collapse if clicking in the top pill area (not buttons)
                btn_area_top = f.origin.y + 60
                if screen_pt.y > btn_area_top:
                    self._controller.toggle_expand()
                return
            self._controller.toggle_expand()
        else:
            # Click outside pill → collapse if expanded
            if self._controller.expanded:
                self._controller.toggle_expand()

    def _handle_local_click(self, event):
        if not self._controller or not self._island_visible:
            return event
        if self._controller.expanded:
            return event
        screen_pt = NSEvent.mouseLocation()
        f = self._controller.window.frame()
        if (f.origin.x <= screen_pt.x <= f.origin.x + f.size.width and
            f.origin.y <= screen_pt.y <= f.origin.y + f.size.height):
            self._controller.toggle_expand()
        return event

    def _send_approval(self):
        """Send 'y' approval to the Claude Code terminal."""
        print("\033[32m  ▸ Sending approval to terminal\033[0m")
        self._send_to_terminal("y\n")

    def _send_denial(self):
        """Send 'n' denial to the Claude Code terminal."""
        print("\033[33m  ▸ Sending denial to terminal\033[0m")
        self._send_to_terminal("n\n")

    def _send_to_terminal(self, text):
        """Inject a keystroke into the terminal running Claude Code.

        Strategy:
        1. Find the terminal app that owns Claude Code's tty.
        2. Use AppleScript to bring that app to the front, send the key, then
           restore focus — this is the only reliable cross-terminal method on macOS.
        3. Writing to /dev/ttyXXX only echoes to the display, not stdin, so we skip it.
        """
        char = text.strip()          # "y" or "n"
        if not char:
            return

        # Detect which terminal app owns Claude Code's tty
        claude_monitor = self._monitor.monitors.get("claude")
        terminal_app = self._detect_terminal_app(claude_monitor)

        print(f"\033[32m  ▸ Sending '{char}' via AppleScript → {terminal_app}\033[0m")

        # AppleScript: activate terminal, keystroke, restore previous app
        script = f'''
set prevApp to name of (info for (path to frontmost application))
tell application "{terminal_app}"
    activate
end tell
delay 0.1
tell application "System Events"
    keystroke "{char}"
    key code 36
end tell
delay 0.05
try
    tell application prevApp to activate
end try
'''
        try:
            result = subprocess.run(
                ["osascript", "-e", script], timeout=5, capture_output=True, text=True
            )
            if result.returncode != 0:
                print(f"\033[31m  ▸ AppleScript error: {result.stderr.strip()}\033[0m")
        except Exception as e:
            print(f"\033[31m  ▸ Send failed: {e}\033[0m")

    def _detect_terminal_app(self, claude_monitor) -> str:
        """Return the terminal app name that owns Claude Code's tty."""
        # Try to resolve the tty and find which app owns it via lsof
        try:
            if claude_monitor:
                tty_path = claude_monitor.get_tty()
                if tty_path:
                    # lsof the tty device to find all processes using it
                    result = subprocess.run(
                        ["lsof", tty_path], capture_output=True, text=True, timeout=3
                    )
                    output = result.stdout
                    for app in ("Ghostty", "iTerm2", "Terminal", "Alacritty", "kitty", "WezTerm"):
                        if app.lower() in output.lower():
                            return app
        except Exception:
            pass
        # Default: try Ghostty first (most common in the screenshots), then Terminal
        for app in ("Ghostty", "iTerm2", "Terminal"):
            try:
                result = subprocess.run(
                    ["pgrep", "-x", app], capture_output=True, timeout=2
                )
                if result.returncode == 0:
                    return app
            except Exception:
                pass
        return "Terminal"

    def applicationShouldTerminate_(self, sender):
        if self._poll_timer:
            self._poll_timer.invalidate()
        if self._anim_timer:
            self._anim_timer.invalidate()
        try:
            os.remove(PID_FILE)
        except OSError:
            pass
        return True


# ============================================================
# LaunchAgent install / uninstall
# ============================================================

def cmd_install():
    """Install Aisland as a macOS LaunchAgent (auto-start on login)."""
    python3 = sys.executable or "/usr/bin/python3"
    main_py = os.path.join(SCRIPT_DIR, "main.py")
    log_out = os.path.join(SCRIPT_DIR, "aisland.log")
    log_err = os.path.join(SCRIPT_DIR, "aisland.err.log")

    plist = {
        "Label": PLIST_LABEL,
        "ProgramArguments": [python3, main_py],
        "WorkingDirectory": SCRIPT_DIR,
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": log_out,
        "StandardErrorPath": log_err,
        "EnvironmentVariables": {
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
        },
    }

    os.makedirs(os.path.dirname(PLIST_PATH), exist_ok=True)
    with open(PLIST_PATH, "wb") as f:
        plistlib.dump(plist, f)

    # Load the agent
    subprocess.run(["launchctl", "unload", PLIST_PATH], capture_output=True)
    result = subprocess.run(["launchctl", "load", PLIST_PATH], capture_output=True, text=True)

    if result.returncode == 0:
        print("\033[1;32m")
        print("  ✓ Aisland installed as login service")
        print(f"    Plist:  {PLIST_PATH}")
        print(f"    Log:    {log_out}")
        print("    Will auto-start on next login")
        print("    Starting now...")
        print("\033[0m")
    else:
        print(f"\033[31m  ✗ Failed: {result.stderr}\033[0m")


def cmd_uninstall():
    """Remove the LaunchAgent."""
    subprocess.run(["launchctl", "unload", PLIST_PATH], capture_output=True)
    if os.path.exists(PLIST_PATH):
        os.remove(PLIST_PATH)
        print("\033[33m  ✓ Aisland service removed\033[0m")
    else:
        print("  No service found")


def cmd_status():
    """Check if Aisland daemon is running."""
    if os.path.exists(PID_FILE):
        with open(PID_FILE) as f:
            pid = f.read().strip()
        # Check if process is alive
        try:
            os.kill(int(pid), 0)
            print(f"\033[32m  ● Aisland running (PID {pid})\033[0m")

            # Also check what it's monitoring
            from monitor import MultiMonitor
            m = MultiMonitor()
            active = m.get_active_status()
            if active:
                for s in active:
                    print(f"    ▸ {s.tool_name}: {s.status.value}")
            else:
                print("    ▸ No AI CLI detected, island hidden")
            return
        except (ProcessLookupError, ValueError):
            os.remove(PID_FILE)

    # Check LaunchAgent
    installed = os.path.exists(PLIST_PATH)
    if installed:
        print("\033[33m  ○ Service installed but not running\033[0m")
    else:
        print("\033[31m  ○ Aisland not running, not installed\033[0m")
        print("    Run: python3 main.py install")


# ============================================================
# Entry
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Aisland - AI Coding Dynamic Island for macOS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
commands:
  (none)      Start daemon (auto show/hide island)
  install     Install as login auto-start service
  uninstall   Remove auto-start service
  status      Check if daemon is running
        """,
    )
    parser.add_argument("command", nargs="?", default=None,
                        choices=["install", "uninstall", "status"])
    args = parser.parse_args()

    if args.command == "install":
        cmd_install()
        return
    elif args.command == "uninstall":
        cmd_uninstall()
        return
    elif args.command == "status":
        cmd_status()
        return

    # Default: run daemon
    app = NSApplication.sharedApplication()
    delegate = AislandAppDelegate.alloc().init()
    app.setDelegate_(delegate)

    signal.signal(signal.SIGINT, lambda *_: AppHelper.stopEventLoop())

    try:
        AppHelper.runEventLoop()
    except KeyboardInterrupt:
        try:
            os.remove(PID_FILE)
        except OSError:
            pass
        print("\nAisland stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
