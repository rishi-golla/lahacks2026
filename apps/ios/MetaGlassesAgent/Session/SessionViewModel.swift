import Combine
import Foundation

enum GlassesMode: String, CaseIterable, Identifiable {
    case mock
    case real

    var id: String { rawValue }

    var label: String {
        switch self {
        case .mock:
            return "Mock"
        case .real:
            return "Real Glasses"
        }
    }
}

@MainActor
final class SessionViewModel: ObservableObject {
    @Published var debugText = "hello from iOS"
    @Published var backendURLText: String
    @Published var backendURLMessage = ""
    @Published var glassesMode: GlassesMode
    @Published var glassesModeMessage = ""
    @Published var coordinator: SessionCoordinator

    private static let backendURLOverrideKey = "BackendWebSocketURLOverride"
    private static let glassesModeKey = "GlassesMode"
    private var coordinatorCancellable: AnyCancellable?

    init() {
        let url = Self.backendURL()
        let mode = Self.savedGlassesMode()
        self.backendURLText = url.absoluteString
        self.glassesMode = mode
        self.coordinator = SessionCoordinator(
            glasses: Self.makeGlassesSession(mode: mode),
            glassesSourceLabel: mode.label,
            backendURL: url
        )
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
        rebuildCoordinator(backendURL: url)
        observeCoordinator()
        backendURLMessage = "Backend URL saved"
    }

    func applyGlassesMode() async {
        if coordinator.status == .live || coordinator.status == .connecting {
            await coordinator.stop()
        }

        UserDefaults.standard.set(glassesMode.rawValue, forKey: Self.glassesModeKey)
        rebuildCoordinator(backendURL: Self.backendURL())
        observeCoordinator()
        glassesModeMessage = "Using \(glassesMode.label)"
    }

    private func rebuildCoordinator(backendURL: URL) {
        coordinator = SessionCoordinator(
            glasses: Self.makeGlassesSession(mode: glassesMode),
            glassesSourceLabel: glassesMode.label,
            backendURL: backendURL
        )
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

    private static func savedGlassesMode() -> GlassesMode {
        if let rawValue = UserDefaults.standard.string(forKey: glassesModeKey),
           let mode = GlassesMode(rawValue: rawValue) {
            return mode
        }

        return .mock
    }

    private static func makeGlassesSession(mode: GlassesMode) -> GlassesSession {
        switch mode {
        case .mock:
            return MockGlassesSession()
        case .real:
            return DATGlassesSession()
        }
    }
}
