import Foundation

enum JSONValue: Codable, Equatable {
    case string(String)
    case number(Double)
    case bool(Bool)
    case object([String: JSONValue])
    case array([JSONValue])
    case null

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
        } else if let value = try? container.decode(Bool.self) {
            self = .bool(value)
        } else if let value = try? container.decode(Double.self) {
            self = .number(value)
        } else if let value = try? container.decode(String.self) {
            self = .string(value)
        } else if let value = try? container.decode([JSONValue].self) {
            self = .array(value)
        } else {
            self = .object(try container.decode([String: JSONValue].self))
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let value):
            try container.encode(value)
        case .number(let value):
            try container.encode(value)
        case .bool(let value):
            try container.encode(value)
        case .object(let value):
            try container.encode(value)
        case .array(let value):
            try container.encode(value)
        case .null:
            try container.encodeNil()
        }
    }
}

enum ClientMessage: Codable, Equatable {
    case hello(Hello)
    case audio(AudioFrame)
    case audioEnd
    case photo(PhotoFrame)
    case text(TextMessage)
    case bargeIn
    case ping(Ping)

    private enum MessageType: String, Codable {
        case hello
        case audio
        case audioEnd = "audio_end"
        case photo
        case text
        case bargeIn = "barge_in"
        case ping
    }

    private enum CodingKeys: String, CodingKey {
        case type
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let type = try container.decode(MessageType.self, forKey: .type)
        switch type {
        case .hello:
            self = .hello(try Hello(from: decoder))
        case .audio:
            self = .audio(try AudioFrame(from: decoder))
        case .audioEnd:
            self = .audioEnd
        case .photo:
            self = .photo(try PhotoFrame(from: decoder))
        case .text:
            self = .text(try TextMessage(from: decoder))
        case .bargeIn:
            self = .bargeIn
        case .ping:
            self = .ping(try Ping(from: decoder))
        }
    }

    func encode(to encoder: Encoder) throws {
        switch self {
        case .hello(let message):
            try message.encode(to: encoder)
        case .audio(let message):
            try message.encode(to: encoder)
        case .audioEnd:
            var container = encoder.container(keyedBy: CodingKeys.self)
            try container.encode(MessageType.audioEnd, forKey: .type)
        case .photo(let message):
            try message.encode(to: encoder)
        case .text(let message):
            try message.encode(to: encoder)
        case .bargeIn:
            var container = encoder.container(keyedBy: CodingKeys.self)
            try container.encode(MessageType.bargeIn, forKey: .type)
        case .ping(let message):
            try message.encode(to: encoder)
        }
    }
}

struct Hello: Codable, Equatable {
    var client: String = "ios"
    var clientVersion: String
    var device: DeviceKind
    var sessionResume: String?
    var capabilities: Capabilities

    enum CodingKeys: String, CodingKey {
        case type
        case client
        case clientVersion = "client_version"
        case device
        case sessionResume = "session_resume"
        case capabilities
    }

    init(
        clientVersion: String = "0.1.0",
        device: DeviceKind = .iphoneMock,
        sessionResume: String? = nil,
        capabilities: Capabilities = .allEnabled
    ) {
        self.clientVersion = clientVersion
        self.device = device
        self.sessionResume = sessionResume
        self.capabilities = capabilities
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        client = try container.decodeIfPresent(String.self, forKey: .client) ?? "ios"
        clientVersion = try container.decode(String.self, forKey: .clientVersion)
        device = try container.decode(DeviceKind.self, forKey: .device)
        sessionResume = try container.decodeIfPresent(String.self, forKey: .sessionResume)
        capabilities = try container.decode(Capabilities.self, forKey: .capabilities)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode("hello", forKey: .type)
        try container.encode(client, forKey: .client)
        try container.encode(clientVersion, forKey: .clientVersion)
        try container.encode(device, forKey: .device)
        try container.encodeIfPresent(sessionResume, forKey: .sessionResume)
        try container.encode(capabilities, forKey: .capabilities)
    }
}

