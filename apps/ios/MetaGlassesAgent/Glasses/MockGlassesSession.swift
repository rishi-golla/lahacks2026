import MWDATMockDevice
import UIKit

final class MockGlassesSession: GlassesSession {
    private let continuation: AsyncStream<GlassesState>.Continuation
    let stateStream: AsyncStream<GlassesState>

    init() {
        var continuation: AsyncStream<GlassesState>.Continuation?
        self.stateStream = AsyncStream { streamContinuation in
            continuation = streamContinuation
        }
        self.continuation = continuation!
    }

    func start() async throws {
        continuation.yield(.connecting)

        #if DEBUG
        MockDeviceKit.shared.enable()
        let device = MockDeviceKit.shared.pairRaybanMeta()
        device.powerOn()
        device.unfold()
        #endif

        continuation.yield(.ready)
    }

    func stop() async {
        #if DEBUG
        MockDeviceKit.shared.disable()
        #endif

        continuation.yield(.stopped)
    }

    func capturePhoto() async throws -> Data {
        try PlaceholderPhoto.jpegData(label: "Mock glasses")
    }

    func videoFrames(at fps: Double) -> AsyncStream<UIImage> {
        AsyncStream { continuation in
            let task = Task {
                let interval = UInt64(1_000_000_000 / max(fps, 1))
                while !Task.isCancelled {
                    continuation.yield(PlaceholderPhoto.image(label: "Mock frame"))
                    try? await Task.sleep(nanoseconds: interval)
                }
                continuation.finish()
            }

            continuation.onTermination = { _ in
                task.cancel()
            }
        }
    }
}
