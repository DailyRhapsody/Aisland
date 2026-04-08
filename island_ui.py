"""
Aisland - Dynamic Island UI for macOS
The pill is simply a WIDER version of the notch — same black, same shape.
Only bottom corners are rounded (matching the notch bottom edge).
Top edge is flush with the screen top, seamlessly extending the notch.
Content is placed on both SIDES of the notch (left: avatar, right: status).
"""

import objc
from AppKit import (
    NSPanel,
    NSWindowStyleMaskBorderless,
    NSWindowStyleMaskNonactivatingPanel,
    NSBackingStoreBuffered,
    NSColor,
    NSView,
    NSTextField,
    NSFont,
    NSFontManager,
    NSMakeRect,
    NSMakeSize,
    NSBezierPath,
    NSScreen,
    NSCenterTextAlignment,
    NSRightTextAlignment,
    NSTrackingArea,
    NSTrackingActiveAlways,
    NSTrackingMouseEnteredAndExited,
)
import Quartz
from monitor import ToolStatus, StatusInfo
from pixel_art import (
    TOOL_ASSETS, CLAUDE_PALETTE, CLAUDE_PALETTE_OFFLINE,
    STATUS_ACCENT, CLAUDE_ANIMATIONS,
)

# ── Window level ────────────────────────────────────────────
ISLAND_LEVEL = Quartz.CGWindowLevelForKey(Quartz.kCGStatusWindowLevelKey)

# ── Layout ──────────────────────────────────────────────────
PX_S = 1             # pixel art size collapsed (small, fits in notch bar)
PX_L = 3             # pixel art size expanded
CORNER_R = 16        # bottom inward corner radius (pill shape)

# Pill body width
CONTENT_W = 460
ARC_R = 12           # outward arc radius at top corners
COLLAPSED_W = CONTENT_W + 2 * ARC_R  # full view width
COLLAPSED_H = 33

# Expanded
EXPANDED_BELOW = 230
EXPANDED_W = CONTENT_W + 2 * ARC_R
EXPANDED_H = 33 + EXPANDED_BELOW

# Content x offset (body starts at ARC_R inside the view)
CX = ARC_R

# ── Colors ──────────────────────────────────────────────────
PILL_BG = (0.0, 0.0, 0.0, 1.0)
TEXT_W = (1.0, 1.0, 1.0, 1.0)
TEXT_DIM = (0.55, 0.55, 0.58, 1.0)
APPROVE_BG = (0.13, 0.42, 0.22, 1.0)
APPROVE_HV = (0.16, 0.55, 0.28, 1.0)
DENY_BG = (0.42, 0.13, 0.13, 1.0)
DENY_HV = (0.55, 0.16, 0.16, 1.0)

STATUS_NS = {}
for _st, _rgba in STATUS_ACCENT.items():
    STATUS_NS[_st] = NSColor.colorWithCalibratedRed_green_blue_alpha_(*_rgba)


def _cg(rgba):
    return Quartz.CGColorCreateGenericRGB(*rgba)


def _ns(rgba):
    return NSColor.colorWithCalibratedRed_green_blue_alpha_(*rgba) if rgba else None