enum DeviceKind: String, Codable, Equatable {
    case iphoneMock = "iphone-mock"
    case iphoneReal = "iphone-real"
    case iphoneNoGlasses = "iphone-no-glasses"
}

struct Capabilities: Codable, Equatable {
    var audioIn: Bool
    var audioOut: Bool
    var photo: Bool
    var bargeIn: Bool

    static let allEnabled = Capabilities(audioIn: true, audioOut: true, photo: true, bargeIn: true)

    enum CodingKeys: String, CodingKey {
        case audioIn = "audio_in"
        case audioOut = "audio_out"
        case photo
        case bargeIn = "barge_in"
    }
}

struct AudioFrame: Codable, Equatable {
    var pcmBase64: String
    var sampleRate: Int
    var timestampMs: Int64?

    enum CodingKeys: String, CodingKey {
        case type
        case pcmBase64 = "pcm_b64"
        case sampleRate = "sample_rate"
        case timestampMs = "ts_ms"
    }

    init(pcmBase64: String, sampleRate: Int = 16_000, timestampMs: Int64? = nil) {
        self.pcmBase64 = pcmBase64
        self.sampleRate = sampleRate
        self.timestampMs = timestampMs
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        pcmBase64 = try container.decode(String.self, forKey: .pcmBase64)
        sampleRate = try container.decode(Int.self, forKey: .sampleRate)
        timestampMs = try container.decodeIfPresent(Int64.self, forKey: .timestampMs)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode("audio", forKey: .type)
        try container.encode(pcmBase64, forKey: .pcmBase64)
        try container.encode(sampleRate, forKey: .sampleRate)
        try container.encodeIfPresent(timestampMs, forKey: .timestampMs)
    }
}

struct PhotoFrame: Codable, Equatable {
    var jpegBase64: String
    var trigger: PhotoTrigger
    var toolCallID: String?
    var timestampMs: Int64

    enum CodingKeys: String, CodingKey {
        case type
        case jpegBase64 = "jpeg_b64"
        case trigger
        case toolCallID = "tool_call_id"
        case timestampMs = "ts_ms"
    }

    init(jpegBase64: String, trigger: PhotoTrigger, toolCallID: String? = nil, timestampMs: Int64 = monotonicMilliseconds()) {
        self.jpegBase64 = jpegBase64
        self.trigger = trigger
        self.toolCallID = toolCallID
        self.timestampMs = timestampMs
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        jpegBase64 = try container.decode(String.self, forKey: .jpegBase64)
        trigger = try container.decode(PhotoTrigger.self, forKey: .trigger)
        toolCallID = try container.decodeIfPresent(String.self, forKey: .toolCallID)
        timestampMs = try container.decode(Int64.self, forKey: .timestampMs)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode("photo", forKey: .type)
        try container.encode(jpegBase64, forKey: .jpegBase64)
        try container.encode(trigger, forKey: .trigger)
        try container.encodeIfPresent(toolCallID, forKey: .toolCallID)
        try container.encode(timestampMs, forKey: .timestampMs)
    }
}

enum PhotoTrigger: String, Codable, Equatable {
    case auto
    case userRequest = "user_request"
    case toolLook = "tool_look"
}

struct TextMessage: Codable, Equatable {
    var text: String

    enum CodingKeys: String, CodingKey {
        case type
        case text
    }

    init(text: String) {
        self.text = text
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        text = try container.decode(String.self, forKey: .text)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode("text", forKey: .type)
        try container.encode(text, forKey: .text)
    }
}

struct Ping: Codable, Equatable {
    var timestampMs: Int64

    enum CodingKeys: String, CodingKey {
        case type
        case timestampMs = "ts_ms"
    }

    init(timestampMs: Int64 = monotonicMilliseconds()) {
        self.timestampMs = timestampMs
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        timestampMs = try container.decode(Int64.self, forKey: .timestampMs)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode("ping", forKey: .type)
        try container.encode(timestampMs, forKey: .timestampMs)
    }
}

