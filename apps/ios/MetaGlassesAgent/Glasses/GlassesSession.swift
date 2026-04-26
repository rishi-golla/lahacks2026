import UIKit

enum GlassesState: Equatable {
    case stopped
    case connecting
    case ready
    case streaming
    case paused
    case error(String)
}

@MainActor
protocol GlassesSession: AnyObject {
    var stateStream: AsyncStream<GlassesState> { get }

    func start() async throws
    func stop() async
    func capturePhoto() async throws -> Data
    func videoFrames(at fps: Double) -> AsyncStream<UIImage>
}

enum GlassesSessionError: Error, Equatable {
    case photoEncodingFailed
    case deviceSessionUnavailable
    /// `addStream` failed while starting the glasses session (SDK / device issue).
    case streamSessionUnavailable
    /// No active `StreamSession` — e.g. \"Capture photo\" before **Start Assistant** or after **Stop**.
    case cameraStreamNotRunning
    case photoCaptureRejected
    case photoCaptureTimedOut
    case cameraPermissionDenied
    case cameraPermissionUnavailable(String)
    case notImplemented
    /// `UIImage` could not read bytes from the glasses (often truncated or non-JPEG data).
    case photoDecodeFailed(byteCount: Int)
}

extension GlassesSessionError: LocalizedError {
    var errorDescription: String? {
        switch self {
        case .photoEncodingFailed:
            return "Could not encode photo JPEG."
        case .deviceSessionUnavailable:
            return "Could not start a glasses device session."
        case .streamSessionUnavailable:
            return "Could not start a glasses camera stream (addStream failed during session start)."
        case .cameraStreamNotRunning:
            return "The glasses camera stream is not running. Tap Start Assistant and wait until the session is live, then try Capture photo again."
        case .photoCaptureRejected:
            return "The glasses camera rejected the photo capture request."
        case .photoCaptureTimedOut:
            return "Timed out waiting for a glasses photo."
        case .cameraPermissionDenied:
            return "Camera permission is not granted for the glasses. Open Debug controls, register DAT if needed, then request camera permission."
        case .cameraPermissionUnavailable(let message):
            return "Could not check glasses camera permission: \(message). Make sure Bluetooth is on, the glasses are paired, and DAT registration is granted."
        case .notImplemented:
            return "This glasses feature is not implemented yet."
        case .photoDecodeFailed(let n):
            return "Could not decode photo from glasses (\(n) bytes). The capture may be truncated or corrupt."
        }
    }
}
