import AppKit
import SwiftUI

// MARK: - App Delegate

class AppDelegate: NSObject, NSApplicationDelegate {
    var island: IslandWindowController!
    var monitor: ProcessMonitor!
    var pollTimer: Timer?
    var clickMonitor: Any?
    var tickCount = 0

    func applicationDidFinishLaunching(_ notification: Notification) {
        monitor = ProcessMonitor()
        island = IslandWindowController()
        // Don't show immediately — wait until an agent is detected

        // Start polling for agents
        pollTimer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { [weak self] _ in
            self?.tick()
        }
        pollTimer?.fire()

        // Overlay click: toggle expand/collapse
        island.overlay.onClick = { [weak self] in
            self?.toggleExpand()
        }

        // Global click: collapse when clicking outside
        clickMonitor = NSEvent.addGlobalMonitorForEvents(matching: .leftMouseUp) { [weak self] event in
            guard let self = self, self.island.vm.expanded else { return }
            DispatchQueue.main.async {
                self.island.vm.expanded = false
            }
        }

        print("\u{1B}[1;36m")
        print("  ╔════════════════════════════════════════╗")
        print("  ║  Aisland running                        ║")
        print("  ║  Ctrl+C to stop                        ║")
        print("  ╚════════════════════════════════════════╝")
        print("\u{1B}[0m")
    }

    func tick() {
        tickCount += 1
        DispatchQueue.global(qos: .utility).async { [weak self] in
            guard let self = self else { return }
            let agents = self.monitor.detectAgents()
            // Only scan for model every 5 ticks (~10s) to avoid heavy filesystem IO
            let model = (self.tickCount % 5 == 0) ? self.monitor.detectModel() : nil

            DispatchQueue.main.async {
                let vm = self.island.vm

                if let agent = agents.first {
                    vm.agentName = agent.name
                    vm.cpuPercent = agent.cpu
                    vm.memoryMB = agent.memory
                    vm.pid = agent.pid

                    if agent.cpu > 15 {
                        vm.statusText = "THINKING..."
                        vm.statusColor = .orange
                    } else {
                        vm.statusText = "READY"
                        vm.statusColor = .green
                    }

                    if let model = model {
                        vm.model = model
                    }

                    // Show island when agent is active
                    if !self.island.isVisible {
                        self.island.show()
                    }
                } else {
                    // Hide island when no agent is running
                    if self.island.isVisible {
                        self.island.hide()
                    }
                    vm.statusText = "SLEEPING"
                    vm.statusColor = Color(white: 0.5)
                    vm.agentName = "Claude Code"
                }
            }
        }
    }

    func toggleExpand() {
        island.vm.expanded.toggle()
    }
}

// MARK: - Entry Point

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.accessory)  // no dock icon
app.run()
