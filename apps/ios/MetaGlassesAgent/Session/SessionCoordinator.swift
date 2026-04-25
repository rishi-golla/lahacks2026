import Foundation
import UIKit

@MainActor
final class SessionCoordinator: ObservableObject {
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

    private let glasses: GlassesSession
    private let audioPipeline: AudioPipeline
    private let backend: BackendClient
    private let photoCapture = PhotoCapture()
    private var receiveTask: Task<Void, Never>?
    private var sessionResumeToken: String?

    init(
        glasses: GlassesSession,
        audioPipeline: AudioPipeline = AudioPipeline(),
        backendURL: URL
    ) {
        self.glasses = glasses
        self.audioPipeline = audioPipeline
        self.backend = BackendClient(url: backendURL)
    }

    func start() async {
        guard status != .live && status != .connecting else {
            return
        }

        status = .connecting
        appendDebug("Starting session")

        do {
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
            status = .error(error.localizedDescription)
            appendDebug("Start failed: \(error.localizedDescription)")
        }
    }

    func stop() async {
        receiveTask?.cancel()
        receiveTask = nil
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
            let jpeg = try await photoCapture.captureJPEG(from: glasses)
            lastPhoto = UIImage(data: jpeg)
            let message = PhotoFrame(jpegBase64: jpeg.base64EncodedString(), trigger: .userRequest)
            try await backend.send(.photo(message))
            appendDebug("Captured and sent photo")
        } catch {
            appendDebug("Photo failed: \(error.localizedDescription)")
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

    private func handle(_ message: ServerMessage) async {
        switch message {
        case .ready(let ready):
            sessionResumeToken = ready.sessionResumeToken
            appendDebug("Backend ready: \(ready.model)")
        case .sessionUpdate(let update):
            sessionResumeToken = update.sessionResumeToken
            appendDebug("Session token refreshed")
        case .audioChunk(let chunk):
            if let data = Data(base64Encoded: chunk.pcmBase64) {
                await audioPipeline.player.enqueue(pcm: data, sampleRate: chunk.sampleRate, turnID: chunk.turnID)
            }
        case .transcriptIn(let transcript):
            lastUserTranscript = transcript.text
        case .transcriptOut(let transcript):
            lastModelTranscript = transcript.text
        case .toolEvent(let event):
            toolEventsLog.insert(event, at: 0)
        case .lookRequest(let request):
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
            status = .ended
        case .echo(let echo):
            appendDebug("Echo: \(echo.received)")
        case .unknown(let type, _):
            appendDebug("Ignored unknown message: \(type)")
        }
    }

    private func handleLookRequest(_ request: LookRequest) async {
        do {
            let jpeg = try await photoCapture.captureJPEG(from: glasses)
            lastPhoto = UIImage(data: jpeg)
            let message = PhotoFrame(jpegBase64: jpeg.base64EncodedString(), trigger: .toolLook, toolCallID: request.toolCallID)
            try await backend.send(.photo(message))
            appendDebug("Responded to look_request: \(request.reason)")
        } catch {
            appendDebug("look_request failed: \(error.localizedDescription)")
        }
    }

    private func appendDebug(_ line: String) {
        latestDebugLine = line
        debugLog.insert(line, at: 0)
        if debugLog.count > 100 {
            debugLog.removeLast(debugLog.count - 100)
        }
    }
}
