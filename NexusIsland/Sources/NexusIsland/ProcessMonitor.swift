import Foundation

// MARK: - Agent Info

struct AgentInfo {
    let name: String
    let pid: Int32
    let cpu: Double
    let memory: Double  // MB
}

// MARK: - Process Monitor

class ProcessMonitor {
    /// Scan running processes for known AI CLI tools.
    func detectAgents() -> [AgentInfo] {
        var agents: [AgentInfo] = []

        let pipe = Pipe()
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: "/bin/ps")
        proc.arguments = ["-eo", "pid,pcpu,rss,comm"]
        proc.standardOutput = pipe
        proc.standardError = FileHandle.nullDevice

        do {
            try proc.run()
            proc.waitUntilExit()
        } catch {
            return agents
        }

        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        guard let output = String(data: data, encoding: .utf8) else { return agents }

        let patterns: [(keyword: String, name: String)] = [
            ("claude", "Claude Code"),
            ("gemini", "Gemini CLI"),
            ("codex", "Codex CLI"),
        ]

        for line in output.components(separatedBy: "\n") {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            let parts = trimmed.split(separator: " ", maxSplits: 3,
                                       omittingEmptySubsequences: true)
            guard parts.count >= 4,
                  let pid = Int32(parts[0]),
                  let cpu = Double(parts[1]),
                  let rssKB = Double(parts[2]) else { continue }

            let comm = String(parts[3]).lowercased()
            for pat in patterns {
                if comm.contains(pat.keyword) {
                    agents.append(AgentInfo(
                        name: pat.name,
                        pid: pid,
                        cpu: cpu,
                        memory: rssKB / 1024.0
                    ))
                    break
                }
            }
        }

        return agents
    }

    /// Read model from Claude session JSONL files.
    func detectModel() -> String? {
        let home = FileManager.default.homeDirectoryForCurrentUser
        let projectsDir = home.appendingPathComponent(".claude/projects")

        guard let enumerator = FileManager.default.enumerator(
            at: projectsDir,
            includingPropertiesForKeys: [.contentModificationDateKey],
            options: [.skipsHiddenFiles]
        ) else { return nil }

        var newest: (url: URL, date: Date)?
        while let url = enumerator.nextObject() as? URL {
            guard url.pathExtension == "jsonl" else { continue }
            if let values = try? url.resourceValues(forKeys: [.contentModificationDateKey]),
               let date = values.contentModificationDate {
                if newest == nil || date > newest!.date {
                    newest = (url, date)
                }
            }
        }

        guard let file = newest?.url,
              let handle = try? FileHandle(forReadingFrom: file) else { return nil }

        // Read last 8KB
        let size = handle.seekToEndOfFile()
        let readStart = size > 8192 ? size - 8192 : 0
        handle.seek(toFileOffset: readStart)
        let data = handle.readDataToEndOfFile()
        handle.closeFile()

        guard let text = String(data: data, encoding: .utf8) else { return nil }

        // Parse lines in reverse, find "model" field
        let lines = text.components(separatedBy: "\n").reversed()
        for line in lines {
            guard let jsonData = line.data(using: .utf8),
                  let obj = try? JSONSerialization.jsonObject(with: jsonData) as? [String: Any],
                  let model = obj["model"] as? String,
                  !model.isEmpty else { continue }
            return model
        }
        return nil
    }
}
