import MWDATCamera
import MWDATCore
import UIKit

final class DATGlassesSession: GlassesSession {
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
        // TODO(Lucas): Select a real paired wearable via Wearables.shared and start a camera stream.
        continuation.yield(.ready)
    }

    func stop() async {
        // TODO(Lucas): Stop the active DAT stream session once wired to hardware.
        continuation.yield(.stopped)
    }

    func capturePhoto() async throws -> Data {
        // TODO(Lucas): Replace with DAT still capture from the active camera session.
        try PlaceholderPhoto.jpegData(label: "DAT glasses")
    }

    func videoFrames(at fps: Double) -> AsyncStream<UIImage> {
        // TODO(Lucas): Replace with MWDATCamera stream frames.
        AsyncStream { continuation in
            continuation.finish()
        }
    }
}
