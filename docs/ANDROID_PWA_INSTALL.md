# Android access

The current Android-ready deliverable is an installable PWA, not a signed APK.

## Install the PWA

1. Deploy the web app over HTTPS (or run it locally for testing).
2. Open the app URL in Chrome on Android.
3. Open Chrome's menu and choose **Install app** or **Add to Home screen**.
4. Confirm the installation. The app opens in standalone display mode.
5. Historical chart data and analysis still require the API connection; the service worker only caches the application shell.

## Native APK status

A native Android APK has not been built or signed. That requires a configured Android build environment (Android SDK/Gradle), application ID, signing key and a real-device install test. Do not treat the PWA as an APK.
