import SwiftUI

struct ContentView: View {
    @StateObject private var viewModel = SessionViewModel()
    @StateObject private var wearablesViewModel = WearablesViewModel()
    @State private var isDebugExpanded = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 18) {
                    assistantHero
                    visualContextCard
                    transcriptCard
                    debugDisclosure
                }
                .padding()
            }
            .navigationTitle("Meta Glasses Agent")
            .onOpenURL { url in
                Task {
                    await wearablesViewModel.handleCallbackURL(url)
                }
            }
        }
    }

    private var assistantHero: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("AI assistant")
                        .font(.title2.weight(.semibold))
                    Text("Voice + visual context from \(viewModel.glassesMode.label)")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }

                Spacer()

                ConnectionStatusView(status: viewModel.coordinator.status)
            }

            Button {
                Task {
                    if viewModel.coordinator.status == .live {
                        await viewModel.coordinator.stop()
                    } else {
                        await viewModel.coordinator.start()
                    }
                }
            } label: {
                Label(primaryButtonTitle, systemImage: primaryButtonIcon)
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)

            Text(statusLine)
                .font(.caption)
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.secondary.opacity(0.10), in: RoundedRectangle(cornerRadius: 18))
    }

    private var visualContextCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("What Gemini sees")
                    .font(.headline)
                Spacer()
                VStack(alignment: .trailing, spacing: 2) {
                    Text(viewModel.glassesMode.label)
                        .font(.caption.weight(.medium))
                    Text(viewModel.coordinator.visualContextSourceLabel)
                        .font(.caption2)
                }
                .foregroundStyle(.secondary)
            }

            if let image = viewModel.coordinator.lastPhoto {
                Image(uiImage: image)
                    .resizable()
                    .scaledToFill()
                    .frame(maxWidth: .infinity, minHeight: 180, maxHeight: 220)
                    .clipShape(RoundedRectangle(cornerRadius: 14))
                    .id(viewModel.coordinator.visualContextFrameCount)
            } else {
                RoundedRectangle(cornerRadius: 14)
                    .fill(.secondary.opacity(0.14))
                    .frame(height: 180)
                    .overlay {
                        VStack(spacing: 8) {
                            Image(systemName: "camera.viewfinder")
                                .font(.largeTitle)
                            Text("Visual context will appear here")
                                .font(.subheadline)
                        }
                        .foregroundStyle(.secondary)
                    }
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.background, in: RoundedRectangle(cornerRadius: 18))
        .overlay {
            RoundedRectangle(cornerRadius: 18)
                .stroke(.secondary.opacity(0.15))
        }
    }

    private var transcriptCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Conversation")
                .font(.headline)

            transcriptRow(
                title: "You",
                text: viewModel.coordinator.lastUserTranscript,
                placeholder: "Ask a question out loud"
            )
            transcriptRow(
                title: "Gemini",
                text: viewModel.coordinator.lastModelTranscript,
                placeholder: "Assistant response will appear here"
            )
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.background, in: RoundedRectangle(cornerRadius: 18))
        .overlay {
            RoundedRectangle(cornerRadius: 18)
                .stroke(.secondary.opacity(0.15))
        }
    }

    private func transcriptRow(title: String, text: String, placeholder: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
            Text(text.isEmpty ? placeholder : text)
                .foregroundStyle(text.isEmpty ? .secondary : .primary)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private var debugDisclosure: some View {
        DisclosureGroup("Debug controls", isExpanded: $isDebugExpanded) {
            VStack(alignment: .leading, spacing: 16) {
                glassesModePicker
                debugTextSender
                backendURLControls
                debugActionButtons
                DATStatusView(viewModel: wearablesViewModel)
                DebugView(coordinator: viewModel.coordinator)
            }
            .padding(.top, 12)
        }
        .padding(16)
        .background(.secondary.opacity(0.08), in: RoundedRectangle(cornerRadius: 18))
    }

    private var glassesModePicker: some View {
        VStack(alignment: .leading, spacing: 6) {
            Picker("Glasses", selection: $viewModel.glassesMode) {
                ForEach(GlassesMode.allCases) { mode in
                    Text(mode.label).tag(mode)
                }
            }
            .pickerStyle(.segmented)
            .onChange(of: viewModel.glassesMode) { _ in
                Task {
                    await viewModel.applyGlassesMode()
                }
            }

            if !viewModel.glassesModeMessage.isEmpty {
                Text(viewModel.glassesModeMessage)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }

    private var debugTextSender: some View {
        HStack {
            TextField("Debug text", text: $viewModel.debugText)
                .textFieldStyle(.roundedBorder)

            Button("Send") {
                let text = viewModel.debugText
                Task {
                    await viewModel.coordinator.sendDebugText(text)
                }
            }
            .buttonStyle(.bordered)
        }
    }

    private var backendURLControls: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                TextField("Backend WebSocket URL", text: $viewModel.backendURLText)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .keyboardType(.URL)
                    .textFieldStyle(.roundedBorder)

                Button("Apply") {
                    Task {
                        await viewModel.applyBackendURL()
                    }
                }
                .buttonStyle(.bordered)
            }

            if !viewModel.backendURLMessage.isEmpty {
                Text(viewModel.backendURLMessage)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }

    private var debugActionButtons: some View {
        ViewThatFits {
            HStack {
                actionButtons
            }
            VStack(alignment: .leading) {
                actionButtons
            }
        }
    }

    private var actionButtons: some View {
        Group {
            Button("Capture Photo") {
                Task {
                    await viewModel.coordinator.captureDebugPhoto()
                }
            }

            Button("Barge In") {
                Task {
                    await viewModel.coordinator.bargeIn()
                }
            }

            Button(viewModel.coordinator.isLoopbackRunning ? "Recording..." : "Loopback Test") {
                Task {
                    await viewModel.coordinator.runLoopbackTest()
                }
            }
            .disabled(viewModel.coordinator.isLoopbackRunning)
        }
        .buttonStyle(.bordered)
    }

    private var primaryButtonTitle: String {
        switch viewModel.coordinator.status {
        case .live:
            return "Stop Assistant"
        case .connecting, .reconnecting:
            return "Connecting..."
        default:
            return "Start Assistant"
        }
    }

    private var primaryButtonIcon: String {
        switch viewModel.coordinator.status {
        case .live:
            return "stop.fill"
        case .connecting, .reconnecting:
            return "antenna.radiowaves.left.and.right"
        default:
            return "play.fill"
        }
    }

    private var statusLine: String {
        switch viewModel.coordinator.status {
        case .live:
            if viewModel.coordinator.isMicStreaming && viewModel.coordinator.isVisualContextStreaming {
                return "Listening now. Visual context: \(viewModel.coordinator.visualContextSourceLabel)."
            }
            if viewModel.coordinator.isMicStreaming {
                return "Listening now. Waiting for visual context."
            }
            if viewModel.coordinator.isVisualContextStreaming {
                return "Visual context is streaming. Waiting for mic."
            }
            return "Connected. Starting assistant inputs..."
        case .connecting, .reconnecting:
            return viewModel.coordinator.latestDebugLine
        case .error(let message):
            return message
        default:
            return viewModel.coordinator.latestDebugLine
        }
    }
}
