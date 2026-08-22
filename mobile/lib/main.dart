import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hive_flutter/hive_flutter.dart';

import 'core/theme/app_theme.dart';
import 'features/auth/data/data_sources/auth_local_data_source.dart';
import 'features/auth/presentation/providers/auth_providers.dart';
import 'features/auth/presentation/providers/auth_notifier.dart';
import 'router/app_router.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize Hive for local storage
  await Hive.initFlutter();
  final localDataSource = AuthLocalDataSource();
  await localDataSource.init();

  runApp(
    ProviderScope(
      overrides: [
        // Pre-initialized local data source
        authLocalDataSourceProvider.overrideWithValue(localDataSource),
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

class _FitNationAppState extends ConsumerState<FitNationApp> {
  @override
  void initState() {
    super.initState();
    // Initialize auth state from local storage
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(authProvider.notifier).init();
    });
  }

  @override
  Widget build(BuildContext context) {
    final router = ref.watch(routerProvider);

    return MaterialApp.router(
      title: 'FitNation',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      routerConfig: router,
    );
  }
}