class _PillBG(NSView):
    """Draws the pill background with outward arcs at top corners.

    Shape: body is CONTENT_W wide, centered in the view (offset by ARC_R).
    Top corners: outward (convex) quarter-circle arcs — the pill widens at the top.
    Bottom corners: standard inward (concave) quarter-circle arcs.

    Visual (zoomed top-right corner):

        screen top edge ───────────────────────┐ ear tip (w, h)
                                               │
                           outward arc ──>   ╮ │
                                            │  │
        body right edge (br, h-a) ──────────┘  │
                                               │ (not filled — transparent)
    """

    # Kappa constant for quarter-circle bezier approximation
    K = 0.5522847498

    def initWithFrame_(self, frame):
        self = objc.super(_PillBG, self).initWithFrame_(frame)
        if self is None:
            return None
        return self

    def isOpaque(self):
        return False

    def drawRect_(self, dirty):
        w = self.bounds().size.width
        h = self.bounds().size.height
        a = ARC_R           # outward arc radius (top)
        r = CORNER_R         # inward arc radius (bottom)
        k = self.K

        path = NSBezierPath.bezierPath()

        bl = a           # body left x
        br = w - a       # body right x

        # ── Start at top-left ear tip ──
        path.moveToPoint_((0, h))

        # ── Top edge ──
        path.lineToPoint_((w, h))

        # ── Top-right outward arc ──
        # Quarter circle from (w, h) down to (br, h-a)
        # Center of curvature at (br, h) — arc bows RIGHT (outward)
        path.curveToPoint_controlPoint1_controlPoint2_(
            (br, h - a),               # end
            (w, h - a * k),            # cp1: near start, heading down
            (br + a * k, h - a),       # cp2: near end, heading right→body
        )

        # ── Right side ──
        path.lineToPoint_((br, r))

        # ── Bottom-right inward arc ──
        # Quarter circle from (br, r) to (br-r, 0)
        # Center at (br-r, r) — arc bows inward (standard corner)
        path.curveToPoint_controlPoint1_controlPoint2_(
            (br - r, 0),               # end
            (br, r - r * k),           # cp1
            (br - r + r * k, 0),       # cp2
        )

        # ── Bottom edge ──
        path.lineToPoint_((bl + r, 0))

        # ── Bottom-left inward arc ──
        # Quarter circle from (bl+r, 0) to (bl, r)
        path.curveToPoint_controlPoint1_controlPoint2_(
            (bl, r),                   # end
            (bl + r - r * k, 0),       # cp1
            (bl, r - r * k),           # cp2
        )

        # ── Left side ──
        path.lineToPoint_((bl, h - a))

        # ── Top-left outward arc ──
        # Quarter circle from (bl, h-a) to (0, h)
        # Center of curvature at (bl, h) — arc bows LEFT (outward)
        path.curveToPoint_controlPoint1_controlPoint2_(
            (0, h),                    # end
            (bl - a * k, h - a),       # cp1: near start, heading left
            (0, h - a * k),            # cp2: near end, heading up
        )

        path.closePath()

        _ns(PILL_BG).set()
        path.fill()


def _font(sz=11):
    fm = NSFontManager.sharedFontManager()
    for name in ("Menlo", "JetBrains Mono", "SF Mono"):
        f = fm.fontWithFamily_traits_weight_size_(name, 0, 5, sz)
        if f:
            return f
    return NSFont.monospacedSystemFontOfSize_weight_(sz, 0.4)


def _label(text="", sz=11, rgba=TEXT_W):
    l = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 10, 10))
    l.setStringValue_(text)
    l.setBezeled_(False)
    l.setDrawsBackground_(False)
    l.setEditable_(False)
    l.setSelectable_(False)
    l.setFont_(_font(sz))
    l.setTextColor_(_ns(rgba))
    return l


def _notch_zones(pill_w):
    """Return (left_zone_end, right_zone_start) relative to the pill.
    Content left of left_zone_end is visible; right of right_zone_start is visible.
    Between them is behind the physical notch."""
    screen = NSScreen.mainScreen()
    sw = screen.frame().size.width
    try:
        aux = screen.auxiliaryTopLeftArea()
        if aux and aux.size.width > 0:
            notch_left = aux.size.width
            notch_w = sw - 2 * notch_left
            pill_x = (sw - pill_w) / 2
            return notch_left - pill_x, notch_left + notch_w - pill_x
    except Exception:
        pass
    # Fallback: assume 182px notch centered
    pill_x = (sw - pill_w) / 2
    nl = (sw - 182) / 2
    return nl - pill_x, nl + 182 - pill_x


# ============================================================
# Pixel Art View
# ============================================================

class _PixelView(NSView):
    def initWithFrame_(self, frame):
        self = objc.super(_PixelView, self).initWithFrame_(frame)
        if self is None:
            return None
        self._grid = None
        self._overlay = None
        self._pal = CLAUDE_PALETTE
        self._ps = PX_S
        return self

    def drawRect_(self, dirty):
        if not self._grid:
            return
        ps = self._ps
        rows = len(self._grid)
        for r, row in enumerate(self._grid):
            for c, val in enumerate(row):
                rgba = self._pal.get(val)
                if not rgba:
                    continue
                _ns(rgba).set()
                NSBezierPath.fillRect_(NSMakeRect(c * ps, (rows - 1 - r) * ps, ps, ps))
        if self._overlay:
            orows = len(self._overlay)
            cols = len(self._grid[0])
            ox = cols * ps + 2
            oy = (rows - orows) * ps + (rows * ps) // 3
            for r2, row2 in enumerate(self._overlay):
                for c2, val2 in enumerate(row2):
                    rgba2 = self._pal.get(val2)
                    if not rgba2:
                        continue
                    _ns(rgba2).set()
                    NSBezierPath.fillRect_(NSMakeRect(
                        ox + c2 * ps, oy + (orows - 1 - r2) * ps, ps, ps))


