import AVFoundation
import Foundation

final class MicCapture {
    static let targetSampleRate = 16_000.0
    static let targetChunkBytes = 3_200

    private let audioEngine = AVAudioEngine()
    private let emitQueue = DispatchQueue(label: "MetaGlassesAgent.MicCapture.emit")
    private let continuation: AsyncStream<Data>.Continuation
    private var chunkBuffer = Data()
    private var isRunning = false

    let chunks: AsyncStream<Data>
    var onChunkCaptured: ((Data) -> Void)?

    init() {
        var continuation: AsyncStream<Data>.Continuation?
        self.chunks = AsyncStream { streamContinuation in
            continuation = streamContinuation
        }
        self.continuation = continuation!
    }

    func start() throws {
        guard !isRunning else {
            return
        }

        let input = audioEngine.inputNode
        let nativeFormat = input.outputFormat(forBus: 0)
        let targetFormat = AVAudioFormat(
            commonFormat: .pcmFormatFloat32,
            sampleRate: Self.targetSampleRate,
            channels: 1,
            interleaved: false
        )!

        let needsConversion = nativeFormat.commonFormat != .pcmFormatFloat32
            || nativeFormat.sampleRate != Self.targetSampleRate
            || nativeFormat.channelCount != 1
        let converter = needsConversion ? AVAudioConverter(from: nativeFormat, to: targetFormat) : nil

        input.removeTap(onBus: 0)
        input.installTap(onBus: 0, bufferSize: 4_096, format: nativeFormat) { [weak self] buffer, _ in
            guard let self else {
                return
            }

            let pcmBuffer: AVAudioPCMBuffer
            if let converter {
                guard let converted = self.convert(buffer, using: converter, targetFormat: targetFormat) else {
                    return
                }
                pcmBuffer = converted
            } else {
                pcmBuffer = buffer
            }

            self.appendPCM(self.float32BufferToInt16Data(pcmBuffer))
        }

        emitQueue.async {
            self.chunkBuffer.removeAll(keepingCapacity: true)
        }
        audioEngine.prepare()
        try audioEngine.start()
        isRunning = true
    }

    func stop() {
        stopCapture()
        emitQueue.async {
            self.flushRemainingChunk()
        }
    }

    func stopAndFlush() async {
        stopCapture()
        await withCheckedContinuation { continuation in
            emitQueue.async {
                self.flushRemainingChunk()
                continuation.resume()
            }
        }
    }

    private func stopCapture() {
        guard isRunning else {
            return
        }

        audioEngine.inputNode.removeTap(onBus: 0)
        audioEngine.stop()
        isRunning = false
    }

    private func convert(
        _ inputBuffer: AVAudioPCMBuffer,
        using converter: AVAudioConverter,
        targetFormat: AVAudioFormat
    ) -> AVAudioPCMBuffer? {
        let ratio = targetFormat.sampleRate / inputBuffer.format.sampleRate
        let outputFrameCount = AVAudioFrameCount(Double(inputBuffer.frameLength) * ratio)
        guard outputFrameCount > 0,
              let outputBuffer = AVAudioPCMBuffer(pcmFormat: targetFormat, frameCapacity: outputFrameCount)
        else {
            return nil
        }

        var error: NSError?
        var consumed = false
        converter.convert(to: outputBuffer, error: &error) { _, status in
            if consumed {
                status.pointee = .noDataNow
                return nil
            }

            consumed = true
            status.pointee = .haveData
            return inputBuffer
        }

        return error == nil ? outputBuffer : nil
    }

    private func float32BufferToInt16Data(_ buffer: AVAudioPCMBuffer) -> Data {
        guard let channelData = buffer.floatChannelData, buffer.frameLength > 0 else {
            return Data()
        }

        let samples = channelData[0]
        var data = Data(capacity: Int(buffer.frameLength) * MemoryLayout<Int16>.size)
        for index in 0..<Int(buffer.frameLength) {
            let clamped = max(-1.0, min(1.0, samples[index]))
            let sample = Int16(clamped * Float(Int16.max))
            var littleEndian = sample.littleEndian
            withUnsafeBytes(of: &littleEndian) { bytes in
                data.append(contentsOf: bytes)
            }
        }

        return data
    }

    private func appendPCM(_ pcmData: Data) {
        guard !pcmData.isEmpty else {
            return
        }

        emitQueue.async {
            self.chunkBuffer.append(pcmData)
            while self.chunkBuffer.count >= Self.targetChunkBytes {
                let chunk = Data(self.chunkBuffer.prefix(Self.targetChunkBytes))
                self.emit(chunk)
                self.chunkBuffer.removeFirst(Self.targetChunkBytes)
            }
        }
    }

    private func emit(_ chunk: Data) {
        continuation.yield(chunk)
        onChunkCaptured?(chunk)
    }

    private func flushRemainingChunk() {
        if !chunkBuffer.isEmpty {
            emit(chunkBuffer)
            chunkBuffer.removeAll(keepingCapacity: true)
        }
    }
}
