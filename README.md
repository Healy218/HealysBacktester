# HealyLabs for iPhone

Open **App.xcodeproj** in Xcode. The dashboard is already built and configured
for Firebase project `stonks-22367`. No Node, npm, CocoaPods or terminal build
commands are required on this Mac.

1. Download this branch as a ZIP and unzip it.
2. Double-click `App.xcodeproj`. Allow Xcode to resolve its Swift package.
3. Select the **App** target, then **Signing & Capabilities**. Keep automatic
   signing enabled and choose your Apple development team. If needed, add your
   Apple account in Xcode Settings → Accounts. If the bundle ID is unavailable
   to your team, choose a unique one for your app.
4. Select your connected iPhone (or an iPhone simulator) and press **Run** (▶).
   Follow Xcode's device pairing/Developer Mode prompts if shown.
5. Sign in with your existing dashboard email and password.

Requires Xcode 26 or newer, the iOS SDK, and internet for initial Swift package
resolution and live dashboard data. Capacitor is pinned to 8.5.2.
Official requirements: https://capacitorjs.com/docs/getting-started/environment-setup

This branch contains the iOS app only. Its UI is bundled locally; dashboard data
comes from the existing Firebase service. Future UI changes require an updated
bundle and another Xcode build. The web dashboard remains available at
https://stonks-22367.web.app. Push notifications are not included yet.

Packaging, web production build and resource checks passed on Linux. Xcode
compilation, signing, and physical-device acceptance must be completed on a Mac.

Full editable web source: branch `ops/firebase-dashboard-20260911` in this repo.
This app-only branch is `ios/ready-to-open`; do not merge it into main.
