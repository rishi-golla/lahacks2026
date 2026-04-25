import AVFoundation
import Foundation

final class PCMPlayer {
    private let audioEngine = AVAudioEngine()
    private let playerNode = AVAudioPlayerNode()
    private var interruptedTurnIDs = Set<String>()
    private var isAttached = false

    func start() throws {
        guard !audioEngine.isRunning else {
            return
        }

        if !isAttached {
            audioEngine.attach(playerNode)
            isAttached = true
        }
        let format = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: 24_000, channels: 1, interleaved: false)
        audioEngine.connect(playerNode, to: audioEngine.mainMixerNode, format: format)
        audioEngine.prepare()
        try audioEngine.start()
        playerNode.play()
    }

    func enqueue(pcm: Data, sampleRate: Int, turnID: String) async {
        guard !interruptedTurnIDs.contains(turnID),
              let buffer = makeBuffer(pcm: pcm, sampleRate: sampleRate)
        else {
            return
        }

        if !playerNode.isPlaying {
            playerNode.play()
        }
        playerNode.scheduleBuffer(buffer, completionHandler: nil)
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
}
