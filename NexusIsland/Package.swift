// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "Aisland",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "Aisland",
            path: "Sources/NexusIsland",
            linkerSettings: [
                .unsafeFlags(["-framework", "AppKit"]),
                .unsafeFlags(["-framework", "QuartzCore"]),
            ]
        )
    ]
)
