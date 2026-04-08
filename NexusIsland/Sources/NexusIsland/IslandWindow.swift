import AppKit
import SwiftUI

// MARK: - Layout Constants

enum Layout {
    static let pillWidth: CGFloat = 460
    static let collapsedHeight: CGFloat = 33
    static let expandedHeight: CGFloat = 260
    static let collapsedRadius: CGFloat = 17   // half of collapsed height ≈ full pill ends
    static let expandedRadius: CGFloat = 44    // Apple Dynamic Island expanded radius
    static let contentInset: CGFloat = 14
}

// MARK: - Island Panel (Non-activating, above menu bar)

class IslandPanel: NSPanel {
    override var canBecomeKey: Bool { false }
    override var canBecomeMain: Bool { false }
}

// Transparent overlay that catches mouse clicks without blocking hover
class ClickOverlay: NSView {
    var onClick: (() -> Void)?

    override func mouseUp(with event: NSEvent) {
        onClick?()
    }

    override func acceptsFirstMouse(for event: NSEvent?) -> Bool {
        return true
    }
}

// MARK: - Island Window Controller

class IslandWindowController {
    let panel: IslandPanel
    private let hostView: NSHostingView<IslandContentView>
    let overlay: ClickOverlay
    private let viewModel = IslandViewModel()

    init() {
        let screen = NSScreen.main!
        let sw = screen.frame.width
        let w = Layout.pillWidth
        let h = Layout.expandedHeight  // fixed to max size
        let x = (sw - w) / 2
        let y = screen.frame.height - h

        panel = IslandPanel(
            contentRect: NSRect(x: x, y: y, width: w, height: h),
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )

        panel.level = NSWindow.Level(rawValue: Int(CGWindowLevelForKey(.statusWindow)))
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = false
        panel.isMovableByWindowBackground = false
        panel.ignoresMouseEvents = false
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.hidesOnDeactivate = false

        let contentView = IslandContentView(viewModel: viewModel)
        hostView = NSHostingView(rootView: contentView)
        hostView.frame = NSRect(x: 0, y: 0, width: w, height: h)

        let container = NSView(frame: NSRect(x: 0, y: 0, width: w, height: h))
        container.addSubview(hostView)

        overlay = ClickOverlay(frame: NSRect(x: 0, y: 0, width: w, height: h))
        overlay.autoresizingMask = [.width, .height]
        container.addSubview(overlay)

        panel.contentView = container
    }

    var isVisible: Bool {
        panel.isVisible
    }

    func show() {
        panel.orderFrontRegardless()
    }

    func hide() {
        viewModel.expanded = false
        panel.orderOut(nil)
    }

    var vm: IslandViewModel { viewModel }
}

// MARK: - View Model

class IslandViewModel: ObservableObject {
    @Published var expanded = false
    @Published var agentName = "Claude Code"
    @Published var statusText = "READY"
    @Published var statusColor: Color = .green
    @Published var detail = "Monitoring..."
    @Published var model = "--"
    @Published var cpuPercent: Double = 0
    @Published var memoryMB: Double = 0
    @Published var pid: Int32 = 0
    @Published var showButtons = false
}
