import Foundation
import CryptoKit
import UIKit

@MainActor
final class SessionCoordinator: ObservableObject {
    private enum VisualContextEvent {
        case frame(UIImage)
        case firstFrameTimeout
    }

    enum Status: Equatable {
        case idle
        case connecting
        case live
        case reconnecting
        case ended
        case error(String)

        var label: String {
            switch self {
            case .idle:
                return "Idle"
            case .connecting:
                return "Connecting"
            case .live:
                return "Live"
            case .reconnecting:
                return "Reconnecting"
            case .ended:
                return "Ended"
            case .error:
                return "Error"
            }
        }
    }

    @Published private(set) var status: Status = .idle
    @Published private(set) var lastUserTranscript = ""
    @Published private(set) var lastModelTranscript = ""
    @Published private(set) var lastPhoto: UIImage?
    @Published private(set) var toolEventsLog: [ToolEvent] = []
    @Published private(set) var debugLog: [String] = []
    @Published private(set) var latestDebugLine = "No debug events yet"
    @Published private(set) var isLoopbackRunning = false
    @Published private(set) var isMicStreaming = false
    @Published private(set) var isVisualContextStreaming = false
    @Published private(set) var visualContextSourceLabel = "Idle"
    @Published private(set) var visualContextFrameCount = 0

    private let glasses: GlassesSession
    private let glassesSourceLabel: String
    private let audioPipeline: AudioPipeline
    private let backend: BackendClient
    private let photoCapture = PhotoCapture()
    private var receiveTask: Task<Void, Never>?
    private var glassesStateTask: Task<Void, Never>?
    private var micStreamingTask: Task<Void, Never>?
    private var visualContextTask: Task<Void, Never>?
    private var sessionResumeToken: String?
    private var sentAudioChunkCount = 0
    private var sentVisualFrameCount = 0
    private var lastVisualPreviewUpdateSeconds: TimeInterval = 0
    private let visualStreamFirstFrameTimeoutNanoseconds: UInt64 = 3_000_000_000
    private let visualFallbackIntervalNanoseconds: UInt64 = 4_000_000_000
    private let visualPreviewUpdateIntervalSeconds: TimeInterval = 4

    init(
        glasses: GlassesSession,
        glassesSourceLabel: String? = nil,
        audioPipeline: AudioPipeline? = nil,
        backendURL: URL
    ) {
        self.glasses = glasses
        self.glassesSourceLabel = glassesSourceLabel ?? String(describing: type(of: glasses))
        self.audioPipeline = audioPipeline ?? AudioPipeline()
        self.backend = BackendClient(url: backendURL)
    }

    func start() async {
        guard status != .live && status != .connecting else {
            return
        }

        status = .connecting
        appendDebug("Starting session")

        do {
            startGlassesStateObserver()
            appendDebug("Starting glasses session")
            try await glasses.start()
            appendDebug("Glasses session ready")
            appendDebug("Connecting to backend")
            try await backend.connect()
            try await backend.send(.hello(Hello(sessionResume: sessionResumeToken)))
            startReceiveLoop()
            status = .live
            appendDebug("Connected to backend")
        } catch {
            await cleanupAfterFailedStart()
            status = .error(error.localizedDescription)
            appendDebug("Start failed: \(error.localizedDescription)")
        }
    }

    func stop() async {
        await stopAssistantInputLoops()
        receiveTask?.cancel()
        receiveTask = nil
        glassesStateTask?.cancel()
        glassesStateTask = nil
        backend.close()
        await audioPipeline.stop()
        await glasses.stop()
        status = .ended
        appendDebug("Session stopped")
    }

    func bargeIn() async {
        do {
            try await backend.send(.bargeIn)
            appendDebug("Sent barge_in")
        } catch {
            appendDebug("Failed to send barge_in: \(error.localizedDescription)")
        }
    }

    func sendDebugText(_ text: String) async {
        guard !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return
        }