enum ServerMessage: Codable, Equatable {
    case ready(Ready)
    case sessionUpdate(SessionUpdate)
    case audioChunk(AudioChunk)
    case transcriptIn(InputTranscript)
    case transcriptOut(OutputTranscript)
    case toolEvent(ToolEvent)
    case lookRequest(LookRequest)
    case modelInterrupt(ModelInterrupt)
    case pong(Pong)
    case error(ServerErrorMessage)
    case sessionEnd(SessionEnd)
    case echo(EchoMessage)
    case unknown(type: String, payload: JSONValue)

    private enum CodingKeys: String, CodingKey {
        case type
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let type = try container.decode(String.self, forKey: .type)
        switch type {
        case "ready":
            self = .ready(try Ready(from: decoder))
        case "session_update":
            self = .sessionUpdate(try SessionUpdate(from: decoder))
        case "audio_chunk":
            self = .audioChunk(try AudioChunk(from: decoder))
        case "transcript_in":
            self = .transcriptIn(try InputTranscript(from: decoder))
        case "transcript_out":
            self = .transcriptOut(try OutputTranscript(from: decoder))
        case "tool_event":
            self = .toolEvent(try ToolEvent(from: decoder))
        case "look_request":
            self = .lookRequest(try LookRequest(from: decoder))
        case "model_interrupt":
            self = .modelInterrupt(try ModelInterrupt(from: decoder))
        case "pong":
            self = .pong(try Pong(from: decoder))
        case "error":
            self = .error(try ServerErrorMessage(from: decoder))
        case "session_end":
            self = .sessionEnd(try SessionEnd(from: decoder))
        case "echo":
            self = .echo(try EchoMessage(from: decoder))
        default:
            self = .unknown(type: type, payload: try JSONValue(from: decoder))
        }
    }

    func encode(to encoder: Encoder) throws {
        switch self {
        case .ready(let message):
            try message.encode(to: encoder)
        case .sessionUpdate(let message):
            try message.encode(to: encoder)
        case .audioChunk(let message):
            try message.encode(to: encoder)
        case .transcriptIn(let message):
            try message.encode(to: encoder)
        case .transcriptOut(let message):
            try message.encode(to: encoder)
        case .toolEvent(let message):
            try message.encode(to: encoder)
        case .lookRequest(let message):
            try message.encode(to: encoder)
        case .modelInterrupt(let message):
            try message.encode(to: encoder)
        case .pong(let message):
            try message.encode(to: encoder)
        case .error(let message):
            try message.encode(to: encoder)
        case .sessionEnd(let message):
            try message.encode(to: encoder)
        case .echo(let message):
            try message.encode(to: encoder)
        case .unknown(_, let payload):
            try payload.encode(to: encoder)
        }
    }
}

struct Ready: Codable, Equatable {
    var sessionID: String
    var sessionResumeToken: String?
    var resumed: Bool
    var model: String

    enum CodingKeys: String, CodingKey {
        case type
        case sessionID = "session_id"
        case sessionResumeToken = "session_resume_token"
        case resumed
        case model
    }

    init(sessionID: String, sessionResumeToken: String?, resumed: Bool, model: String) {
        self.sessionID = sessionID
        self.sessionResumeToken = sessionResumeToken
        self.resumed = resumed
        self.model = model
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        sessionID = try container.decode(String.self, forKey: .sessionID)
        sessionResumeToken = try container.decodeIfPresent(String.self, forKey: .sessionResumeToken)
        resumed = try container.decode(Bool.self, forKey: .resumed)
        model = try container.decode(String.self, forKey: .model)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode("ready", forKey: .type)
        try container.encode(sessionID, forKey: .sessionID)
        try container.encodeIfPresent(sessionResumeToken, forKey: .sessionResumeToken)
        try container.encode(resumed, forKey: .resumed)
        try container.encode(model, forKey: .model)
    }
}

struct SessionUpdate: Codable, Equatable {
    var sessionResumeToken: String

    enum CodingKeys: String, CodingKey {
        case type
        case sessionResumeToken = "session_resume_token"
    }

