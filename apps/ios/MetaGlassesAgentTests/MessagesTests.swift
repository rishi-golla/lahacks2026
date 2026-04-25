import XCTest

@testable import MetaGlassesAgent

final class MessagesTests: XCTestCase {
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()

    func testClientMessagesRoundTrip() throws {
        try assertRoundTrip(ClientMessage.hello(Hello(sessionResume: "resume-1")))
        try assertRoundTrip(ClientMessage.audio(AudioFrame(pcmBase64: "AAE=", sampleRate: 16_000, timestampMs: 123)))
        try assertRoundTrip(ClientMessage.audioEnd)
        try assertRoundTrip(ClientMessage.photo(PhotoFrame(jpegBase64: "/9j/", trigger: .toolLook, toolCallID: "tool-1", timestampMs: 456)))
        try assertRoundTrip(ClientMessage.text(TextMessage(text: "what time is it?")))
        try assertRoundTrip(ClientMessage.bargeIn)
        try assertRoundTrip(ClientMessage.ping(Ping(timestampMs: 789)))
    }

    func testServerMessagesRoundTrip() throws {
        try assertRoundTrip(ServerMessage.ready(Ready(sessionID: "session-1", sessionResumeToken: "resume-1", resumed: false, model: "gemini-live")))
        try assertRoundTrip(ServerMessage.sessionUpdate(SessionUpdate(sessionResumeToken: "resume-2")))
        try assertRoundTrip(ServerMessage.audioChunk(AudioChunk(pcmBase64: "AAE=", sampleRate: 24_000, turnID: "turn-1")))
        try assertRoundTrip(ServerMessage.transcriptIn(InputTranscript(text: "hello", isFinal: true, timestampMs: 111)))
        try assertRoundTrip(ServerMessage.transcriptOut(OutputTranscript(text: "hi there", turnID: "turn-1", isFinal: true)))
        try assertRoundTrip(ServerMessage.toolEvent(ToolEvent(toolCallID: "tool-1", name: .agent, phase: .started, args: ["intent": .string("buy milk")])))
        try assertRoundTrip(ServerMessage.lookRequest(LookRequest(toolCallID: "tool-2", reason: "fresh visual context")))
        try assertRoundTrip(ServerMessage.modelInterrupt(ModelInterrupt(turnID: "turn-2")))
        try assertRoundTrip(ServerMessage.pong(Pong(clientTimestampMs: 100, serverTimestampMs: 120)))
        try assertRoundTrip(ServerMessage.error(ServerErrorMessage(code: "bad_audio", message: "bad sample rate", fatal: false)))
        try assertRoundTrip(ServerMessage.sessionEnd(SessionEnd(reason: "done")))
        try assertRoundTrip(ServerMessage.echo(EchoMessage(received: .object(["type": .string("hello")]))))
    }

    func testEchoServerErrorWithoutCodeOrFatalDecodes() throws {
        let data = Data(#"{"type":"error","message":"invalid JSON"}"#.utf8)
        XCTAssertEqual(
            try decoder.decode(ServerMessage.self, from: data),
            .error(ServerErrorMessage(message: "invalid JSON"))
        )
    }

    func testUnknownServerMessageIsPreserved() throws {
        let data = Data(#"{"type":"future","value":42}"#.utf8)
        XCTAssertEqual(
            try decoder.decode(ServerMessage.self, from: data),
            .unknown(type: "future", payload: .object(["type": .string("future"), "value": .number(42)]))
        )
    }

    private func assertRoundTrip<T: Codable & Equatable>(_ value: T, file: StaticString = #filePath, line: UInt = #line) throws {
        let data = try encoder.encode(value)
        let decoded = try decoder.decode(T.self, from: data)
        XCTAssertEqual(decoded, value, file: file, line: line)
    }
}
