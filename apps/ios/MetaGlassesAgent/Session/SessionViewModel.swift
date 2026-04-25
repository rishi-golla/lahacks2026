import Foundation

@MainActor
final class SessionViewModel: ObservableObject {
    @Published var debugText = "hello from iOS"
    @Published var coordinator: SessionCoordinator

    init() {
        let url = Self.backendURL()
        self.coordinator = SessionCoordinator(glasses: MockGlassesSession(), backendURL: url)
    }

    static func backendURL() -> URL {
        if let value = Bundle.main.object(forInfoDictionaryKey: "BackendWebSocketURL") as? String,
           let url = URL(string: value) {
            return url
        }

        return URL(string: "ws://localhost:8000/session")!
    }
}
