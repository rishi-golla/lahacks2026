import UIKit

enum PlaceholderPhoto {
    static func image(label: String) -> UIImage {
        let renderer = UIGraphicsImageRenderer(size: CGSize(width: 640, height: 480))
        return renderer.image { context in
            UIColor(red: 0.08, green: 0.1, blue: 0.14, alpha: 1).setFill()
            context.fill(CGRect(x: 0, y: 0, width: 640, height: 480))

            let paragraph = NSMutableParagraphStyle()
            paragraph.alignment = .center

            let attrs: [NSAttributedString.Key: Any] = [
                .font: UIFont.boldSystemFont(ofSize: 36),
                .foregroundColor: UIColor.white,
                .paragraphStyle: paragraph
            ]

            NSString(string: label).draw(
                in: CGRect(x: 40, y: 210, width: 560, height: 80),
                withAttributes: attrs
            )
        }
    }

    static func jpegData(label: String) throws -> Data {
        guard let data = image(label: label).jpegData(compressionQuality: 0.7) else {
            throw GlassesSessionError.photoEncodingFailed
        }
        return data
    }
}

struct PhotoCapture {
    var maxSize = CGSize(width: 640, height: 480)
    var jpegQuality: CGFloat = 0.7

    func captureJPEG(from glasses: GlassesSession) async throws -> Data {
        let data = try await glasses.capturePhoto()
        guard let image = UIImage(data: data) else {
            return data
        }
        return try resizeAndEncode(image)
    }

    func resizeAndEncode(_ image: UIImage) throws -> Data {
        let size = scaledSize(for: image.size)
        let renderer = UIGraphicsImageRenderer(size: size)
        let resized = renderer.image { _ in
            image.draw(in: CGRect(origin: .zero, size: size))
        }

        guard let data = resized.jpegData(compressionQuality: jpegQuality) else {
            throw GlassesSessionError.photoEncodingFailed
        }
        return data
    }

    private func scaledSize(for original: CGSize) -> CGSize {
        guard original.width > 0, original.height > 0 else {
            return maxSize
        }

        let scale = min(maxSize.width / original.width, maxSize.height / original.height, 1)
        return CGSize(width: original.width * scale, height: original.height * scale)
    }
}