# ============================================================
# Progress bar
# ============================================================

class _Bar(NSView):
    def initWithFrame_(self, frame):
        self = objc.super(_Bar, self).initWithFrame_(frame)
        if self is None:
            return None
        self.setWantsLayer_(True)
        self.layer().setBackgroundColor_(_cg((0.15, 0.15, 0.18, 1.0)))
        self.layer().setCornerRadius_(2)
        self._fill = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 0, frame.size.height))
        self._fill.setWantsLayer_(True)
        self._fill.layer().setCornerRadius_(2)
        self._fill.layer().setBackgroundColor_(_cg((0.4, 0.7, 1.0, 1.0)))
        self.addSubview_(self._fill)
        self._w = frame.size.width
        self._h = frame.size.height
        return self

    def setProgress_color_(self, p, cg_color):
        p = max(0.0, min(1.0, p))
        self._fill.setFrame_(NSMakeRect(0, 0, self._w * p, self._h))
        self._fill.layer().setBackgroundColor_(cg_color)


# ============================================================
# Clickable button
# ============================================================

class _Btn(NSView):
    def initWithFrame_title_bg_hover_(self, frame, title, bg, hover):
        self = objc.super(_Btn, self).initWithFrame_(frame)
        if self is None:
            return None
        self._bg = bg
        self._hover = hover
        self._cb = None
        self.setWantsLayer_(True)
        self.layer().setBackgroundColor_(_cg(bg))
        self.layer().setCornerRadius_(8)
        lbl = _label(title, 11, TEXT_W)
        lbl.setFrame_(NSMakeRect(0, 4, frame.size.width, frame.size.height - 4))
        lbl.setAlignment_(NSCenterTextAlignment)
        self.addSubview_(lbl)
        ta = NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
            NSMakeRect(0, 0, frame.size.width, frame.size.height),
            NSTrackingActiveAlways | NSTrackingMouseEnteredAndExited, self, None)
        self.addTrackingArea_(ta)
        return self

    def mouseEntered_(self, e):
        self.layer().setBackgroundColor_(_cg(self._hover))
    def mouseExited_(self, e):
        self.layer().setBackgroundColor_(_cg(self._bg))
    def mouseDown_(self, e):
        self.layer().setBackgroundColor_(_cg(self._hover))
    def mouseUp_(self, e):
        self.layer().setBackgroundColor_(_cg(self._bg))
        if self._cb:
            self._cb()
    def acceptsFirstMouse_(self, e):
        return True


# ============================================================
# Status text
# ============================================================

_STATUS_TEXT = {
    ToolStatus.OFFLINE:         "SLEEPING",
    ToolStatus.IDLE:            "READY",
    ToolStatus.THINKING:        "THINKING...",
    ToolStatus.TOOL_EXECUTING:  "EXECUTING",
    ToolStatus.WAITING_CONFIRM: "! ACTION !",
    ToolStatus.STREAMING:       "STREAMING",
    ToolStatus.ERROR:           "ERROR",
}


# ============================================================
# IslandWindowController
# ============================================================

