# StudySmart mobile app

This Flutter client uses the same authenticated Flask REST API as the web application. It includes registration/sign-in, Overview, Planner, Courses, Assignments, Pomodoro Focus, Notifications and OULAD Performance screens.

## First run

1. Install Flutter and Android Studio (or Xcode on macOS).
2. In this `mobile` folder run `flutter create --platforms=android,ios .` once to generate the native runner folders.
3. Run `flutter pub get`.
4. Start the StudySmart backend, then run:
   - Android emulator: `flutter run --dart-define=API_URL=http://10.0.2.2:5000/api/v1`
   - iOS simulator: `flutter run --dart-define=API_URL=http://127.0.0.1:5000/api/v1`
   - Physical phone: replace the address with the computer's LAN address and permit Flask through the firewall.
   - Hosted release: `flutter run --dart-define=API_URL=https://YOUR-VERCEL-DOMAIN/api/v1`

The authentication token is stored using platform secure storage. Production builds must use the HTTPS Vercel address, never a local HTTP address.
