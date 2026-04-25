import MWDATMockDevice
import UIKit

@MainActor
final class MockGlassesSession: GlassesSession {
    private let continuation: AsyncStream<GlassesState>.Continuation
    let stateStream: AsyncStream<GlassesState>
    private var mockDevice: MockRaybanMeta?

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
        let camera = device.services.camera
        if let videoURL = Bundle.main.url(forResource: "mock-pov", withExtension: "mp4") {
            camera.setCameraFeed(fileURL: videoURL)
        }
        let imageURL = try Self.mockCapturedImageURL()
        camera.setCapturedImage(fileURL: imageURL)
        device.powerOn()
        device.unfold()
        device.don()
        mockDevice = device
        #endif

        continuation.yield(.ready)
    }

    func stop() async {
        #if DEBUG
        mockDevice = nil
        MockDeviceKit.shared.disable()
        #endif

        continuation.yield(.stopped)
    }

    func capturePhoto() async throws -> Data {
        try Data(contentsOf: Self.mockCapturedImageURL())
    }

    func videoFrames(at fps: Double) -> AsyncStream<UIImage> {
        AsyncStream { continuation in
            let task = Task {
                let interval = UInt64(1_000_000_000 / max(fps, 1))
                let image = try? Self.mockCapturedImage()
                while !Task.isCancelled {
                    if let image {
                        continuation.yield(image)
                    }
                    try? await Task.sleep(nanoseconds: interval)
                }
                continuation.finish()
            }

            continuation.onTermination = { _ in
                task.cancel()
            }
        }
    }

    private static func mockCapturedImageURL() throws -> URL {
        if let bundledURL = Bundle.main.url(forResource: "mock-pov", withExtension: "png") {
            return bundledURL
        }

        let image = PlaceholderPhoto.image(label: "MockDeviceKit POV")
        guard let data = image.jpegData(compressionQuality: 0.85) else {
            throw GlassesSessionError.photoEncodingFailed
        }

        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("metaglassesagent-mock-captured-image.jpg")
        try data.write(to: url, options: .atomic)
        return url
    }

    private static func mockCapturedImage() throws -> UIImage {
        let data = try Data(contentsOf: mockCapturedImageURL())
        guard let image = UIImage(data: data) else {
            return PlaceholderPhoto.image(label: "MockDeviceKit POV")
        }
        return image
    }
}