class IslandWindowController:
    """The pill is just a wider notch."""

    def __init__(self):
        self.expanded = False
        self.current_status = StatusInfo(
            tool_name="Claude Code", status=ToolStatus.OFFLINE, detail="Initializing...")
        self._anim_frame = 0
        self._anim_tick = 0
        self._tool_key = "claude"
        self._was_waiting = False
        self.on_approve = None
        self.on_deny = None

        self._sw = NSScreen.mainScreen().frame().size.width
        self._sh = NSScreen.mainScreen().frame().size.height

        # Notch-safe zones for content (relative to full view width)
        self._lz, self._rz = _notch_zones(COLLAPSED_W)
        self._lz_e, self._rz_e = _notch_zones(EXPANDED_W)
        # Content left inset: CX (=CORNER_R) for the outward arc margin

        # Panel
        self._panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, COLLAPSED_W, COLLAPSED_H),
            NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel,
            NSBackingStoreBuffered,
            False,
        )
        self._panel.setLevel_(ISLAND_LEVEL)
        self._panel.setOpaque_(False)
        self._panel.setBackgroundColor_(NSColor.clearColor())
        self._panel.setHasShadow_(False)
        self._panel.setMovableByWindowBackground_(False)
        self._panel.setIgnoresMouseEvents_(False)
        self._panel.setCollectionBehavior_(1 << 0 | 1 << 4)
        self._panel.setHidesOnDeactivate_(False)

        self._build_collapsed()
        self._build_expanded()

        self._collapsed_view.setHidden_(False)
        self._expanded_view.setHidden_(True)
        self._position(COLLAPSED_W, COLLAPSED_H)

    # ── Position: centered, top extending above screen ──────

    def _position(self, w, h):
        x = (self._sw - w) / 2
        y = self._sh - h  # top edge at screen top, rounded corners visible
        self._panel.setFrame_display_animate_(NSMakeRect(x, y, w, h), True, True)

    # ── Collapsed: content on both sides of notch ───────────
    #
    # Left zone (0 → lz):  [pad] [avatar] [tool name]
    # Notch zone (lz → rz): empty (behind hardware)
    # Right zone (rz → W):  [status dot] [status text] [pad]
    #
    # Y layout: content in the bottom 33px (top TOP_EXTEND is above screen)

    def _build_collapsed(self):
        W, H = COLLAPSED_W, COLLAPSED_H
        root = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, W, H))

        # Pill background with outward arcs (drawn via NSBezierPath)
        bg = _PillBG.alloc().initWithFrame_(NSMakeRect(0, 0, W, H))
        root.addSubview_(bg)

        lz = self._lz
        rz = self._rz
        cy = H / 2  # vertical center
        ox = CX  # content x offset for outward arc margin

        # ── Left: avatar + name ──
        aw = 12 * PX_S
        ah = 14 * PX_S
        self._c_av = _PixelView.alloc().initWithFrame_(
            NSMakeRect(ox + 4, cy - ah / 2, aw, ah))
        self._c_av._ps = PX_S
        root.addSubview_(self._c_av)

        nx = ox + 4 + aw + 5
        self._c_name = _label("Claude", 10, TEXT_DIM)
        self._c_name.setFrame_(NSMakeRect(nx, cy - 7, max(lz - nx - 4, 10), 14))
        root.addSubview_(self._c_name)

        # ── Right: dot + READY (vertically centered together) ──
        rpad = ox + 4
        self._c_label = _label("READY", 11, TEXT_W)
        self._c_label.sizeToFit()
        lw = self._c_label.frame().size.width
        lx = W - rpad - lw
        self._c_label.setFrame_(NSMakeRect(lx, cy - 7, lw + 2, 14))
        root.addSubview_(self._c_label)

        self._c_dot = NSView.alloc().initWithFrame_(
            NSMakeRect(lx - 10, cy - 3, 6, 6))
        self._c_dot.setWantsLayer_(True)
        self._c_dot.layer().setCornerRadius_(3)
        self._c_dot.layer().setBackgroundColor_(_cg((0.3, 0.85, 0.45, 1.0)))
        root.addSubview_(self._c_dot)

        self._collapsed_view = root
        self._panel.contentView().addSubview_(root)

    # ── Expanded ────────────────────────────────────────────

    def _build_expanded(self):
        W, H = EXPANDED_W, EXPANDED_H
        PAD = CX + 6  # padding from body edge
        root = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, W, H))

        # Pill background with outward arcs
        bg = _PillBG.alloc().initWithFrame_(NSMakeRect(0, 0, W, H))
        root.addSubview_(bg)

        # Top 33px = notch bar, below that = detail content
        CONTENT_TOP = H - 33
        ox = CX  # content x offset

        # ── Top bar: left=avatar+name, right=dot+status ──
        lz = self._lz_e
        rz = self._rz_e
        bar_cy = CONTENT_TOP + 33 / 2

        aw = 12 * PX_S
        ah = 14 * PX_S
        self._e_c_av = _PixelView.alloc().initWithFrame_(
            NSMakeRect(ox + 4, bar_cy - ah / 2, aw, ah))
        self._e_c_av._ps = PX_S
        root.addSubview_(self._e_c_av)

        nx = ox + 4 + aw + 5
        self._e_c_name = _label("Claude", 10, TEXT_DIM)
        self._e_c_name.setFrame_(NSMakeRect(nx, bar_cy - 7, max(lz - nx - 4, 10), 14))
        root.addSubview_(self._e_c_name)

        rpad = ox + 4
        self._e_c_label = _label("READY", 11, TEXT_W)
        self._e_c_label.sizeToFit()
        elw = self._e_c_label.frame().size.width
        elx = W - rpad - elw
        self._e_c_label.setFrame_(NSMakeRect(elx, bar_cy - 7, elw + 2, 14))
        root.addSubview_(self._e_c_label)

        self._e_c_dot = NSView.alloc().initWithFrame_(
            NSMakeRect(elx - 10, bar_cy - 3, 6, 6))
        self._e_c_dot.setWantsLayer_(True)
        self._e_c_dot.layer().setCornerRadius_(3)
        self._e_c_dot.layer().setBackgroundColor_(_cg((0.3, 0.85, 0.45, 1.0)))
        root.addSubview_(self._e_c_dot)

        # ── Separator between notch bar and detail ──
        sep = NSView.alloc().initWithFrame_(NSMakeRect(PAD, CONTENT_TOP - 1, W - PAD * 2, 1))
        sep.setWantsLayer_(True)
        sep.layer().setBackgroundColor_(_cg((0.2, 0.2, 0.24, 0.6)))
        root.addSubview_(sep)

        # ── Detail area below (from CONTENT_TOP downward) ──
        cy = CONTENT_TOP

        # Large avatar + name + status
        aw2 = (12 + 5) * PX_L
        ah2 = 14 * PX_L
        self._e_av = _PixelView.alloc().initWithFrame_(
            NSMakeRect(PAD, cy - ah2 - 12, aw2, ah2))
        self._e_av._ps = PX_L
        root.addSubview_(self._e_av)

        rx = PAD + aw2 + 12
        rw = W - rx - PAD

        self._e_name = _label("Claude Code", 13, TEXT_W)
        self._e_name.setFrame_(NSMakeRect(rx, cy - 28, rw, 16))
        root.addSubview_(self._e_name)

        self._e_detail = _label("--", 10, TEXT_DIM)
        self._e_detail.setFrame_(NSMakeRect(rx, cy - 46, rw, 13))
        root.addSubview_(self._e_detail)

        # Separator 2
        sy = cy - 72
        sep2 = NSView.alloc().initWithFrame_(NSMakeRect(PAD, sy, W - PAD * 2, 1))
        sep2.setWantsLayer_(True)
        sep2.layer().setBackgroundColor_(_cg((0.2, 0.2, 0.24, 0.6)))
        root.addSubview_(sep2)

        self._e_model = _label("Model: --", 9, TEXT_DIM)
        self._e_model.setFrame_(NSMakeRect(PAD, sy - 18, W - PAD * 2, 13))
        root.addSubview_(self._e_model)

        self._e_metrics = _label("CPU --  MEM --", 9, TEXT_DIM)
        self._e_metrics.setFrame_(NSMakeRect(PAD, sy - 34, W - PAD * 2, 13))
        root.addSubview_(self._e_metrics)

        self._e_bar = _Bar.alloc().initWithFrame_(
            NSMakeRect(PAD, sy - 48, W - PAD * 2, 5))
        root.addSubview_(self._e_bar)

        sep3 = NSView.alloc().initWithFrame_(NSMakeRect(PAD, sy - 58, W - PAD * 2, 1))
        sep3.setWantsLayer_(True)
        sep3.layer().setBackgroundColor_(_cg((0.2, 0.2, 0.24, 0.6)))
        root.addSubview_(sep3)

        self._e_extra = _label("", 9, TEXT_DIM)
        self._e_extra.setFrame_(NSMakeRect(PAD, sy - 76, W - PAD * 2, 13))
        root.addSubview_(self._e_extra)

        self._e_hint = _label("", 10, TEXT_W)
        self._e_hint.setFrame_(NSMakeRect(PAD, sy - 76, W - PAD * 2, 13))
        self._e_hint.setAlignment_(NSCenterTextAlignment)
        self._e_hint.setHidden_(True)
        root.addSubview_(self._e_hint)

        # Buttons
        bw, bh = 140, 34
        gap = 12
        bx = (W - bw * 2 - gap) / 2
        by = 16

        self._e_approve = _Btn.alloc().initWithFrame_title_bg_hover_(
            NSMakeRect(bx, by, bw, bh), "ALLOW", APPROVE_BG, APPROVE_HV)
        self._e_approve._cb = lambda: self.on_approve() if self.on_approve else None
        self._e_approve.setHidden_(True)
        root.addSubview_(self._e_approve)

        self._e_deny = _Btn.alloc().initWithFrame_title_bg_hover_(
            NSMakeRect(bx + bw + gap, by, bw, bh), "DENY", DENY_BG, DENY_HV)
        self._e_deny._cb = lambda: self.on_deny() if self.on_deny else None
        self._e_deny.setHidden_(True)
        root.addSubview_(self._e_deny)

        self._expanded_view = root
        self._panel.contentView().addSubview_(root)

    # ── Expand / Collapse ───────────────────────────────────

    def toggle_expand(self):
        if self.expanded:
            self._collapse()
        else:
            self._expand()

    def _expand(self):
        self.expanded = True
        self._collapsed_view.setHidden_(True)
        self._expanded_view.setHidden_(False)
        self._expanded_view.setFrame_(NSMakeRect(0, 0, EXPANDED_W, EXPANDED_H))
        self._position(EXPANDED_W, EXPANDED_H)
        self._update_expanded()

    def _collapse(self):
        self.expanded = False
        self._expanded_view.setHidden_(True)
        self._collapsed_view.setHidden_(False)
        self._collapsed_view.setFrame_(NSMakeRect(0, 0, COLLAPSED_W, COLLAPSED_H))
        self._position(COLLAPSED_W, COLLAPSED_H)

    # ── Animation ───────────────────────────────────────────

    def _get_frame(self):
        assets = TOOL_ASSETS.get(self._tool_key)
        if not assets:
            return None, None, {}
        st = self.current_status.status
        pal = dict(assets.get("palette_offline", assets["palette"])
                   if st == ToolStatus.OFFLINE else assets["palette"])
        acc = STATUS_ACCENT.get(st)
        if acc:
            pal[4] = acc
        frames, overlays = assets["animations"].get(
            st, assets["animations"][ToolStatus.IDLE])
        idx = self._anim_frame % len(frames)
        return frames[idx], overlays[idx] if overlays else None, pal

    def tick_animation(self):
        self._anim_tick += 1
        if self._anim_tick % 2 == 0:
            self._anim_frame = 1 - self._anim_frame
        g, o, pal = self._get_frame()
        if not g:
            return
        # Collapsed avatar
        self._c_av._grid = g
        self._c_av._overlay = o
        self._c_av._pal = pal
        self._c_av.setNeedsDisplay_(True)
        if self.expanded:
            # Expanded top-bar avatar
            self._e_c_av._grid = g
            self._e_c_av._overlay = o
            self._e_c_av._pal = pal
            self._e_c_av.setNeedsDisplay_(True)
            # Expanded large avatar
            self._e_av._grid = g
            self._e_av._overlay = o
            self._e_av._pal = pal
            self._e_av.setNeedsDisplay_(True)

    # ── Status update ───────────────────────────────────────

    def update_status(self, status: StatusInfo):
        self.current_status = status
        st = status.status
        ns_c = STATUS_NS.get(st, _ns(TEXT_DIM))
        cg_c = _cg(STATUS_ACCENT.get(st, (0.5, 0.5, 0.5, 1.0)))
        txt = _STATUS_TEXT.get(st, "???")

        nm = status.tool_name.lower()
        if "claude" in nm:   self._tool_key = "claude"
        elif "gemini" in nm: self._tool_key = "gemini"
        elif "codex" in nm:  self._tool_key = "codex"

        # ── Update collapsed bar (left: avatar/name, right: dot/status) ──
        g, o, pal = self._get_frame()
        if g:
            self._c_av._grid = g
            self._c_av._overlay = o
            self._c_av._pal = pal
            self._c_av.setNeedsDisplay_(True)

        short_name = status.tool_name.replace(" Code", "")
        self._c_name.setStringValue_(short_name)
        self._c_label.setStringValue_(txt)
        self._c_label.setTextColor_(ns_c)
        # Reposition dot+label right-aligned
        self._c_label.sizeToFit()
        lw = self._c_label.frame().size.width
        rpad = CX + 4
        lx = COLLAPSED_W - rpad - lw
        cy = COLLAPSED_H / 2
        self._c_label.setFrame_(NSMakeRect(lx, cy - 7, lw + 2, 14))
        self._c_dot.setFrame_(NSMakeRect(lx - 10, cy - 3, 6, 6))
        self._c_dot.layer().setBackgroundColor_(cg_c)

        # ── Update expanded top bar ──
        if g:
            self._e_c_av._grid = g
            self._e_c_av._overlay = o
            self._e_c_av._pal = pal
            self._e_c_av.setNeedsDisplay_(True)
        self._e_c_name.setStringValue_(short_name)
        self._e_c_label.setStringValue_(txt)
        self._e_c_label.setTextColor_(ns_c)
        self._e_c_label.sizeToFit()
        elw = self._e_c_label.frame().size.width
        rpad = CX + 4
        elx = EXPANDED_W - rpad - elw
        bar_cy = self._e_c_label.frame().origin.y + 7
        self._e_c_label.setFrame_(NSMakeRect(elx, bar_cy - 7, elw + 2, 14))
        self._e_c_dot.setFrame_(NSMakeRect(elx - 10, bar_cy - 3, 6, 6))
        self._e_c_dot.layer().setBackgroundColor_(cg_c)

        # ── Update expanded detail ──
        if self.expanded:
            self._update_expanded()

        # Auto-expand on WAITING_CONFIRM
        if st == ToolStatus.WAITING_CONFIRM:
            self._e_hint.setHidden_(False)
            self._e_hint.setStringValue_("NEEDS YOUR APPROVAL")
            self._e_hint.setTextColor_(ns_c)
            self._e_extra.setHidden_(True)
            self._e_approve.setHidden_(False)
            self._e_deny.setHidden_(False)
            if not self.expanded:
                self._expand()
            self._was_waiting = True
        else:
            self._e_hint.setHidden_(True)
            self._e_extra.setHidden_(False)
            self._e_approve.setHidden_(True)
            self._e_deny.setHidden_(True)
            if self._was_waiting and self.expanded:
                self._collapse()
                self._was_waiting = False

    def _update_expanded(self):
        s = self.current_status
        st = s.status
        ns_c = STATUS_NS.get(st, _ns(TEXT_DIM))
        cg_c = _cg(STATUS_ACCENT.get(st, (0.5, 0.5, 0.5, 1.0)))
        txt = _STATUS_TEXT.get(st, "???")
        bp = {ToolStatus.OFFLINE: 0.0, ToolStatus.IDLE: 1.0,
              ToolStatus.THINKING: 0.65, ToolStatus.TOOL_EXECUTING: 0.6,
              ToolStatus.WAITING_CONFIRM: 1.0, ToolStatus.STREAMING: 0.75,
              ToolStatus.ERROR: 0.15}.get(st, 0.5)

        self._e_name.setStringValue_(s.tool_name)
        self._e_detail.setStringValue_(s.detail or "--")
        self._e_model.setStringValue_(f"Model: {s.model}" if s.model else "Model: --")

        elapsed = s.elapsed_seconds
        if elapsed > 0:
            m, sec = divmod(int(elapsed), 60)
            et = f"{m}m{sec:02d}s" if m else f"{sec}s"
            self._e_metrics.setStringValue_(
                f"CPU {s.cpu_percent:.0f}%  MEM {s.memory_mb:.0f}MB  {et}")
        else:
            self._e_metrics.setStringValue_(
                f"CPU {s.cpu_percent:.0f}%  MEM {s.memory_mb:.0f}MB")
        self._e_bar.setProgress_color_(bp, cg_c)

        pid_str = f"pid {s.pid}" if s.pid else "--"
        self._e_extra.setStringValue_(f"PID: {pid_str}")

        g, o, pal = self._get_frame()
        if g:
            self._e_av._grid = g
            self._e_av._overlay = o
            self._e_av._pal = pal
            self._e_av.setNeedsDisplay_(True)

    # ── Show / Hide ─────────────────────────────────────────

    @property
    def window(self):
        return self._panel

    @property
    def visible(self):
        return self._panel.isVisible()

    def show(self):
        self._position(COLLAPSED_W, COLLAPSED_H)
        self._panel.orderFrontRegardless()

    def hide(self):
        if self.expanded:
            self._collapse()
        self._panel.orderOut_(None)

    def _apply_collapsed(self):
        if self.expanded:
            self._collapse()
