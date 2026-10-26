# FitNation Mobile

> FBOS Mobile — Flutter customer app for the Fitness Business Operating System
> Workout tracking, diet plans, bookings, progress, chat, push notifications

## Tech Stack
- **Framework:** Flutter (stable channel) + Dart
- **Navigation:** GoRouter
- **Networking:** Dio + Retrofit
- **State:** Riverpod
- **Local Storage:** Hive/Isar (offline-first)
- **Charts:** fl_chart
- **Push Notifications:** Firebase Cloud Messaging
- **Testing:** flutter_test, integration_test

## Getting Started
```bash
flutter pub get
flutter run
```

## Authentication

Phone-OTP login via **Firebase** (project `yougetfitwithus`): `PhoneInputScreen`
→ `FirebaseAuth.verifyPhoneNumber` (Android auto-SMS-retrieval when available)
→ `OtpVerifyScreen` → Firebase ID token → `POST /api/v1/auth/firebase/` →
session stored in Hive (same shape as the legacy OTP flow).

### Rollback to backend OTP
The legacy backend OTP flow (`/auth/otp/request/` + `/auth/otp/verify/`) stays
compiled and reachable behind a feature flag:

```bash
flutter run --dart-define=FBOS_USE_FIREBASE_AUTH=false
```

(The flag lives in `lib/core/constants/app_constants.dart`, default: Firebase.)

## API base URL

The API base URL is injectable at build time — no code changes needed for
devices to hit the real server:

```bash
# Android emulator (default): host loopback
flutter run

# Real server (device builds, staging, prod)
flutter run --dart-define=FBOS_API_BASE=https://<real-server>
```

Default: `http://10.0.2.2:8000` (Android emulator → host localhost).

## Firebase console setup (owner actions)

- Android app `com.fitnation.fitnation_app` registered in the Firebase project
- **Phone sign-in provider enabled**
- Debug SHA-256 registered for the debug keystore
  (`3D:3F:AE:F8:FD:32:FF:5E:FF:CD:D2:A5:C3:4C:AC:5B:A8:65:8E:9F:AA:64:32:C0:A2:6D:E0:F7:33:18:E6:EC`);
  Play-managed release keys are registered after the first Play upload
- SMS billing/quota enabled on the project

## Testing
```bash
# Run all tests with coverage
flutter test --coverage

# Run specific tests
flutter test test/features/auth/

# Analyze
dart analyze
```

## Related Repos
- Backend: https://github.com/sirajudheen53/fitnation-backend
- Frontend: https://github.com/sirajudheen53/fitnation-frontend
