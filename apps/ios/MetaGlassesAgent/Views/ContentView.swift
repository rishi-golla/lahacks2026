import SwiftUI

struct ContentView: View {
    @StateObject private var viewModel = SessionViewModel()
    @StateObject private var wearablesViewModel = WearablesViewModel()

    var body: some View {
        NavigationStack {
            VStack(spacing: 16) {
                HStack {
                    ConnectionStatusView(status: viewModel.coordinator.status)
                    Spacer()
                    Button(viewModel.coordinator.status == .live ? "Stop" : "Start") {
                        Task {
                            if viewModel.coordinator.status == .live {
                                await viewModel.coordinator.stop()
                            } else {
                                await viewModel.coordinator.start()
                            }
                        }
                    }
                    .buttonStyle(.borderedProminent)
                }

                Text(viewModel.coordinator.latestDebugLine)
                    .font(.caption.monospaced())
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .leading)

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

                HStack {
                    Button("Capture Photo") {
                        Task {
                            await viewModel.coordinator.captureDebugPhoto()
                        }
                    }
                    .buttonStyle(.bordered)

                    Button("Barge In") {
                        Task {
                            await viewModel.coordinator.bargeIn()
                        }
                    }
                    .buttonStyle(.bordered)

                    Button(viewModel.coordinator.isLoopbackRunning ? "Recording..." : "Loopback Test") {
                        Task {
                            await viewModel.coordinator.runLoopbackTest()
                        }
                    }
                    .buttonStyle(.bordered)
                    .disabled(viewModel.coordinator.isLoopbackRunning)

                    Spacer()
                }

                DATStatusView(viewModel: wearablesViewModel)

                DebugView(coordinator: viewModel.coordinator)
            }
            .padding()
            .navigationTitle("Glasses Agent")
            .onOpenURL { url in
                Task {
                    await wearablesViewModel.handleCallbackURL(url)
                }
            }
        }
    }
}
