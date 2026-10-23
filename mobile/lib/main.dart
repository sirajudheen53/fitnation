import 'dart:async';

import 'package:app_links/app_links.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:play_install_referrer/play_install_referrer.dart';

import 'core/anchor/anchor_providers.dart';
import 'core/anchor/anchor_store.dart';
import 'core/deeplink/deep_link_service.dart';
import 'core/deeplink/join_link.dart';
import 'core/preferences/dial_code_providers.dart';
import 'core/preferences/dial_code_store.dart';
import 'core/theme/app_theme.dart';
import 'features/auth/data/data_sources/api_client.dart';
import 'features/auth/data/data_sources/auth_local_data_source.dart';
import 'features/auth/presentation/providers/auth_notifier.dart';
import 'features/auth/presentation/providers/auth_providers.dart';
import 'features/notifications/providers/notification_providers.dart';
import 'router/app_router.dart';

/// Re-validation throttle for the entitlement check on app resume
/// (FBOS-011 §7.2: no more often than every 15 minutes).
const _entitlementResumeThrottle = Duration(minutes: 15);

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize Hive for local storage
  await Hive.initFlutter();
  final localDataSource = AuthLocalDataSource();
  await localDataSource.init();
  final anchorStore = AnchorStore();
  await anchorStore.init();
  // Last-selected dial code for the phone input (issue #69).
  final dialCodeStore = DialCodeStore();
  await dialCodeStore.init();

  // Firebase is optional: without a `google-services.json` the bootstrap
  // returns null and the app boots with push disabled (FBOS-011 M4).
  final messagingClient = await bootstrapFirebase();

  runApp(
    ProviderScope(
      overrides: [
        // Pre-initialized local data sources
        authLocalDataSourceProvider.overrideWithValue(localDataSource),
        anchorStoreProvider.overrideWithValue(anchorStore),
        dialCodeStoreProvider.overrideWithValue(dialCodeStore),
        if (messagingClient != null)
          messagingClientProvider.overrideWithValue(messagingClient),
      ],
      child: const FitNationApp(),
    ),
  );
}

class FitNationApp extends ConsumerStatefulWidget {
  const FitNationApp({super.key});

  @override
  ConsumerState<FitNationApp> createState() => _FitNationAppState();
}

class _FitNationAppState extends ConsumerState<FitNationApp>
    with WidgetsBindingObserver {
  DateTime? _lastEntitlementCheck;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);

    // Initialize auth state from local storage
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(authProvider.notifier).init();

      // Entitlement 403s from any endpoint flip the gate immediately
      // (FBOS-011 §2.4 — mid-session revocation, §9.4).
      ApiClient.onAccessDenied = (code) {
        ref.read(authProvider.notifier).applyAccessDeniedCode(code);
      };

      _initDeepLinks();
      _initPush();
    });
  }

  Future<void> _initDeepLinks() async {
    final deepLinks = DeepLinkService(
      anchorStore: ref.read(anchorStoreProvider),
      appLinks: AppLinks(),
      readInstallReferrer: () async =>
          (await PlayInstallReferrer.installReferrer).installReferrer,
      confirmSwitch: _confirmGymSwitch,
    );
    await deepLinks.init();
  }

  Future<void> _initPush() async {
    final push = ref.read(pushNotificationServiceProvider);
    push.onNavigate = (route) => ref.read(routerProvider).go(route);
    await push.initialize();
  }

  /// Multi-gym members: overwriting the device anchor while logged in needs a
  /// confirmation (FBOS-011 §7.3). Unauthenticated captures are immediate.
  Future<bool> _confirmGymSwitch(JoinLink link) async {
    final auth = ref.read(authProvider);
    if (!auth.isAuthenticated) return true;
    if (auth.entitlement?.gymUuid == link.gymUuid) return true;

    final switchConfirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Switch gym?'),
        content: const Text(
          'This invite link belongs to a different gym. '
          'Use that gym for your next sign-in?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('Switch'),
          ),
        ],
      ),
    );
    return switchConfirmed ?? false;
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    super.didChangeAppLifecycleState(state);
    if (state == AppLifecycleState.resumed) {
      _recheckEntitlement();
    }
  }

  /// Re-derives the gate state from the server on resume (throttled).
  Future<void> _recheckEntitlement() async {
    final auth = ref.read(authProvider);
    if (!auth.isAuthenticated) return;
    final last = _lastEntitlementCheck;
    if (last != null && DateTime.now().difference(last) < _entitlementResumeThrottle) {
      return;
    }
    _lastEntitlementCheck = DateTime.now();
    await ref.read(authProvider.notifier).refreshEntitlement();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    ApiClient.onAccessDenied = null;
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final router = ref.watch(routerProvider);

    // Push token lifecycle rides on auth transitions: register after login,
    // unregister on logout (FBOS-011 §7.4).
    ref.listen<AuthState>(authProvider, (previous, next) {
      final wasAuthenticated = previous?.isAuthenticated ?? false;
      final isAuthenticated = next.isAuthenticated;
      if (!wasAuthenticated && isAuthenticated) {
        ref.read(pushNotificationServiceProvider).registerCurrentToken();
      }
      if (wasAuthenticated && !isAuthenticated) {
        ref.read(pushNotificationServiceProvider).unregisterCurrentToken();
      }
    });

    return MaterialApp.router(
      title: 'FitNation',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      routerConfig: router,
    );
  }
}
