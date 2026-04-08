import SwiftUI

/// The pill shape for Nexus Island.
///
/// Matches the MacBook Dynamic Island / vibe-island style:
/// - Top edge: flush with screen top, sharp corners (no rounding)
/// - Bottom: standard inward rounded corners
///
/// ```
///  ┌──────────────────────────┐  ← top: sharp, flush with screen
///  │                          │
///  │        pill body         │
///  │                          │
///  ╰──────────────────────────╯  ← bottom: inward rounded corners
/// ```
struct PillShape: Shape {
    var cornerRadius: CGFloat = 16

    func path(in rect: CGRect) -> Path {
        let w = rect.width
        let h = rect.height
        let r = min(cornerRadius, h / 2, w / 2)

        var p = Path()

        // Top-left (sharp)
        p.move(to: CGPoint(x: 0, y: 0))

        // Top-right (sharp)
        p.addLine(to: CGPoint(x: w, y: 0))

        // Right side down to bottom-right arc
        p.addLine(to: CGPoint(x: w, y: h - r))

        // Bottom-right inward arc
        p.addArc(
            center: CGPoint(x: w - r, y: h - r),
            radius: r,
            startAngle: .degrees(0),
            endAngle: .degrees(90),
            clockwise: false
        )

        // Bottom edge
        p.addLine(to: CGPoint(x: r, y: h))

        // Bottom-left inward arc
        p.addArc(
            center: CGPoint(x: r, y: h - r),
            radius: r,
            startAngle: .degrees(90),
            endAngle: .degrees(180),
            clockwise: false
        )

        // Left side up to top
        p.addLine(to: CGPoint(x: 0, y: 0))

        p.closeSubpath()
        return p
    }
}
