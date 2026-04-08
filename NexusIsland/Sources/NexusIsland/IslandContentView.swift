import SwiftUI

// MARK: - Spring animation matching Apple Dynamic Island

private let islandSpring = Animation.spring(response: 0.4, dampingFraction: 0.75, blendDuration: 0)

// MARK: - Main Island Content View

struct IslandContentView: View {
    @ObservedObject var viewModel: IslandViewModel

    private var currentHeight: CGFloat {
        viewModel.expanded ? Layout.expandedHeight : Layout.collapsedHeight
    }

    private var currentRadius: CGFloat {
        viewModel.expanded ? Layout.expandedRadius : Layout.collapsedRadius
    }

    var body: some View {
        VStack(spacing: 0) {
            // The pill — pinned to top of the fixed-size window
            ZStack(alignment: .top) {
                // Background pill
                RoundedRectangle(cornerRadius: currentRadius, style: .continuous)
                    .fill(Color.black)
                    .shadow(color: .black.opacity(0.5), radius: 10, y: 5)

                // Content
                if viewModel.expanded {
                    ExpandedView(viewModel: viewModel)
                        .transition(.opacity)
                } else {
                    CollapsedView(viewModel: viewModel)
                        .transition(.opacity)
                }
            }
            .frame(width: Layout.pillWidth, height: currentHeight)
            .clipShape(RoundedRectangle(cornerRadius: currentRadius, style: .continuous))
            .animation(islandSpring, value: viewModel.expanded)

            Spacer(minLength: 0)
        }
        .frame(width: Layout.pillWidth, height: Layout.expandedHeight, alignment: .top)
        .allowsHitTesting(false)
    }
}

// MARK: - Collapsed View

struct CollapsedView: View {
    @ObservedObject var viewModel: IslandViewModel

    var body: some View {
        HStack {
            HStack(spacing: 4) {
                Text("🤖")
                    .font(.system(size: 10))
                Text(viewModel.agentName.replacingOccurrences(of: " Code", with: ""))
                    .font(.system(size: 10, weight: .medium, design: .monospaced))
                    .foregroundColor(.white.opacity(0.6))
            }
            .padding(.leading, Layout.contentInset + 6)

            Spacer()

            HStack(spacing: 5) {
                Circle()
                    .fill(viewModel.statusColor)
                    .frame(width: 6, height: 6)
                Text(viewModel.statusText)
                    .font(.system(size: 11, weight: .semibold, design: .monospaced))
                    .foregroundColor(viewModel.statusColor)
            }
            .padding(.trailing, Layout.contentInset + 6)
        }
        .frame(height: Layout.collapsedHeight)
    }
}

// MARK: - Expanded View

struct ExpandedView: View {
    @ObservedObject var viewModel: IslandViewModel

    private let pad = Layout.contentInset + 8

    var body: some View {
        VStack(spacing: 0) {
            // Top bar
            HStack {
                HStack(spacing: 4) {
                    Text("🤖")
                        .font(.system(size: 10))
                    Text(viewModel.agentName.replacingOccurrences(of: " Code", with: ""))
                        .font(.system(size: 10, weight: .medium, design: .monospaced))
                        .foregroundColor(.white.opacity(0.6))
                }
                .padding(.leading, pad)

                Spacer()

                HStack(spacing: 5) {
                    Circle()
                        .fill(viewModel.statusColor)
                        .frame(width: 6, height: 6)
                    Text(viewModel.statusText)
                        .font(.system(size: 11, weight: .semibold, design: .monospaced))
                        .foregroundColor(viewModel.statusColor)
                }
                .padding(.trailing, pad)
            }
            .frame(height: Layout.collapsedHeight)

            Divider().background(Color.white.opacity(0.15))

            // Detail area
            VStack(alignment: .leading, spacing: 8) {
                Text(viewModel.agentName)
                    .font(.system(size: 14, weight: .semibold, design: .monospaced))
                    .foregroundColor(.white)

                Text(viewModel.detail)
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundColor(.white.opacity(0.5))

                Divider().background(Color.white.opacity(0.15))

                Text("Model: \(viewModel.model)")
                    .font(.system(size: 9, design: .monospaced))
                    .foregroundColor(.white.opacity(0.5))

                Text("CPU \(Int(viewModel.cpuPercent))%  MEM \(Int(viewModel.memoryMB))MB  PID \(viewModel.pid)")
                    .font(.system(size: 9, design: .monospaced))
                    .foregroundColor(.white.opacity(0.5))

                // Progress bar
                GeometryReader { geo in
                    ZStack(alignment: .leading) {
                        RoundedRectangle(cornerRadius: 2)
                            .fill(Color.white.opacity(0.1))
                        RoundedRectangle(cornerRadius: 2)
                            .fill(viewModel.statusColor)
                            .frame(width: geo.size.width * 0.6)
                    }
                }
                .frame(height: 4)
            }
            .padding(.horizontal, pad)
            .padding(.top, 10)

            Spacer()

            // ALLOW / DENY buttons
            if viewModel.showButtons {
                HStack(spacing: 12) {
                    Button(action: {}) {
                        Text("ALLOW")
                            .font(.system(size: 11, weight: .semibold, design: .monospaced))
                            .foregroundColor(.white)
                            .frame(maxWidth: .infinity)
                            .frame(height: 34)
                            .background(Color.green.opacity(0.35))
                            .cornerRadius(8)
                    }
                    .buttonStyle(.plain)

                    Button(action: {}) {
                        Text("DENY")
                            .font(.system(size: 11, weight: .semibold, design: .monospaced))
                            .foregroundColor(.white)
                            .frame(maxWidth: .infinity)
                            .frame(height: 34)
                            .background(Color.red.opacity(0.35))
                            .cornerRadius(8)
                    }
                    .buttonStyle(.plain)
                }
                .padding(.horizontal, pad)
                .padding(.bottom, 16)
            }
        }
    }
}
