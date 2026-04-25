import MWDATCamera
import MWDATCore
import UIKit

@MainActor
final class DATGlassesSession: GlassesSession {
    private let continuation: AsyncStream<GlassesState>.Continuation
    let stateStream: AsyncStream<GlassesState>
    private let wearables: WearablesInterface
    private let deviceSelector: AutoDeviceSelector
    private var deviceSession: DeviceSession?
    private var streamSession: StreamSession?
    private var deviceStateTask: Task<Void, Never>?
    private var stateListenerToken: AnyListenerToken?
    private var videoFrameListenerToken: AnyListenerToken?
    private var errorListenerToken: AnyListenerToken?
    private var photoDataListenerToken: AnyListenerToken?
    private var photoContinuation: CheckedContinuation<Data, Error>?
    private var photoTimeoutTask: Task<Void, Never>?
    private var videoFrameContinuation: AsyncStream<UIImage>.Continuation?

    init(wearables: WearablesInterface = Wearables.shared) {
        self.wearables = wearables
        self.deviceSelector = AutoDeviceSelector(wearables: wearables)
        var continuation: AsyncStream<GlassesState>.Continuation?
        self.stateStream = AsyncStream { streamContinuation in
            continuation = streamContinuation
        }
        self.continuation = continuation!
    }

    func start() async throws {
        continuation.yield(.connecting)

        var cameraStatus = try await wearables.checkPermissionStatus(.camera)
        if cameraStatus != .granted {
            cameraStatus = try await wearables.requestPermission(.camera)
        }
        guard cameraStatus == .granted else {
            throw GlassesSessionError.cameraPermissionDenied
        }

        let session = try wearables.createSession(deviceSelector: deviceSelector)
        deviceSession = session

        let stateStream = session.stateStream()
        try session.start()
        guard await waitForDeviceSessionStarted(stateStream, timeoutSeconds: 15) else {
            deviceSession = nil
            throw GlassesSessionError.deviceSessionUnavailable
        }
        observeDeviceState(session)

        guard let stream = try session.addStream(
            config: StreamSessionConfig(videoCodec: .raw, resolution: .low, frameRate: 24)
        ) else {
            throw GlassesSessionError.streamSessionUnavailable
        }
        streamSession = stream
        setupListeners(for: stream)
        await stream.start()

        continuation.yield(.ready)
    }

    func stop() async {
        photoContinuation?.resume(throwing: CancellationError())
        photoContinuation = nil
        photoTimeoutTask?.cancel()
        photoTimeoutTask = nil
        deviceStateTask?.cancel()
        deviceStateTask = nil
        clearListeners()

        if let streamSession {
            await streamSession.stop()
        }
        deviceSession?.stop()
        streamSession = nil
        deviceSession = nil
        videoFrameContinuation?.finish()
        videoFrameContinuation = nil
        continuation.yield(.stopped)
    }

    func capturePhoto() async throws -> Data {
        guard let streamSession else {
            throw GlassesSessionError.streamSessionUnavailable
        }

        return try await withCheckedThrowingContinuation { continuation in
            photoContinuation = continuation
            photoTimeoutTask = Task { [weak self] in
                try? await Task.sleep(nanoseconds: 5_000_000_000)
                await MainActor.run {
                    guard let self, self.photoContinuation != nil else {
                        return
                    }
                    self.photoContinuation?.resume(throwing: GlassesSessionError.photoCaptureTimedOut)
                    self.photoContinuation = nil
                    self.photoTimeoutTask = nil
                }
            }

            let success = streamSession.capturePhoto(format: .jpeg)
            if !success {
                photoTimeoutTask?.cancel()
                photoTimeoutTask = nil
                photoContinuation = nil
                continuation.resume(throwing: GlassesSessionError.photoCaptureRejected)
            }
        }
    }

    func videoFrames(at fps: Double) -> AsyncStream<UIImage> {
        AsyncStream { continuation in
            videoFrameContinuation = continuation

            continuation.onTermination = { _ in
                Task { @MainActor in
                    self.videoFrameContinuation = nil
                }
            }
        }
    }

