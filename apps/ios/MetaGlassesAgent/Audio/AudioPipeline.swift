import AVFoundation
import Foundation

struct LoopbackResult: Equatable {
    let chunkCount: Int
    let totalBytes: Int
    let recordingSeconds: TimeInterval
    let sampleRate: Int

    var estimatedPlaybackSeconds: Double {
        Double(totalBytes) / Double(sampleRate * MemoryLayout<Int16>.size)
    }
}

final class AudioPipeline {
    let micCapture: MicCapture
    let player: PCMPlayer

    init(micCapture: MicCapture = MicCapture(), player: PCMPlayer = PCMPlayer()) {
        self.micCapture = micCapture
        self.player = player
    }

    func start() async throws {
        try configureAudioSession()
        try micCapture.start()
        try player.start()
    }

    func runLoopback(
        recordingSeconds: TimeInterval = 3,
        progress: @escaping (String) -> Void = { _ in }
    ) async throws -> LoopbackResult {
        progress("Loopback: configuring audio session")
        try configureAudioSession()
        progress("Loopback: starting playback engine")
        try player.start()

        let lock = NSLock()
        var captured = Data()
        var chunkCount = 0

        micCapture.onChunkCaptured = { chunk in
            lock.lock()
            captured.append(chunk)
            chunkCount += 1
            lock.unlock()
        }

        progress("Loopback: starting mic capture")
        try micCapture.start()
        try await Task.sleep(nanoseconds: UInt64(recordingSeconds * 1_000_000_000))
        progress("Loopback: stopping mic capture")
        await micCapture.stopAndFlush()
        progress("Loopback: preparing playback")

        lock.lock()
        let playbackData = captured
        let result = LoopbackResult(
            chunkCount: chunkCount,
            totalBytes: captured.count,
            recordingSeconds: recordingSeconds,
            sampleRate: Int(MicCapture.targetSampleRate)
        )
        lock.unlock()

        micCapture.onChunkCaptured = nil
        progress("Loopback: playing captured audio")
        await player.enqueue(
            pcm: playbackData,
            sampleRate: result.sampleRate,
            turnID: "loopback-\(UUID().uuidString)"
        )

        return result
    }

    func stop() async {
        micCapture.stop()
        micCapture.onChunkCaptured = nil
        await player.reset()

        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }

    private func configureAudioSession() throws {
        let session = AVAudioSession.sharedInstance()
        try session.setCategory(
            .playAndRecord,
            mode: .voiceChat,
            options: [.allowBluetooth, .allowBluetoothA2DP, .defaultToSpeaker]
        )
        try session.setPreferredSampleRate(16_000)
        try session.setPreferredIOBufferDuration(0.05)
        try session.setActive(true, options: .notifyOthersOnDeactivation)
    }
}
