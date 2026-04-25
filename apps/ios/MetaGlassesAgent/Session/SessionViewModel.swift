import Combine
import Foundation

@MainActor
final class SessionViewModel: ObservableObject {
    @Published var debugText = "hello from iOS"
    @Published var backendURLText: String
    @Published var backendURLMessage = ""
    @Published var coordinator: SessionCoordinator

    private static let backendURLOverrideKey = "BackendWebSocketURLOverride"
    private var coordinatorCancellable: AnyCancellable?

    init() {
        let url = Self.backendURL()
        self.backendURLText = url.absoluteString
        self.coordinator = SessionCoordinator(glasses: MockGlassesSession(), backendURL: url)
        observeCoordinator()
    }

    func applyBackendURL() async {
        let trimmed = backendURLText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let url = URL(string: trimmed),
              let scheme = url.scheme?.lowercased(),
              ["ws", "wss"].contains(scheme),
              url.host != nil else {
            backendURLMessage = "Use a valid ws:// or wss:// URL"
            return
        }

        if coordinator.status == .live || coordinator.status == .connecting {
            await coordinator.stop()
        }

        UserDefaults.standard.set(trimmed, forKey: Self.backendURLOverrideKey)
        coordinator = SessionCoordinator(glasses: MockGlassesSession(), backendURL: url)
        observeCoordinator()
        backendURLMessage = "Backend URL saved"
    }

    private func observeCoordinator() {
        coordinatorCancellable = coordinator.objectWillChange.sink { [weak self] _ in
            Task { @MainActor in
                self?.objectWillChange.send()
            }
        }
    }

    static func backendURL() -> URL {
        if let value = UserDefaults.standard.string(forKey: backendURLOverrideKey),
           let url = URL(string: value) {
            return url
        }

        if let value = Bundle.main.object(forInfoDictionaryKey: "BackendWebSocketURL") as? String,
           let url = URL(string: value) {
            return url
        }

        return URL(string: "ws://localhost:8000/session")!
    }
}
