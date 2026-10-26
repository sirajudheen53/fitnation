# AGENTS.md - FitNation Mobile (OpenCode)

## Project: FBOS Mobile — Flutter Customer App

## Tech Stack
- Flutter (stable channel) + Dart
- GoRouter for navigation
- Dio + Retrofit for API calls
- Riverpod for state management
- Hive/Isar for local storage (offline-first)
- fl_chart for charts
- Firebase Cloud Messaging for push notifications
- cached_network_image for images
- flutter_test + integration_test for testing

## 🚨 STRICT TESTING RULE (NON-NEGOTIABLE)
- **Widget tests** for every reusable widget
- **Unit tests** for every model, service, repository, provider
- **Integration tests** for every screen/flow
- **Minimum 80% code coverage**
- Tests must be in the **same commit** as the feature
- Bug fixes: write reproducing test FIRST, then fix
- **No PR merged without passing tests in CI**

## Coding Standards
- Null safety everywhere
- Immutable data models (freezed)
- Feature-based folder structure
- No business logic in widgets
- API clients from OpenAPI spec
- Tests for all widgets and integration

## API Integration
- Backend API: see fitnation-backend repo
- Use Dio + Retrofit for all API calls
- Offline-first: cache responses in Hive/Isar
- Sync when connection restored

## Commands
```bash
# Run app
flutter run

# Run tests with coverage
flutter test --coverage

# Analyze
dart analyze

# Build
flutter build apk  # Android
flutter build ios   # iOS
```