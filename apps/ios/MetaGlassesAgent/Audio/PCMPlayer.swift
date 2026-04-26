import AVFoundation
import Foundation

@MainActor
final class PCMPlayer {
    private let audioEngine = AVAudioEngine()
    private let playerNode = AVAudioPlayerNode()
    private var interruptedTurnIDs = Set<String>()
    private var isAttached = false
    private var connectedSampleRate: Int?
    private(set) var scheduledBufferCount = 0

    func start(sampleRate: Int = 24_000) throws {
        try connectIfNeeded(sampleRate: sampleRate)
    }

    func enqueue(pcm: Data, sampleRate: Int, turnID: String) async {
        guard !interruptedTurnIDs.contains(turnID),
              let buffer = makeBuffer(pcm: pcm, sampleRate: sampleRate)
        else {
            return
        }

        do {
            try connectIfNeeded(sampleRate: sampleRate)
        } catch {
            return
        }

        if !playerNode.isPlaying {
            playerNode.play()
        }
        playerNode.scheduleBuffer(buffer, completionHandler: nil)
        scheduledBufferCount += 1
    }

    func interrupt(turnID: String) async {
        interruptedTurnIDs.insert(turnID)
        playerNode.stop()
        playerNode.play()
    }

    func reset() async {
        interruptedTurnIDs.removeAll()
        playerNode.stop()
        audioEngine.stop()
        connectedSampleRate = nil
        scheduledBufferCount = 0
    }

    private func makeBuffer(pcm: Data, sampleRate: Int) -> AVAudioPCMBuffer? {
        let sampleCount = pcm.count / MemoryLayout<Int16>.size
        guard sampleCount > 0,
              let format = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: Double(sampleRate), channels: 1, interleaved: false),
              let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: AVAudioFrameCount(sampleCount)),
              let channel = buffer.floatChannelData?[0]
        else {
            return nil
        }

        buffer.frameLength = AVAudioFrameCount(sampleCount)
        pcm.withUnsafeBytes { rawBuffer in
            let samples = rawBuffer.bindMemory(to: Int16.self)
            for index in 0..<sampleCount {
                channel[index] = Float(Int16(littleEndian: samples[index])) / Float(Int16.max)
            }
        }

        return buffer
    }

    private func connectIfNeeded(sampleRate: Int) throws {
        if !isAttached {
            audioEngine.attach(playerNode)
            isAttached = true
        }

        if connectedSampleRate != sampleRate {
            if audioEngine.isRunning {
                playerNode.stop()
                audioEngine.stop()
            }

            let format = AVAudioFormat(
                commonFormat: .pcmFormatFloat32,
                sampleRate: Double(sampleRate),
                channels: 1,
                interleaved: false
            )!
            audioEngine.connect(playerNode, to: audioEngine.mainMixerNode, format: format)
            connectedSampleRate = sampleRate
        }

        if !audioEngine.isRunning {
            audioEngine.prepare()
            try audioEngine.start()
        }

        if !playerNode.isPlaying {
            playerNode.play()
        }
    }
}
