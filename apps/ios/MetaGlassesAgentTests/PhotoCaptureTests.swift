import XCTest
import UIKit

@testable import MetaGlassesAgent

final class PhotoCaptureTests: XCTestCase {
    func testNormalizeJPEGDataReencodesValidImageData() throws {
        let capture = PhotoCapture()
        let source = try PlaceholderPhoto.jpegData(label: "Test")

        let normalized = try capture.normalizeJPEGData(source)

        XCTAssertFalse(normalized.isEmpty)
        XCTAssertNotNil(UIImage(data: normalized))
    }

    func testNormalizeJPEGDataRejectsCorruptPayload() {
        let capture = PhotoCapture()

        XCTAssertThrowsError(try capture.normalizeJPEGData(Data([0xFF, 0xD8, 0xFF]))) { error in
            guard case GlassesSessionError.photoDecodeFailed(let byteCount) = error else {
                return XCTFail("Unexpected error: \(error)")
            }
            XCTAssertEqual(byteCount, 3)
        }
    }
}
