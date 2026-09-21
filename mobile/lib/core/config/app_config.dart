/// Build-time environment and server configuration.
///
/// Selected via ``--dart-define`` at build/run time:
///
/// ```sh
/// flutter run --dart-define=SERVER=dev          # emulator
/// flutter run --dart-define=SERVER=dev-lan      # LAN device
/// flutter run --dart-define=SERVER=cloud-dev    # GCP Cloud Run dev
/// flutter run --dart-define=SERVER=prod         # production
/// ```
///
/// Any explicit ``API_BASE_URL`` dart-define overrides the preset.
library;

/// A named server deployment.
class ServerConfig {
  const ServerConfig(this.name, this.baseUrl);

  final String name;
  final String baseUrl;

  static const ServerConfig dev = ServerConfig('dev', 'http://10.0.2.2:8000');
  static const ServerConfig devLan = ServerConfig(
    'dev-lan',
    'http://192.168.1.104:8000',
  );
  static const ServerConfig cloudDev = ServerConfig(
    'cloud-dev',
    'https://fitnation-backend-6qezqfxxla-el.a.run.app',
  );
  static const ServerConfig prod = ServerConfig('prod', 'https://api.yougetfitwithus.com');
}

/// Resolved runtime environment for this build.
class AppEnvironment {
  const AppEnvironment._();

  /// Flavor name (dev | dev-lan | cloud-dev | prod). Defaults to dev.
  static const String flavor = String.fromEnvironment(
    'SERVER',
    defaultValue: 'dev',
  );

  /// Explicit base URL override; wins over the [ServerConfig] presets.
  static const String apiBaseUrlOverride = String.fromEnvironment('API_BASE_URL');

  /// Device-bound gym anchor (tenant UUID) for phone-OTP login.
  /// Passed via --dart-define=GYM_ANCHOR=<tenant-uuid>.
  /// Per-gym builds set this to the gym's tenant UUID.
  static const String gymAnchor = String.fromEnvironment('GYM_ANCHOR');

  /// API base URL for this build.
  static String get apiBaseUrl {
    final override = apiBaseUrlOverride;
    if (override.isNotEmpty) return override;
    switch (flavor) {
      case 'dev-lan':
        return ServerConfig.devLan.baseUrl;
      case 'cloud-dev':
        return ServerConfig.cloudDev.baseUrl;
      case 'prod':
        return ServerConfig.prod.baseUrl;
      default:
        return ServerConfig.dev.baseUrl;
    }
  }
}