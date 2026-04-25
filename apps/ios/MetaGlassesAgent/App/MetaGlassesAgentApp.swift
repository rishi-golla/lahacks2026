import MWDATCore
import SwiftUI

@main
struct MetaGlassesAgentApp: App {
    init() {
        do {
            try Wearables.configure()
        } catch {
            #if DEBUG
            NSLog("[MetaGlassesAgent] Failed to configure Wearables SDK: \(error)")
            #endif
        }
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}
