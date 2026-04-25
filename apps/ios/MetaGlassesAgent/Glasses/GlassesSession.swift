import UIKit

enum GlassesState: Equatable {
    case stopped
    case connecting
    case ready
    case streaming
    case paused
    case error(String)
}

protocol GlassesSession: AnyObject {
    var stateStream: AsyncStream<GlassesState> { get }

    func start() async throws
    func stop() async
    func capturePhoto() async throws -> Data
    func videoFrames(at fps: Double) -> AsyncStream<UIImage>
}

enum GlassesSessionError: Error, Equatable {
    case photoEncodingFailed
    case notImplemented
}
