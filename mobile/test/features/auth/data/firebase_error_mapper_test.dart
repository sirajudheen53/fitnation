import 'package:flutter_test/flutter_test.dart';
import 'package:firebase_auth/firebase_auth.dart';

import 'package:fitnation_app/core/errors/failures.dart';
import 'package:fitnation_app/features/auth/data/firebase_error_mapper.dart';

import '../../../helpers/fakes.dart';

void main() {
  group('mapFirebaseAuthException', () {
    Failure map(String code, {String? message}) => mapFirebaseAuthException(
      FirebaseAuthException(code: code, message: message),
    );

    test('app-not-authorized → friendly setup/SHA message', () {
      final f = map('app-not-authorized');
      expect(f, isA<AuthFailure>());
      expect(f.message, contains('support'));
      expect(f.message, contains('registered'));
    });

    test('operation-not-allowed → sign-in disabled message', () {
      expectFailure(
        map('operation-not-allowed'),
        AuthFailure,
        messageContains: 'phone sign-in',
      );
    });

    test('invalid-api-key → same setup message family', () {
      expectFailure(
        map('invalid-api-key'),
        AuthFailure,
        messageContains: 'support',
      );
    });

    test('too-many-requests → rate-limit message', () {
      final f = map('too-many-requests');
      expectFailure(f, AuthFailure, messageContains: 'too many');
      expect(f.statusCode, 429);
    });

    test('quota-exceeded → SMS quota message', () {
      expectFailure(
        map('quota-exceeded'),
        AuthFailure,
        messageContains: 'quota',
      );
    });

    test('invalid-phone-number → invalid phone message', () {
      final f = map('invalid-phone-number');
      expectFailure(f, AuthFailure, messageContains: "doesn't look right");
      expect(f.statusCode, 400);
    });

    test('invalid-verification-code → wrong code message', () {
      expectFailure(
        map('invalid-verification-code'),
        AuthFailure,
        messageContains: 'incorrect',
      );
    });

    test('expired sessions → request-new-code message', () {
      for (final code in [
        'invalid-verification-id',
        'code-expired',
        'session-expired',
      ]) {
        expectFailure(map(code), AuthFailure, messageContains: 'expired');
      }
    });

    test('missing-verification-code → enter code message', () {
      expectFailure(
        map('missing-verification-code'),
        AuthFailure,
        messageContains: '6-digit',
      );
    });

    test('network-request-failed → NetworkFailure', () {
      expect(map('network-request-failed'), isA<NetworkFailure>());
    });

    test('user-disabled → disabled message', () {
      expectFailure(
        map('user-disabled'),
        AuthFailure,
        messageContains: 'disabled',
      );
    });

    test('unknown code falls back to the exception message', () {
      final f = map('weird-unknown-code', message: 'Something specific');
      expectFailure(f, AuthFailure, messageContains: 'Something specific');
    });

    test('unknown code without message → generic fallback', () {
      final f = map('weird-unknown-code');
      expectFailure(f, AuthFailure, messageContains: 'sign-in failed');
    });
  });

  group('mapFirebaseBackendFailure', () {
    test('401 → invalid/expired token message', () {
      final f = mapFirebaseBackendFailure(401, {'detail': 'bad token'});
      expectFailure(f, AuthFailure, messageContains: 'bad token');
      expect(f.statusCode, 401);
    });

    test('401 without detail → generic expired message', () {
      final f = mapFirebaseBackendFailure(401, null);
      expectFailure(f, AuthFailure, messageContains: 'could not be verified');
    });

    test('429 → rate limit message', () {
      final f = mapFirebaseBackendFailure(429, {'detail': 'slow down'});
      expectFailure(f, AuthFailure, messageContains: 'too many');
      expect(f.statusCode, 429);
    });

    test('400 with gyms list → tenant disambiguation with parsed gyms', () {
      final f = mapFirebaseBackendFailure(400, {
        'detail': 'Specify your gym to continue.',
        'gyms': [
          {'id': 1, 'name': 'Alpha Gym'},
          {'id': 2, 'name': 'Beta Gym'},
        ],
      });
      expect(f, isA<TenantSelectionRequiredFailure>());
      final tenant = f as TenantSelectionRequiredFailure;
      expect(tenant.message, contains('Specify your gym'));
      expect(tenant.gyms.length, 2);
      expect(tenant.gyms[0].id, '1');
      expect(tenant.gyms[0].name, 'Alpha Gym');
      expect(tenant.gyms[1].id, '2');
    });

    test('400 with gym_required code → tenant disambiguation', () {
      final f = mapFirebaseBackendFailure(400, {
        'code': 'gym_required',
        'detail': 'Pick a gym',
      });
      expect(f, isA<TenantSelectionRequiredFailure>());
      expect((f as TenantSelectionRequiredFailure).message, 'Pick a gym');
    });

    test('403 without gym payload → AuthFailure', () {
      final f = mapFirebaseBackendFailure(403, null);
      expectFailure(f, AuthFailure, messageContains: 'not allowed');
    });

    test('500 → server failure with friendly message', () {
      final f = mapFirebaseBackendFailure(500, {'detail': 'boom'});
      expect(f, isA<ServerFailure>());
      expect(f.message, contains('server issue'));
      expect(f.statusCode, 500);
    });

    test('400 other payload → ValidationFailure', () {
      final f = mapFirebaseBackendFailure(400, {'detail': 'nope'});
      expect(f, isA<ValidationFailure>());
      expect(f.message, 'nope');
    });

    test('non-map payload handled without crashing', () {
      final f = mapFirebaseBackendFailure(400, 'plain error');
      expect(f, isA<ValidationFailure>());
    });
  });

  group('GymOption.fromJson', () {
    test('parses id/name maps', () {
      final gym = GymOption.fromJson({'id': 3, 'name': 'Gamma'});
      expect(gym.id, '3');
      expect(gym.name, 'Gamma');
    });

    test('parses bare ids with fallback name', () {
      final gym = GymOption.fromJson(9);
      expect(gym.id, '9');
      expect(gym.name, '9');
    });

    test('equality by id', () {
      expect(GymOption(id: '1', name: 'A'), GymOption(id: '1', name: 'B'));
    });
  });
}