    init(sessionResumeToken: String) {
        self.sessionResumeToken = sessionResumeToken
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        sessionResumeToken = try container.decode(String.self, forKey: .sessionResumeToken)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode("session_update", forKey: .type)
        try container.encode(sessionResumeToken, forKey: .sessionResumeToken)
    }
}

struct AudioChunk: Codable, Equatable {
    var pcmBase64: String
    var sampleRate: Int
    var turnID: String

    enum CodingKeys: String, CodingKey {
        case type
        case pcmBase64 = "pcm_b64"
        case sampleRate = "sample_rate"
        case turnID = "turn_id"
    }

    init(pcmBase64: String, sampleRate: Int = 24_000, turnID: String) {
        self.pcmBase64 = pcmBase64
        self.sampleRate = sampleRate
        self.turnID = turnID
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        pcmBase64 = try container.decode(String.self, forKey: .pcmBase64)
        sampleRate = try container.decode(Int.self, forKey: .sampleRate)
        turnID = try container.decode(String.self, forKey: .turnID)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode("audio_chunk", forKey: .type)
        try container.encode(pcmBase64, forKey: .pcmBase64)
        try container.encode(sampleRate, forKey: .sampleRate)
        try container.encode(turnID, forKey: .turnID)
    }
}

struct InputTranscript: Codable, Equatable {
    var text: String
    var isFinal: Bool
    var timestampMs: Int64?

    enum CodingKeys: String, CodingKey {
        case type
        case text
        case isFinal = "is_final"
        case timestampMs = "ts_ms"
    }

    init(text: String, isFinal: Bool, timestampMs: Int64? = nil) {
        self.text = text
        self.isFinal = isFinal
        self.timestampMs = timestampMs
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        text = try container.decode(String.self, forKey: .text)
        isFinal = try container.decode(Bool.self, forKey: .isFinal)
        timestampMs = try container.decodeIfPresent(Int64.self, forKey: .timestampMs)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode("transcript_in", forKey: .type)
        try container.encode(text, forKey: .text)
        try container.encode(isFinal, forKey: .isFinal)
        try container.encodeIfPresent(timestampMs, forKey: .timestampMs)
    }
}

struct OutputTranscript: Codable, Equatable {
    var text: String
    var turnID: String
    var isFinal: Bool

    enum CodingKeys: String, CodingKey {
        case type
        case text
        case turnID = "turn_id"
        case isFinal = "is_final"
    }

    init(text: String, turnID: String, isFinal: Bool) {
        self.text = text
        self.turnID = turnID
        self.isFinal = isFinal
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        text = try container.decode(String.self, forKey: .text)
        turnID = try container.decode(String.self, forKey: .turnID)
        isFinal = try container.decode(Bool.self, forKey: .isFinal)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode("transcript_out", forKey: .type)
        try container.encode(text, forKey: .text)
        try container.encode(turnID, forKey: .turnID)
        try container.encode(isFinal, forKey: .isFinal)
    }
}

struct ToolEvent: Codable, Equatable, Identifiable {
    var id: String { toolCallID }
    var toolCallID: String
    var name: ToolName
    var phase: ToolPhase
    var args: [String: JSONValue]?
    var resultSummary: String?
    var error: String?

    enum CodingKeys: String, CodingKey {
        case type
        case toolCallID = "tool_call_id"
        case name
        case phase
        case args
        case resultSummary = "result_summary"
        case error
    }

    init(
        toolCallID: String,
        name: ToolName,
        phase: ToolPhase,
        args: [String: JSONValue]? = nil,
        resultSummary: String? = nil,
        error: String? = nil
    ) {
        self.toolCallID = toolCallID
        self.name = name
        self.phase = phase
        self.args = args
        self.resultSummary = resultSummary
        self.error = error
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        toolCallID = try container.decode(String.self, forKey: .toolCallID)
        name = try container.decode(ToolName.self, forKey: .name)
        phase = try container.decode(ToolPhase.self, forKey: .phase)
        args = try container.decodeIfPresent([String: JSONValue].self, forKey: .args)
        resultSummary = try container.decodeIfPresent(String.self, forKey: .resultSummary)
        error = try container.decodeIfPresent(String.self, forKey: .error)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode("tool_event", forKey: .type)
        try container.encode(toolCallID, forKey: .toolCallID)
        try container.encode(name, forKey: .name)
        try container.encode(phase, forKey: .phase)
        try container.encodeIfPresent(args, forKey: .args)
        try container.encodeIfPresent(resultSummary, forKey: .resultSummary)
        try container.encodeIfPresent(error, forKey: .error)
    }
}

