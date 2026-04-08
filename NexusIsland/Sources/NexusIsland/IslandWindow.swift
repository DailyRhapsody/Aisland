import AppKit
import SwiftUI

// MARK: - Layout Constants

enum Layout {
    static let pillWidth: CGFloat = 460
    static let cornerRadius: CGFloat = 16    // bottom corners only
    static let collapsedHeight: CGFloat = 33
    static let expandedHeight: CGFloat = 260
    static let contentInset: CGFloat = 14    // padding from pill edge
}

// MARK: - Island Panel (Non-activating, above menu bar)

class IslandPanel: NSPanel {
    override var canBecomeKey: Bool { false }
    override var canBecomeMain: Bool { false }
}

// MARK: - Island Window Controller

class IslandWindowController {
    let panel: IslandPanel
    private let hostView: NSHostingView<IslandContentView>
    private let viewModel = IslandViewModel()

    init() {
        let screen = NSScreen.main!
        let sw = screen.frame.width
        let w = Layout.pillWidth
        let h = Layout.collapsedHeight
        let x = (sw - w) / 2
        let y = screen.frame.height - h  // top edge at screen top

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
        panel.contentView = hostView
    }

    func show() {
        reposition(height: Layout.collapsedHeight)
        panel.orderFrontRegardless()
    }

    func reposition(height: CGFloat) {
        guard let screen = NSScreen.main else { return }
        let sw = screen.frame.width
        let w = Layout.pillWidth
        let x = (sw - w) / 2
        let y = screen.frame.height - height
        panel.setFrame(NSRect(x: x, y: y, width: w, height: height), display: true, animate: true)
        hostView.frame = NSRect(x: 0, y: 0, width: w, height: height)
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
