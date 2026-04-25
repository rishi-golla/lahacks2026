import AVFoundation

final class AudioPipeline {
    let micCapture: MicCapture
    let player: PCMPlayer

    init(micCapture: MicCapture = MicCapture(), player: PCMPlayer = PCMPlayer()) {
        self.micCapture = micCapture
        self.player = player
    }

    func start() async throws {
        let session = AVAudioSession.sharedInstance()
        try session.setCategory(
            .playAndRecord,
            mode: .voiceChat,
            options: [.allowBluetooth, .allowBluetoothA2DP, .defaultToSpeaker]
        )
        try session.setPreferredSampleRate(16_000)
        try session.setPreferredIOBufferDuration(0.05)
        try session.setActive(true, options: .notifyOthersOnDeactivation)
        try micCapture.start()
        try player.start()
    }

    func stop() async {
        micCapture.stop()
        await player.reset()

        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }
}
