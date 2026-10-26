import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/data_sources/api_client.dart';
import '../../data/data_sources/auth_local_data_source.dart';
import '../../data/data_sources/auth_remote_data_source.dart';
import '../../data/data_sources/firebase_auth_client.dart';
import '../../domain/repositories/auth_repository.dart';
import '../../services/whatsapp_otp_service.dart';
import 'auth_notifier.dart';
import 'firebase_phone_auth_notifier.dart';

/// Provides the AuthLocalDataSource singleton.
/// Initialized in main.dart before app starts, and overridden in ProviderScope.
final authLocalDataSourceProvider = Provider<AuthLocalDataSource>((ref) {
  return AuthLocalDataSource();
});

/// Provides the AuthRemoteDataSource.
final authRemoteDataSourceProvider = Provider<AuthRemoteDataSource>((ref) {
  final dio = ApiClient.getInstance();
  return AuthRemoteDataSource(dio);
});

/// Provides the Firebase phone-auth client seam.
/// Overridden with a fake in tests (no real Firebase/network/SMS).
final firebaseAuthClientProvider = Provider<FirebaseAuthClient>((ref) {
  return FirebaseAuthClientImpl(FirebaseAuth.instance);
});

/// Provides the AuthRepository.
final authRepositoryProvider = Provider<AuthRepository>((ref) {
  final remote = ref.read(authRemoteDataSourceProvider);
  final local = ref.read(authLocalDataSourceProvider);
  final firebase = ref.read(firebaseAuthClientProvider);
  return AuthRepository(remote, local, firebase);
});

/// Provides the Firebase phone-verification flow state.
final firebasePhoneAuthProvider =
    StateNotifierProvider<FirebasePhoneAuthNotifier, FirebasePhoneAuthState>((
      ref,
    ) {
      return FirebasePhoneAuthNotifier(
        ref.read(firebaseAuthClientProvider),
        ref.read(authRepositoryProvider),
        (response) {
          ref.read(authProvider.notifier).completeLogin(response);
        },
      );
    });

/// Provides the WhatsApp zero-tap OTP service seam.
/// Overridden with a fake/recorder in tests (no real platform channels).
final whatsappOtpServiceProvider = Provider<WhatsAppOtpService>((ref) {
  return WhatsAppOtpService();
});