enum ToolName: String, Codable, Equatable {
    case agent
    case look
    case remember
    case recall
}

enum ToolPhase: String, Codable, Equatable {
    case started
    case result
    case error
}

struct LookRequest: Codable, Equatable {
    var toolCallID: String
    var reason: String

    enum CodingKeys: String, CodingKey {
        case type
        case toolCallID = "tool_call_id"
        case reason
    }

    init(toolCallID: String, reason: String) {
        self.toolCallID = toolCallID
        self.reason = reason
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        toolCallID = try container.decode(String.self, forKey: .toolCallID)
        reason = try container.decode(String.self, forKey: .reason)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode("look_request", forKey: .type)
        try container.encode(toolCallID, forKey: .toolCallID)
        try container.encode(reason, forKey: .reason)
    }
}

struct ModelInterrupt: Codable, Equatable {
    var turnID: String

    enum CodingKeys: String, CodingKey {
        case type
        case turnID = "turn_id"
    }

    init(turnID: String) {
        self.turnID = turnID
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        turnID = try container.decode(String.self, forKey: .turnID)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode("model_interrupt", forKey: .type)
        try container.encode(turnID, forKey: .turnID)
    }
}

struct Pong: Codable, Equatable {
    var clientTimestampMs: Int64
    var serverTimestampMs: Int64

    enum CodingKeys: String, CodingKey {
        case type
        case clientTimestampMs = "ts_ms_client"
        case serverTimestampMs = "ts_ms_server"
    }

    init(clientTimestampMs: Int64, serverTimestampMs: Int64) {
        self.clientTimestampMs = clientTimestampMs
        self.serverTimestampMs = serverTimestampMs
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        clientTimestampMs = try container.decode(Int64.self, forKey: .clientTimestampMs)
        serverTimestampMs = try container.decode(Int64.self, forKey: .serverTimestampMs)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode("pong", forKey: .type)
        try container.encode(clientTimestampMs, forKey: .clientTimestampMs)
        try container.encode(serverTimestampMs, forKey: .serverTimestampMs)
    }
}

struct ServerErrorMessage: Codable, Equatable {
    var code: String?
    var message: String
    var fatal: Bool?

    enum CodingKeys: String, CodingKey {
        case type
        case code
        case message
        case fatal
    }

    init(code: String? = nil, message: String, fatal: Bool? = nil) {
        self.code = code
        self.message = message
        self.fatal = fatal
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        code = try container.decodeIfPresent(String.self, forKey: .code)
        message = try container.decode(String.self, forKey: .message)
        fatal = try container.decodeIfPresent(Bool.self, forKey: .fatal)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode("error", forKey: .type)
        try container.encodeIfPresent(code, forKey: .code)
        try container.encode(message, forKey: .message)
        try container.encodeIfPresent(fatal, forKey: .fatal)
    }
}

struct SessionEnd: Codable, Equatable {
    var reason: String

    enum CodingKeys: String, CodingKey {
        case type
        case reason
    }

    init(reason: String) {
        self.reason = reason
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        reason = try container.decode(String.self, forKey: .reason)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode("session_end", forKey: .type)
        try container.encode(reason, forKey: .reason)
    }
}

struct EchoMessage: Codable, Equatable {
    var received: JSONValue

    enum CodingKeys: String, CodingKey {
        case type
        case received
    }

    init(received: JSONValue) {
        self.received = received
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        received = try container.decode(JSONValue.self, forKey: .received)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode("echo", forKey: .type)
        try container.encode(received, forKey: .received)
    }
}

func monotonicMilliseconds() -> Int64 {
    Int64(ProcessInfo.processInfo.systemUptime * 1000)
}
