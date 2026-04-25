import SwiftUI

struct DATStatusView: View {
    @ObservedObject var viewModel: WearablesViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Meta DAT")
                    .font(.headline)
                Spacer()
                if viewModel.isWorking {
                    ProgressView()
                        .controlSize(.small)
                }
            }

            Grid(alignment: .leading, horizontalSpacing: 12, verticalSpacing: 6) {
                GridRow {
                    Text("Registration")
                        .foregroundStyle(.secondary)
                    Text(viewModel.registrationStateLabel)
                }
                GridRow {
                    Text("Devices")
                        .foregroundStyle(.secondary)
                    Text("\(viewModel.deviceCount)")
                }
                GridRow {
                    Text("Camera")
                        .foregroundStyle(.secondary)
                    Text(viewModel.cameraPermissionLabel)
                }
            }
            .font(.caption)

            Text(viewModel.lastEvent)
                .font(.caption)
                .foregroundStyle(.secondary)

            if let error = viewModel.lastError {
                Text(error)
                    .font(.caption)
                    .foregroundStyle(.red)
            }

            ViewThatFits {
                HStack {
                    buttons
                }
                VStack(alignment: .leading) {
                    buttons
                }
            }
        }
        .padding(12)
        .background(.secondary.opacity(0.10), in: RoundedRectangle(cornerRadius: 12))
    }

    private var buttons: some View {
        Group {
            Button("Register") {
                Task {
                    await viewModel.startRegistration()
                }
            }
            Button("Unregister") {
                Task {
                    await viewModel.startUnregistration()
                }
            }
            Button("Check Camera") {
                Task {
                    await viewModel.checkCameraPermission()
                }
            }
            Button("Request Camera") {
                Task {
                    await viewModel.requestCameraPermission()
                }
            }
        }
        .buttonStyle(.bordered)
        .disabled(viewModel.isWorking)
    }
}
