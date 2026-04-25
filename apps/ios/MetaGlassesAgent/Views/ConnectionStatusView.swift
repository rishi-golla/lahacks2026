import SwiftUI

struct ConnectionStatusView: View {
    let status: SessionCoordinator.Status

    var body: some View {
        Text(status.label)
            .font(.caption.weight(.semibold))
            .foregroundStyle(.white)
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(color, in: Capsule())
            .accessibilityLabel("Connection status \(status.label)")
    }

    private var color: Color {
        switch status {
        case .live:
            return .green
        case .connecting, .reconnecting:
            return .orange
        case .idle, .ended:
            return .gray
        case .error:
            return .red
        }
    }
}
