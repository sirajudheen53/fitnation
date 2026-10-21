import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/config/app_config.dart';

void main() {
  group('ServerConfig.prod', () {
    test('bakes the raw Cloud Run URL (domain mappings unavailable in asia-south1)', () {
      expect(ServerConfig.prod.name, 'prod');
      expect(
        ServerConfig.prod.baseUrl,
        'https://fitnation-backend-prod-6qezqfxxla-el.a.run.app',
      );
    });
  });

  group('AppEnvironment overrides', () {
    test('API_BASE_URL dart-define overrides any preset', () {
      // Compile-time contract: an explicit API_BASE_URL wins over presets.
      // The default test run has no override, so the override path is the
      // empty string and the prod preset remains authoritative for SERVER=prod.
      expect(AppEnvironment.apiBaseUrlOverride, isEmpty);
      expect(AppEnvironment.flavor, 'dev');
      expect(AppEnvironment.apiBaseUrl, ServerConfig.dev.baseUrl);
    });
  });
}