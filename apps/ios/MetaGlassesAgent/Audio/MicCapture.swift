import AVFoundation
import Foundation

final class MicCapture {
    static let targetSampleRate = 16_000
    static let targetChunkBytes = 3_200

    private let audioEngine = AVAudioEngine()
    private let continuation: AsyncStream<Data>.Continuation
    private var chunkBuffer = Data()

    let chunks: AsyncStream<Data>

    init() {
        var continuation: AsyncStream<Data>.Continuation?
        self.chunks = AsyncStream { streamContinuation in
            continuation = streamContinuation
        }
        self.continuation = continuation!
    }

    func start() throws {
        let input = audioEngine.inputNode
        let format = input.inputFormat(forBus: 0)

        input.removeTap(onBus: 0)
        input.installTap(onBus: 0, bufferSize: 1_024, format: format) { [weak self] buffer, _ in
            self?.handle(buffer: buffer)
        }

        audioEngine.prepare()
        try audioEngine.start()
    }

    func stop() {
        audioEngine.inputNode.removeTap(onBus: 0)
        audioEngine.stop()
        if !chunkBuffer.isEmpty {
            continuation.yield(chunkBuffer)
            chunkBuffer.removeAll(keepingCapacity: true)
        }
    }

    private func handle(buffer: AVAudioPCMBuffer) {
        guard let channels = buffer.floatChannelData, buffer.frameLength > 0 else {
            return
        }

        let inputSamples = channels[0]
        let inputRate = buffer.format.sampleRate
        let outputCount = max(1, Int(Double(buffer.frameLength) * Double(Self.targetSampleRate) / inputRate))

        for outputIndex in 0..<outputCount {
            let sourceIndex = min(Int(Double(outputIndex) * inputRate / Double(Self.targetSampleRate)), Int(buffer.frameLength) - 1)
            let clamped = max(-1.0, min(1.0, inputSamples[sourceIndex]))
            let sample = Int16(clamped * Float(Int16.max)).littleEndian
            withUnsafeBytes(of: sample) { bytes in
                chunkBuffer.append(contentsOf: bytes)
            }
        }

        while chunkBuffer.count >= Self.targetChunkBytes {
            let chunk = chunkBuffer.prefix(Self.targetChunkBytes)
            continuation.yield(Data(chunk))
            chunkBuffer.removeFirst(Self.targetChunkBytes)
        }
    }
}
