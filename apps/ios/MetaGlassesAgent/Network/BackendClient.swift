import Foundation

enum BackendClientError: Error, Equatable {
    case notConnected
    case unsupportedMessage
}

final class BackendClient {
    private let url: URL
    private let session: URLSession
    private let encoder: JSONEncoder
    private let decoder: JSONDecoder
    private var task: URLSessionWebSocketTask?

    init(url: URL, session: URLSession = .shared) {
        self.url = url
        self.session = session
        self.encoder = JSONEncoder()
        self.decoder = JSONDecoder()
    }

    func connect() async throws {
        close()
        let task = session.webSocketTask(with: url)
        self.task = task
        task.resume()
    }

    func send(_ message: ClientMessage) async throws {
        guard let task else {
            throw BackendClientError.notConnected
        }

        let data = try encoder.encode(message)
        guard let text = String(data: data, encoding: .utf8) else {
            throw BackendClientError.unsupportedMessage
        }
        try await task.send(.string(text))
    }

    func messages() -> AsyncThrowingStream<ServerMessage, Error> {
        AsyncThrowingStream { continuation in
            let receiveTask = Task {
                do {
                    while !Task.isCancelled {
                        guard let task else {
                            throw BackendClientError.notConnected
                        }

                        let raw = try await task.receive()
                        let data: Data
                        switch raw {
                        case .string(let text):
                            data = Data(text.utf8)
                        case .data(let messageData):
                            data = messageData
                        @unknown default:
                            throw BackendClientError.unsupportedMessage
                        }

                        continuation.yield(try decoder.decode(ServerMessage.self, from: data))
                    }
                } catch is CancellationError {
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }

            continuation.onTermination = { _ in
                receiveTask.cancel()
            }
        }
    }

    func close() {
        task?.cancel(with: .normalClosure, reason: nil)
        task = nil
    }
}
