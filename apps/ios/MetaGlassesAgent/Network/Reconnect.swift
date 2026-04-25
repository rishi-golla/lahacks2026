import Foundation

struct ReconnectState: Equatable {
    var attempt: Int = 0
    var sessionResumeToken: String?

    mutating func reset() {
        attempt = 0
    }

    mutating func recordFailure() {
        attempt += 1
    }
}

struct ReconnectPolicy: Equatable {
    var maxAttempts: Int = 5
    var baseDelayNanoseconds: UInt64 = 250_000_000
    var maxDelayNanoseconds: UInt64 = 5_000_000_000

    func shouldRetry(attempt: Int, lastError: Error?) -> Bool {
        attempt < maxAttempts
    }

    func nextDelayNanoseconds(attempt: Int) -> UInt64 {
        guard attempt > 0 else {
            return 0
        }

        let multiplier = UInt64(1 << min(attempt - 1, 10))
        return min(baseDelayNanoseconds * multiplier, maxDelayNanoseconds)
    }
}
