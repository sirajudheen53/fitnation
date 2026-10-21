import 'package:flutter_test/flutter_test.dart';

import 'package:fitnation_app/core/deeplink/join_link.dart';

void main() {
  const gymUuid = '3f7c1a2b-4d5e-6f70-8192-a3b4c5d6e7f8';
  const otherGymUuid = '11111111-2222-3333-4444-555555555555';

  group('JoinLink.tryParse — App Link (https)', () {
    test('parses the canonical app link /g/{uuid}', () {
      final link = JoinLink.tryParse(
        Uri.parse('https://app.yougetfitwithus.com/g/$gymUuid'),
      );

      expect(link, isNotNull);
      expect(link!.gymUuid, gymUuid);
      expect(link.source, JoinLinkSource.appLink);
      expect(link.inviteToken, isNull);
    });

    test('parses the api host /join?gym={uuid}&t={token}', () {
      final link = JoinLink.tryParse(
        Uri.parse(
          'https://api.yougetfitwithus.com/join?gym=$gymUuid&t=inv-123',
        ),
      );

      expect(link, isNotNull);
      expect(link!.gymUuid, gymUuid);
      expect(link.inviteToken, 'inv-123');
      expect(link.source, JoinLinkSource.appLink);
    });

    test('lowercases the gym uuid', () {
      final link = JoinLink.tryParse(
        Uri.parse('https://app.yougetfitwithus.com/g/${gymUuid.toUpperCase()}'),
      );

      expect(link!.gymUuid, gymUuid);
    });

    test('rejects an unknown host', () {
      final link = JoinLink.tryParse(
        Uri.parse('https://evil.example.com/g/$gymUuid'),
      );

      expect(link, isNull);
    });

    test('rejects a non-uuid gym segment', () {
      final link = JoinLink.tryParse(
        Uri.parse('https://app.yougetfitwithus.com/g/not-a-uuid'),
      );

      expect(link, isNull);
    });

    test('rejects an app link with no gym segment', () {
      final link = JoinLink.tryParse(
        Uri.parse('https://app.yougetfitwithus.com/g/'),
      );

      expect(link, isNull);
    });
  });

  group('JoinLink.tryParse — custom scheme', () {
    test('parses fitnation://g/{uuid}', () {
      final link = JoinLink.tryParse(
        Uri.parse('fitnation://g/$gymUuid'),
      );

      expect(link, isNotNull);
      expect(link!.gymUuid, gymUuid);
      expect(link.source, JoinLinkSource.customScheme);
    });

    test('parses fitnation://join?gym={uuid}&t={token}', () {
      final link = JoinLink.tryParse(
        Uri.parse('fitnation://join?gym=$gymUuid&t=abc'),
      );

      expect(link, isNotNull);
      expect(link!.gymUuid, gymUuid);
      expect(link.inviteToken, 'abc');
      expect(link.source, JoinLinkSource.customScheme);
    });

    test('rejects another custom scheme', () {
      final link = JoinLink.tryParse(Uri.parse('otherapp://g/$gymUuid'));

      expect(link, isNull);
    });
  });

  group('JoinLink.tryParse — rejections', () {
    test('rejects a plain http link', () {
      expect(JoinLink.tryParse(Uri.parse('http://app.yougetfitwithus.com/g/$gymUuid')), isNull);
    });

    test('rejects an unrelated app link path', () {
      expect(
        JoinLink.tryParse(Uri.parse('https://app.yougetfitwithus.com/workouts/$gymUuid')),
        isNull,
      );
    });

    test('rejects a join link with a missing gym param', () {
      expect(
        JoinLink.tryParse(Uri.parse('https://api.yougetfitwithus.com/join?t=abc')),
        isNull,
      );
    });

    test('treats an empty invite token as absent', () {
      final link = JoinLink.tryParse(
        Uri.parse('https://api.yougetfitwithus.com/join?gym=$gymUuid&t='),
      );

      expect(link!.inviteToken, isNull);
    });
  });

  test('equality is by gym, token and source', () {
    final a = JoinLink.tryParse(Uri.parse('fitnation://g/$gymUuid'));
    final b = JoinLink.tryParse(Uri.parse('fitnation://g/$gymUuid'));
    final c = JoinLink.tryParse(Uri.parse('fitnation://g/$otherGymUuid'));

    expect(a, b);
    expect(a.hashCode, b.hashCode);
    expect(a, isNot(c));
  });
}
