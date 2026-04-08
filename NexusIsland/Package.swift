// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "NexusIsland",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "NexusIsland",
            path: "Sources/NexusIsland",
            linkerSettings: [
                .unsafeFlags(["-framework", "AppKit"]),
                .unsafeFlags(["-framework", "QuartzCore"]),
            ]
        )
    ]
)
