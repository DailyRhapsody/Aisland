import AppKit
import SwiftUI

// MARK: - App Delegate

class AppDelegate: NSObject, NSApplicationDelegate {
    var island: IslandWindowController!
    var monitor: ProcessMonitor!
    var pollTimer: Timer?
    var clickMonitor: Any?

    func applicationDidFinishLaunching(_ notification: Notification) {
        monitor = ProcessMonitor()
        island = IslandWindowController()
        island.show()

        // Start polling for agents
        pollTimer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { [weak self] _ in
            self?.tick()
        }
        pollTimer?.fire()

        // Global click monitor: click outside → collapse
        clickMonitor = NSEvent.addGlobalMonitorForEvents(matching: .leftMouseUp) { [weak self] event in
            self?.handleGlobalClick(event)
        }

        // Local click monitor: click inside → toggle
        NSEvent.addLocalMonitorForEvents(matching: .leftMouseUp) { [weak self] event in
            self?.handleLocalClick(event)
            return event
        }

        print("\u{1B}[1;36m")
        print("  ╔════════════════════════════════════════╗")
        print("  ║  Nexus Island running (Swift)          ║")
        print("  ║  Ctrl+C to stop                        ║")
        print("  ╚════════════════════════════════════════╝")
        print("\u{1B}[0m")
    }

    func tick() {
        let agents = monitor.detectAgents()
        let vm = island.vm

        if let agent = agents.first {
            DispatchQueue.main.async {
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

                // Try to detect model
                if let model = self.monitor.detectModel() {
                    vm.model = model
                }
            }
        } else {
            DispatchQueue.main.async {
                vm.statusText = "SLEEPING"
                vm.statusColor = Color(white: 0.5)
                vm.agentName = "Claude Code"
            }
        }
    }

    func handleGlobalClick(_ event: NSEvent) {
        guard island.vm.expanded else { return }
        let pt = NSEvent.mouseLocation
        let f = island.panel.frame
        let inside = f.contains(pt)
        if !inside {
            DispatchQueue.main.async {
                self.island.vm.expanded = false
                self.island.reposition(height: Layout.collapsedHeight)
            }
        }
    }

    func handleLocalClick(_ event: NSEvent) {
        let pt = NSEvent.mouseLocation
        let f = island.panel.frame
        guard f.contains(pt) else { return }

        DispatchQueue.main.async {
            let vm = self.island.vm
            vm.expanded.toggle()
            let h = vm.expanded ? Layout.expandedHeight : Layout.collapsedHeight
            self.island.reposition(height: h)
        }
    }
}

// MARK: - Entry Point

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.accessory)  // no dock icon
app.run()
