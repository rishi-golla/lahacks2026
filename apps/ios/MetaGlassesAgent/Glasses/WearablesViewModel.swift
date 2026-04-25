import Foundation
import MWDATCore

@MainActor
final class WearablesViewModel: ObservableObject {
    @Published private(set) var registrationStateLabel: String
    @Published private(set) var deviceCount: Int
    @Published private(set) var cameraPermissionLabel = "Unknown"
    @Published private(set) var lastError: String?
    @Published private(set) var lastEvent = "DAT idle"
    @Published private(set) var isWorking = false

    private let wearables: WearablesInterface
    private var registrationTask: Task<Void, Never>?
    private var devicesTask: Task<Void, Never>?

    init(wearables: WearablesInterface = Wearables.shared) {
        self.wearables = wearables
        self.registrationStateLabel = String(describing: wearables.registrationState)
        self.deviceCount = wearables.devices.count

        registrationTask = Task { [weak self] in
            guard let self else {
                return
            }

            for await state in wearables.registrationStateStream() {
                self.registrationStateLabel = String(describing: state)
                self.lastEvent = "Registration state: \(self.registrationStateLabel)"
            }
        }

        devicesTask = Task { [weak self] in
            guard let self else {
                return
            }

            for await devices in wearables.devicesStream() {
                self.deviceCount = devices.count
                self.lastEvent = "Detected \(devices.count) wearable device(s)"
            }
        }
    }

    deinit {
        registrationTask?.cancel()
        devicesTask?.cancel()
    }

    func startRegistration() async {
        await run("Starting Meta AI registration") {
            do {
                try await wearables.startRegistration()
                lastEvent = "Registration flow opened in Meta AI"
            } catch let error as RegistrationError {
                fail(error.description)
            } catch {
                fail(error.localizedDescription)
            }
        }
    }

    func startUnregistration() async {
        await run("Starting Meta AI unregistration") {
            do {
                try await wearables.startUnregistration()
                lastEvent = "Unregistration flow opened in Meta AI"
            } catch let error as UnregistrationError {
                fail(error.description)
            } catch {
                fail(error.localizedDescription)
            }
        }
    }

    func checkCameraPermission() async {
        await run("Checking camera permission") {
            do {
                let status = try await wearables.checkPermissionStatus(.camera)
                cameraPermissionLabel = String(describing: status)
                lastEvent = "Camera permission: \(cameraPermissionLabel)"
            } catch {
                fail(error.localizedDescription)
            }
        }
    }

    func requestCameraPermission() async {
        await run("Requesting camera permission") {
            do {
                let status = try await wearables.requestPermission(.camera)
                cameraPermissionLabel = String(describing: status)
                lastEvent = "Camera permission: \(cameraPermissionLabel)"
            } catch {
                fail(error.localizedDescription)
            }
        }
    }

    func handleCallbackURL(_ url: URL) async {
        guard Self.isDATCallback(url) else {
            return
        }

        await run("Handling Meta AI callback") {
            do {
                _ = try await wearables.handleUrl(url)
                lastEvent = "Handled Meta AI callback"
            } catch let error as RegistrationError {
                fail(error.description)
            } catch {
                fail(error.localizedDescription)
            }
        }
    }

    func clearError() {
        lastError = nil
    }

    static func isDATCallback(_ url: URL) -> Bool {
        guard let components = URLComponents(url: url, resolvingAgainstBaseURL: false) else {
            return false
        }
        return components.queryItems?.contains { $0.name == "metaWearablesAction" } == true
    }

    private func run(_ event: String, operation: () async -> Void) async {
        isWorking = true
        lastError = nil
        lastEvent = event
        await operation()
        isWorking = false
    }

    private func fail(_ message: String) {
        lastError = message
        lastEvent = "DAT error"
    }
}
