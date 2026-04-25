import SwiftUI

struct ContentView: View {
    @StateObject private var viewModel = SessionViewModel()

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

                    Spacer()
                }

                DebugView(coordinator: viewModel.coordinator)
            }
            .padding()
            .navigationTitle("Glasses Agent")
        }
    }
}
