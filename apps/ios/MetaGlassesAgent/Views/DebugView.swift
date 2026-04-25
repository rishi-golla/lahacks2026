import SwiftUI

struct DebugView: View {
    @ObservedObject var coordinator: SessionCoordinator

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                if let image = coordinator.lastPhoto {
                    Image(uiImage: image)
                        .resizable()
                        .scaledToFit()
                        .frame(maxHeight: 180)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                } else {
                    RoundedRectangle(cornerRadius: 12)
                        .fill(.secondary.opacity(0.15))
                        .frame(height: 120)
                        .overlay {
                            Text("No photo yet")
                                .foregroundStyle(.secondary)
                        }
                }

                transcriptSection
                toolEventsSection
                debugLogSection
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private var transcriptSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Transcripts")
                .font(.headline)

            Text(coordinator.lastUserTranscript.isEmpty ? "User transcript pending" : coordinator.lastUserTranscript)
                .italic()
                .foregroundStyle(.secondary)

            Text(coordinator.lastModelTranscript.isEmpty ? "Model transcript pending" : coordinator.lastModelTranscript)
                .font(.body.weight(.medium))
        }
    }

    private var toolEventsSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Tool Events")
                .font(.headline)

            if coordinator.toolEventsLog.isEmpty {
                Text("No tool events yet")
                    .foregroundStyle(.secondary)
            } else {
                ForEach(coordinator.toolEventsLog.prefix(10)) { event in
                    VStack(alignment: .leading, spacing: 4) {
                        Text("\(event.name.rawValue) · \(event.phase.rawValue)")
                            .font(.subheadline.weight(.semibold))
                        if let summary = event.resultSummary {
                            Text(summary)
                                .font(.caption)
                        }
                        if let error = event.error {
                            Text(error)
                                .font(.caption)
                                .foregroundStyle(.red)
                        }
                    }
                    .padding(10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(.secondary.opacity(0.12), in: RoundedRectangle(cornerRadius: 10))
                }
            }
        }
    }

    private var debugLogSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Debug Log")
                .font(.headline)

            if coordinator.debugLog.isEmpty {
                Text("No log lines yet")
                    .foregroundStyle(.secondary)
            } else {
                ForEach(Array(coordinator.debugLog.enumerated()), id: \.offset) { _, line in
                    Text(line)
                        .font(.caption.monospaced())
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
        }
    }
}