        do {
            try await backend.send(.text(TextMessage(text: text)))
            appendDebug("Sent text: \(text)")
        } catch {
            appendDebug("Failed to send text: \(error.localizedDescription)")
        }
    }

    func captureDebugPhoto() async {
        do {
            appendDebug("Manual photo capture starting via \(glassesSourceLabel)")
            let jpeg = try await photoCapture.captureJPEG(from: glasses)
            lastPhoto = UIImage(data: jpeg)
            let message = PhotoFrame(jpegBase64: jpeg.base64EncodedString(), trigger: .userRequest)
            appendDebug("Manual photo captured: \(jpeg.count) bytes via \(glassesSourceLabel)")
            appendDebug(photoDiagnosticsLine(prefix: "Manual photo ready", jpeg: jpeg, trigger: .userRequest))
            try await backend.send(.photo(message))
            appendDebug("Manual photo sent: trigger=\(message.trigger.rawValue), ts=\(message.timestampMs)")
        } catch {
            appendDebug("Manual photo failed via \(glassesSourceLabel): \(error.localizedDescription)")
        }
    }

    func runLoopbackTest() async {
        guard !isLoopbackRunning else {
            return
        }

        isLoopbackRunning = true
        appendDebug("Loopback: recording 3 seconds...")
        defer {
            isLoopbackRunning = false
        }

        do {
            let result = try await audioPipeline.runLoopback(recordingSeconds: 3) { [weak self] line in
                Task { @MainActor in
                    self?.appendDebug(line)
                }
            }
            appendDebug(
                "Loopback: \(result.chunkCount) chunks, \(result.totalBytes) bytes, ~\(String(format: "%.2f", result.estimatedPlaybackSeconds))s playback"
            )
        } catch {
            appendDebug("Loopback failed: \(error.localizedDescription)")
        }
    }

    private func startReceiveLoop() {
        receiveTask?.cancel()
        receiveTask = Task { [weak self] in
            guard let self else {
                return
            }

            do {
                for try await message in backend.messages() {
                    await handle(message)
                }
            } catch {
                status = .error(error.localizedDescription)
                appendDebug("Receive loop ended: \(error.localizedDescription)")
            }
        }
    }

    private func startGlassesStateObserver() {
        glassesStateTask?.cancel()
        glassesStateTask = Task { [weak self] in
            guard let self else {
                return
            }

            for await state in glasses.stateStream {
                appendDebug("Glasses: \(label(for: state))")
            }
        }
    }

    private func handle(_ message: ServerMessage) async {
        switch message {
        case .ready(let ready):
            sessionResumeToken = ready.sessionResumeToken
            appendDebug("Backend ready: \(ready.model)")
            await startAssistantInputLoops()
        case .sessionUpdate(let update):
            sessionResumeToken = update.sessionResumeToken
            appendDebug("Session token refreshed")
        case .audioChunk(let chunk):
            if let data = Data(base64Encoded: chunk.pcmBase64) {
                appendDebug("Received audio chunk: \(data.count) bytes @ \(chunk.sampleRate)Hz")
                await audioPipeline.player.enqueue(pcm: data, sampleRate: chunk.sampleRate, turnID: chunk.turnID)
            } else {
                appendDebug("Received invalid audio chunk")
            }
        case .transcriptIn(let transcript):
            lastUserTranscript = transcript.text
        case .transcriptOut(let transcript):
            lastModelTranscript = transcript.text
        case .toolEvent(let event):
            toolEventsLog.insert(event, at: 0)
        case .lookRequest(let request):
            appendDebug("Received look_request: id=\(request.toolCallID), reason=\(request.reason)")
            await handleLookRequest(request)
        case .modelInterrupt(let interrupt):
            await audioPipeline.player.interrupt(turnID: interrupt.turnID)
        case .pong(let pong):
            appendDebug("Pong \(pong.serverTimestampMs - pong.clientTimestampMs)ms")
        case .error(let error):
            appendDebug("Backend error: \(error.message)")
            if error.fatal == true {
                status = .error(error.message)
            }
        case .sessionEnd(let sessionEnd):
            appendDebug("Session ended: \(sessionEnd.reason)")
        case .echo(let echo):
            appendDebug("Echo: \(echo.received)")
        case .unknown(let type, _):
            appendDebug("Ignored unknown message: \(type)")
        }
    }

    private func handleLookRequest(_ request: LookRequest) async {
        do {
            appendDebug("look_request capture starting via \(glassesSourceLabel)")
            let jpeg = try await photoCapture.captureJPEG(from: glasses)
            lastPhoto = UIImage(data: jpeg)
            let message = PhotoFrame(jpegBase64: jpeg.base64EncodedString(), trigger: .toolLook, toolCallID: request.toolCallID)
            appendDebug("look_request photo captured: \(jpeg.count) bytes via \(glassesSourceLabel)")
            appendDebug(
                photoDiagnosticsLine(
                    prefix: "look_request photo ready",
                    jpeg: jpeg,
                    trigger: .toolLook,
                    toolCallID: request.toolCallID
                )
            )
            try await backend.send(.photo(message))
            appendDebug("look_request photo sent: id=\(request.toolCallID), trigger=\(message.trigger.rawValue)")
        } catch {
            appendDebug("look_request failed via \(glassesSourceLabel): \(error.localizedDescription)")
        }
    }

    private func startAssistantInputLoops() async {
        startVisualContextLoop()
        await startMicStreaming()
    }

    private func startMicStreaming() async {
        guard micStreamingTask == nil else {
            return
        }

        do {
            try await audioPipeline.start()
        } catch {
            appendDebug("Mic streaming failed to start: \(error.localizedDescription)")
            return
        }

        sentAudioChunkCount = 0
        isMicStreaming = true
        appendDebug("Mic streaming started")
        micStreamingTask = Task { [weak self] in
            guard let self else {
                return
            }
            defer {
                isMicStreaming = false
            }

            for await chunk in audioPipeline.micCapture.chunks {
                if Task.isCancelled {
                    break
                }

                do {
                    let message = AudioFrame(
                        pcmBase64: chunk.base64EncodedString(),
                        sampleRate: Int(MicCapture.targetSampleRate)
                    )
                    try await backend.send(.audio(message))
                    sentAudioChunkCount += 1
                    if sentAudioChunkCount == 1 || sentAudioChunkCount.isMultiple(of: 50) {
                        appendDebug("Mic audio sent: \(sentAudioChunkCount) chunks")
                    }
                } catch {
                    appendDebug("Mic audio send failed: \(error.localizedDescription)")
                    break
                }
            }
        }
    }

    private func startVisualContextLoop() {
        guard visualContextTask == nil else {
            return
        }

        sentVisualFrameCount = 0
        lastVisualPreviewUpdateSeconds = 0
        isVisualContextStreaming = true
        visualContextSourceLabel = "Starting"
        appendDebug("Auto visual context started via \(glassesSourceLabel)")
        visualContextTask = Task { [weak self] in
            guard let self else {
                return
            }
            defer {
                isVisualContextStreaming = false
                visualContextSourceLabel = "Idle"
            }

            let events = visualContextEvents(
                from: glasses.videoFrames(at: 1),
                firstFrameTimeoutNanoseconds: visualStreamFirstFrameTimeoutNanoseconds
            )

            for await event in events {
                if Task.isCancelled {
                    break
                }

                switch event {
                case .frame(let image):
                    visualContextSourceLabel = "Video stream"
                    await sendAutoVisualFrame(image)
                case .firstFrameTimeout:
                    guard sentVisualFrameCount == 0 else {
                        continue
                    }
                    appendDebug("Auto visual stream timed out; trying still capture fallback")
                    let shouldKeepFallback = await runStillCaptureVisualFallback()
                    if shouldKeepFallback {
                        return
                    }
                    visualContextSourceLabel = "Waiting for video stream"
                    appendDebug("Still capture fallback unavailable; waiting for video stream")
                }
            }
        }
    }

    private func sendAutoVisualFrame(_ image: UIImage) async {
        do {
            let jpeg = try photoCapture.resizeAndEncode(image)
            await sendAutoVisualJPEG(jpeg, previewImage: image)
        } catch {
            appendDebug("Auto visual frame failed via \(glassesSourceLabel): \(error.localizedDescription)")
        }
    }

    private func runStillCaptureVisualFallback() async -> Bool {
        visualContextSourceLabel = "Still capture fallback"

        while !Task.isCancelled {
            do {
                let rawPhoto = try await glasses.capturePhoto()
                let capturedImage = UIImage(data: rawPhoto)
                let jpeg = try photoCapture.normalizeJPEGData(rawPhoto)
                await sendAutoVisualJPEG(jpeg, previewImage: capturedImage)
            } catch is CancellationError {
                break
            } catch GlassesSessionError.photoCaptureRejected {
                appendDebug("Still capture fallback rejected via \(glassesSourceLabel); disabling fallback")
                return false
            } catch {
                appendDebug("Still capture fallback failed via \(glassesSourceLabel): \(error.localizedDescription)")
            }

            try? await Task.sleep(nanoseconds: visualFallbackIntervalNanoseconds)
        }

        return true
    }

    private func sendAutoVisualJPEG(_ jpeg: Data, previewImage: UIImage?) async {
        let preview = UIImage(data: jpeg) ?? previewImage
        if let preview, shouldUpdateVisualPreview() {
            lastPhoto = preview
            visualContextFrameCount += 1
        } else {
            appendDebug(preview == nil ? "Auto visual preview decode failed; sending frame anyway" : "Auto visual preview skipped; sending frame")
        }
        let message = PhotoFrame(jpegBase64: jpeg.base64EncodedString(), trigger: .auto)
        appendDebug("Auto visual frame prepared: \(jpeg.count) bytes via \(glassesSourceLabel)")
        appendDebug(photoDiagnosticsLine(prefix: "Auto visual frame ready", jpeg: jpeg, trigger: .auto))

        do {
            try await backend.send(.photo(message))
            sentVisualFrameCount += 1
            appendDebug("Auto visual frame sent: \(jpeg.count) bytes via \(glassesSourceLabel)")
        } catch {
            appendDebug("Auto visual frame send failed via \(glassesSourceLabel): \(error.localizedDescription)")
        }
    }

    private func shouldUpdateVisualPreview() -> Bool {
        let now = Date().timeIntervalSince1970
        guard visualContextFrameCount > 0 else {
            lastVisualPreviewUpdateSeconds = now
            return true
        }
        guard now - lastVisualPreviewUpdateSeconds >= visualPreviewUpdateIntervalSeconds else {
            return false
        }
        lastVisualPreviewUpdateSeconds = now
        return true
    }

    private func visualContextEvents(
        from frames: AsyncStream<UIImage>,
        firstFrameTimeoutNanoseconds: UInt64
    ) -> AsyncStream<VisualContextEvent> {
        AsyncStream { continuation in
            let timeoutTask = Task {
                try? await Task.sleep(nanoseconds: firstFrameTimeoutNanoseconds)
                guard !Task.isCancelled else {
                    return
                }
                continuation.yield(.firstFrameTimeout)
            }

            let frameTask = Task {
                for await image in frames {
                    timeoutTask.cancel()
                    continuation.yield(.frame(image))
                }
                continuation.finish()
            }

            continuation.onTermination = { _ in
                timeoutTask.cancel()
                frameTask.cancel()
            }
        }
    }

    private func stopAssistantInputLoops() async {
        micStreamingTask?.cancel()
        micStreamingTask = nil
        visualContextTask?.cancel()
        visualContextTask = nil
        isMicStreaming = false
        isVisualContextStreaming = false
        visualContextSourceLabel = "Idle"

        try? await backend.send(.audioEnd)
    }

    private func cleanupAfterFailedStart() async {
        micStreamingTask?.cancel()
        micStreamingTask = nil
        visualContextTask?.cancel()
        visualContextTask = nil
        receiveTask?.cancel()
        receiveTask = nil
        glassesStateTask?.cancel()
        glassesStateTask = nil
        isMicStreaming = false
        isVisualContextStreaming = false
        visualContextSourceLabel = "Idle"
        backend.close()
        await audioPipeline.stop()
        await glasses.stop()
    }

    private func appendDebug(_ line: String) {
        latestDebugLine = line
        debugLog.insert(line, at: 0)
        if debugLog.count > 100 {
            debugLog.removeLast(debugLog.count - 100)
        }
    }

    private func label(for state: GlassesState) -> String {
        switch state {
        case .stopped:
            return "stopped"
        case .connecting:
            return "connecting"
        case .ready:
            return "ready"
        case .streaming:
            return "streaming"
        case .paused:
            return "paused"
        case .error(let message):
            return "error - \(message)"
        }
    }

    private func photoDiagnosticsLine(
        prefix: String,
        jpeg: Data,
        trigger: PhotoTrigger,
        toolCallID: String? = nil
    ) -> String {
        let digest = SHA256.hash(data: jpeg).map { String(format: "%02x", $0) }.joined()
        let firstBytes = jpeg.prefix(12).map { String(format: "%02x", $0) }.joined(separator: " ")
        let suffix = toolCallID.map { ", toolCallID=\($0)" } ?? ""
        return "\(prefix): trigger=\(trigger.rawValue), bytes=\(jpeg.count), sha256=\(digest), firstBytes=\(firstBytes)\(suffix)"
    }
}
