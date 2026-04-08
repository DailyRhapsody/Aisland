#!/usr/bin/env python3
"""Test Aisland UI components step by step."""

import sys
import time
import objc

from AppKit import (
    NSApplication, NSApp, NSApplicationActivationPolicyAccessory,
    NSTimer, NSEvent, NSLeftMouseUp,
    NSWindow, NSWindowStyleMaskBorderless, NSBackingStoreBuffered,
    NSColor, NSView, NSBezierPath, NSMakeRect, NSScreen, NSFloatingWindowLevel,
    NSTextField, NSFont,
)
from Foundation import NSObject
from PyObjCTools import AppHelper

from monitor import MultiMonitor, ToolStatus, StatusInfo
from pixel_art import (
    CLAUDE_IDLE_1, CLAUDE_THINK_1, CLAUDE_EXEC_1, CLAUDE_WAIT_1, CLAUDE_OFFLINE, CLAUDE_ERROR,
    CLAUDE_PALETTE, CLAUDE_PALETTE_OFFLINE, STATUS_ACCENT,
    THOUGHT_BUBBLE_1, EXCLAMATION, ZZZ_1, LIGHTNING,
)


def ns_color(rgba):
    if rgba is None:
        return None
    return NSColor.colorWithCalibratedRed_green_blue_alpha_(*rgba)


# ---- Minimal pixel renderer (pure NSView, no fancy selectors) ----

class TestPixelView(NSView):
    def initWithFrame_(self, frame):
        self = objc.super(TestPixelView, self).initWithFrame_(frame)
        if self is None:
            return None
        self._grid = None
        self._overlay = None
        self._palette = CLAUDE_PALETTE
        self._ps = 3
        return self

    def drawRect_(self, rect):
        if not self._grid:
            return
        ps = self._ps
        rows = len(self._grid)
        for r, row in enumerate(self._grid):
            for c, val in enumerate(row):
                rgba = self._palette.get(val)
                if rgba is None:
                    continue
                color = ns_color(rgba)
                if color:
                    color.set()
                    y = (rows - 1 - r) * ps
                    x = c * ps
                    NSBezierPath.fillRect_(NSMakeRect(x, y, ps, ps))

        if self._overlay:
            overlay_rows = len(self._overlay)
            cols = len(self._grid[0]) if self._grid else 0
            ox = cols * ps + 4
            oy = rows * ps - overlay_rows * ps
            for r2, row2 in enumerate(self._overlay):
                for c2, val2 in enumerate(row2):
                    rgba2 = self._palette.get(val2)
                    if rgba2 is None:
                        continue
                    color2 = ns_color(rgba2)
                    if color2:
                        color2.set()
                        y2 = oy + (overlay_rows - 1 - r2) * ps
                        x2 = ox + c2 * ps
                        NSBezierPath.fillRect_(NSMakeRect(x2, y2, ps, ps))


# ---- Test app ----

STATES = [
    ("OFFLINE",  CLAUDE_OFFLINE, ZZZ_1,          CLAUDE_PALETTE_OFFLINE, ToolStatus.OFFLINE),
    ("IDLE",     CLAUDE_IDLE_1,  None,            CLAUDE_PALETTE,         ToolStatus.IDLE),
    ("THINKING", CLAUDE_THINK_1, THOUGHT_BUBBLE_1,CLAUDE_PALETTE,         ToolStatus.THINKING),
    ("EXECUTING",CLAUDE_EXEC_1,  LIGHTNING,        CLAUDE_PALETTE,         ToolStatus.TOOL_EXECUTING),
    ("ACTION!",  CLAUDE_WAIT_1,  EXCLAMATION,      CLAUDE_PALETTE,         ToolStatus.WAITING_CONFIRM),
    ("ERROR",    CLAUDE_ERROR,   None,             CLAUDE_PALETTE,         ToolStatus.ERROR),
]