    private func waitForDeviceSessionStarted(
        _ states: AsyncStream<DeviceSessionState>,
        timeoutSeconds: UInt64
    ) async -> Bool {
        await withCheckedContinuation { continuation in
            var didResume = false
            var stateTask: Task<Void, Never>?
            var timeoutTask: Task<Void, Never>?

            func finish(_ result: Bool) {
                guard !didResume else {
                    return
                }
                didResume = true
                stateTask?.cancel()
                timeoutTask?.cancel()
                continuation.resume(returning: result)
            }

            stateTask = Task {
                for await state in states {
                    if Task.isCancelled {
                        return
                    }
                    switch state {
                    case .started:
                        await MainActor.run { finish(true) }
                        return
                    case .stopped:
                        await MainActor.run { finish(false) }
                        return
                    default:
                        continue
                    }
                }
                await MainActor.run { finish(false) }
            }

            timeoutTask = Task {
                try? await Task.sleep(nanoseconds: timeoutSeconds * 1_000_000_000)
                await MainActor.run { finish(false) }
            }
        }
    }

    private func waitForStreamReady(timeoutSeconds: UInt64) async -> Bool {
        guard let streamSession else {
            return false
        }
        if streamSession.state == .streaming {
            return true
        }

        return await withCheckedContinuation { continuation in
            var didResume = false
            var token: AnyListenerToken?
            var timeoutTask: Task<Void, Never>?

            func finish(_ result: Bool) {
                guard !didResume else {
                    return
                }
                didResume = true
                token = nil
                timeoutTask?.cancel()
                continuation.resume(returning: result)
            }

            token = streamSession.statePublisher.listen { state in
                Task { @MainActor in
                    switch state {
                    case .streaming:
                        finish(true)
                    case .stopped:
                        finish(false)
                    default:
                        break
                    }
                }
            }

            timeoutTask = Task {
                try? await Task.sleep(nanoseconds: timeoutSeconds * 1_000_000_000)
                await MainActor.run { finish(false) }
            }
        }
    }

    private func observeDeviceState(_ session: DeviceSession) {
        deviceStateTask?.cancel()
        deviceStateTask = Task { [weak self] in
            for await state in session.stateStream() {
                guard let self else {
                    return
                }
                if state == .stopped {
                    self.continuation.yield(.stopped)
                    return
                }
            }
        }
    }

    private func setupListeners(for stream: StreamSession) {
        stateListenerToken = stream.statePublisher.listen { [weak self] state in
            Task { @MainActor in
                self?.handleStreamState(state)
            }
        }

        videoFrameListenerToken = stream.videoFramePublisher.listen { [weak self] frame in
            Task { @MainActor in
                if let image = frame.makeUIImage() {
                    self?.videoFrameContinuation?.yield(image)
                }
            }
        }

        errorListenerToken = stream.errorPublisher.listen { [weak self] error in
            Task { @MainActor in
                self?.continuation.yield(.error(String(describing: error)))
            }
        }

        photoDataListenerToken = stream.photoDataPublisher.listen { [weak self] photo in
            Task { @MainActor in
                guard let self else {
                    return
                }
                self.photoTimeoutTask?.cancel()
                self.photoTimeoutTask = nil
                self.photoContinuation?.resume(returning: photo.data)
                self.photoContinuation = nil
            }
        }
    }

    private func clearListeners() {
        stateListenerToken = nil
        videoFrameListenerToken = nil
        errorListenerToken = nil
        photoDataListenerToken = nil
    }

    private func handleStreamState(_ state: StreamSessionState) {
        switch state {
        case .streaming:
            continuation.yield(.streaming)
        case .paused:
            continuation.yield(.paused)
        case .stopped:
            continuation.yield(.ready)
        case .waitingForDevice, .starting, .stopping:
            continuation.yield(.connecting)
        }
    }
}