class TestDelegate(NSObject):
    def init(self):
        self = objc.super(TestDelegate, self).init()
        self._idx = 0
        self._window = None
        self._pixel_view = None
        self._label = None
        self._timer = None
        return self

    def applicationDidFinishLaunching_(self, notification):
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

        screen = NSScreen.mainScreen().frame()
        w, h = 320, 120
        x = (screen.size.width - w) / 2
        y = screen.size.height - h - 10

        self._window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(x, y, w, h),
            NSWindowStyleMaskBorderless,
            NSBackingStoreBuffered,
            False,
        )
        self._window.setLevel_(NSFloatingWindowLevel)
        self._window.setOpaque_(False)
        self._window.setBackgroundColor_(NSColor.clearColor())
        self._window.setHasShadow_(True)
        self._window.setMovableByWindowBackground_(True)

        content = self._window.contentView()

        # Background pill
        bg = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, w, h))
        bg.setWantsLayer_(True)
        bg.layer().setBackgroundColor_(
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0.06, 0.06, 0.08, 0.95).CGColor()
        )
        bg.layer().setCornerRadius_(24)
        content.addSubview_(bg)

        # Pixel art view
        ps = 3
        avatar_w = (12 + 6) * ps
        avatar_h = 14 * ps
        self._pixel_view = TestPixelView.alloc().initWithFrame_(
            NSMakeRect(16, (h - avatar_h) / 2, avatar_w, avatar_h)
        )
        content.addSubview_(self._pixel_view)

        # Status label
        self._label = NSTextField.alloc().initWithFrame_(NSMakeRect(80, h/2 + 8, 220, 24))
        self._label.setStringValue_("Testing...")
        self._label.setBezeled_(False)
        self._label.setDrawsBackground_(False)
        self._label.setEditable_(False)
        self._label.setSelectable_(False)
        self._label.setFont_(NSFont.monospacedSystemFontOfSize_weight_(16, 0.5))
        self._label.setTextColor_(NSColor.whiteColor())
        content.addSubview_(self._label)

        # Sublabel
        self._sublabel = NSTextField.alloc().initWithFrame_(NSMakeRect(80, h/2 - 16, 220, 18))
        self._sublabel.setStringValue_("cycle every 2s")
        self._sublabel.setBezeled_(False)
        self._sublabel.setDrawsBackground_(False)
        self._sublabel.setEditable_(False)
        self._sublabel.setSelectable_(False)
        self._sublabel.setFont_(NSFont.monospacedSystemFontOfSize_weight_(11, 0.3))
        self._sublabel.setTextColor_(
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0.5, 0.5, 0.55, 1.0)
        )
        content.addSubview_(self._sublabel)

        self._window.makeKeyAndOrderFront_(None)

        # Cycle states every 2 seconds
        self._timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            2.0, self, b"nextState:", None, True
        )
        self.nextState_(None)
        print("Test UI running — cycling 6 states every 2s. Ctrl+C to stop.")

    @objc.typedSelector(b"v@:@")
    def nextState_(self, timer):
        name, grid, overlay, palette, status = STATES[self._idx % len(STATES)]

        # Apply status accent
        p = dict(palette)
        accent = STATUS_ACCENT.get(status)
        if accent:
            p[4] = accent

        self._pixel_view._grid = grid
        self._pixel_view._overlay = overlay
        self._pixel_view._palette = p
        self._pixel_view.setNeedsDisplay_(True)

        color = ns_color(STATUS_ACCENT.get(status, (1,1,1,1)))
        self._label.setStringValue_(f"  {name}")
        self._label.setTextColor_(color)
        self._sublabel.setStringValue_(f"  state {self._idx % len(STATES) + 1}/6")

        self._idx += 1

    def applicationShouldTerminate_(self, sender):
        if self._timer:
            self._timer.invalidate()
        return True


def main():
    import signal
    app = NSApplication.sharedApplication()
    delegate = TestDelegate.alloc().init()
    app.setDelegate_(delegate)
    signal.signal(signal.SIGINT, lambda *_: AppHelper.stopEventLoop())
    try:
        AppHelper.runEventLoop()
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == "__main__":
    main()
