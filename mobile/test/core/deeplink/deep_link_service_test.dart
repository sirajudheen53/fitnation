import 'dart:async';
import 'dart:io';

import 'package:app_links/app_links.dart';
import 'package:app_links_platform_interface/app_links_platform_interface.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hive/hive.dart';

import 'package:fitnation_app/core/anchor/anchor_store.dart';
import 'package:fitnation_app/core/deeplink/deep_link_service.dart';
import 'package:fitnation_app/core/deeplink/join_link.dart';

/// Fake [AppLinksPlatform] so the cold-start link and the warm-link stream
/// can be driven from a test. `AppLinks` is a singleton that delegates to
/// this platform, so overriding the instance is enough to fake both.
///
/// One instance is shared by the whole file: `AppLinks` caches its stream
/// controller against the platform that was installed when the controller
/// was first created, so swapping the platform per test would leave the
/// cached controller bound to a dead stream.
class _FakeAppLinksPlatform extends AppLinksPlatform {
  Uri? initialLink;
  final StreamController<Uri> warmLinks = StreamController<Uri>.broadcast();

  @override
  Future<Uri?> getInitialLink() async => initialLink;

  @override
  Stream<Uri> get uriLinkStream => warmLinks.stream;

  @override
  Stream<String> get stringLinkStream => const Stream<String>.empty();
}

void main() {
  late Directory hiveDir;
  late Box<String> box;
  late AnchorStore store;

  final platform = _FakeAppLinksPlatform();

  const gymA = '3f7c1a2b-4d5e-6f70-8192-a3b4c5d6e7f8';
  const gymB = '11111111-2222-3333-4444-555555555555';

  setUpAll(() {
    AppLinksPlatform.instance = platform;
  });

  setUp(() async {
    hiveDir = await Directory.systemTemp.createTemp('deep_link_test');
    Hive.init(hiveDir.path);
    box = await Hive.openBox<String>('anchor_box_dl_test');
    store = AnchorStore(box: box);
    platform.initialLink = null;
  });

  tearDown(() async {
    await box.close();
    await hiveDir.delete(recursive: true);
  });

  /// Builds a service. `withLinks: false` leaves the AppLinks client out so
  /// the link-reading paths can be exercised in isolation.
  DeepLinkService build({
    bool withLinks = false,
    Future<String?> Function()? readInstallReferrer,
    Future<bool> Function(JoinLink link)? confirmSwitch,
  }) {
    return DeepLinkService(
      anchorStore: store,
      appLinks: withLinks ? AppLinks() : null,
      readInstallReferrer: readInstallReferrer,
      confirmSwitch: confirmSwitch,
    );
  }

  group('handleLink', () {
    test('captures the gym from the App Link shape', () async {
      final service = build();

      final captured = await service.handleLink(
        Uri.parse('https://app.yougetfitwithus.com/g/$gymA'),
      );

      expect(captured, isTrue);
      expect(store.runtimeGymUuid, gymA);
    });

    test('captures the gym from the custom scheme shape', () async {
      final service = build();

      final captured = await service.handleLink(
        Uri.parse('fitnation://g/$gymA'),
      );

      expect(captured, isTrue);
      expect(store.runtimeGymUuid, gymA);
    });

    test('captures the invite token when the link carries one', () async {
      final service = build();

      await service.handleLink(
        Uri.parse('https://api.yougetfitwithus.com/join?gym=$gymA&t=inv-7'),
      );

      expect(store.inviteToken, 'inv-7');
    });

    test('ignores a link that is not a join link', () async {
      final service = build();

      final captured = await service.handleLink(
        Uri.parse('https://example.com/something'),
      );

      expect(captured, isFalse);
      expect(store.runtimeGymUuid, isNull);
    });
  });

  group('install referrer', () {
    test('captures the gym from a URL-encoded referrer', () async {
      final service = build(
        readInstallReferrer: () async => 'gym%3D$gymA',
      );

      final captured = await service.handleInstallReferrer('gym%3D$gymA');

      expect(captured, isTrue);
      expect(store.runtimeGymUuid, gymA);
    });

    test('captures the gym from a plain referrer', () async {
      final service = build();

      final captured = await service.handleInstallReferrer('gym=$gymA');

      expect(captured, isTrue);
      expect(store.runtimeGymUuid, gymA);
    });

    test('ignores a referrer with no gym', () async {
      final service = build();

      final captured = await service.handleInstallReferrer('utm_source=play');

      expect(captured, isFalse);
      expect(store.runtimeGymUuid, isNull);
    });

    test('a real link wins over the referrer', () async {
      final service = build();

      // A link arrives first (warm link / cold start)…
      await service.handleLink(Uri.parse('fitnation://g/$gymA'));
      // …then the referrer is processed: it must not overwrite the link.
      final captured = await service.handleInstallReferrer('gym%3D$gymB');

      expect(captured, isFalse);
      expect(store.runtimeGymUuid, gymA);
    });
  });

  group('anchor precedence (runtime over build-time)', () {
    test('effectiveAnchor returns the runtime anchor when one exists', () async {
      final service = build();
      await service.handleLink(Uri.parse('fitnation://g/$gymA'));

      expect(service.effectiveAnchor(gymB), gymA);
    });

    test('effectiveAnchor falls back to the build-time anchor', () {
      final service = build();

      expect(service.effectiveAnchor(gymB), gymB);
    });

    test('effectiveAnchor is null when neither exists', () {
      final service = build();

      expect(service.effectiveAnchor(''), isNull);
    });

    test('hasRuntimeAnchor reflects the captured state', () async {
      final service = build();
      expect(service.hasRuntimeAnchor, isFalse);

      await service.handleLink(Uri.parse('fitnation://g/$gymA'));

      expect(service.hasRuntimeAnchor, isTrue);
    });
  });

  group('gym switch confirmation', () {
    test('a confirmed switch overwrites the anchor', () async {
      var asked = 0;
      final service = build(
        confirmSwitch: (link) async {
          asked++;
          return true;
        },
      );
      await service.handleLink(Uri.parse('fitnation://g/$gymA'));

      final captured = await service.handleLink(
        Uri.parse('fitnation://g/$gymB'),
      );

      expect(asked, 2);
      expect(captured, isTrue);
      expect(store.runtimeGymUuid, gymB);
    });

    test('a declined switch keeps the old anchor', () async {
      var asked = 0;
      final service = build(
        confirmSwitch: (link) async {
          asked++;
          // Confirm the first capture, decline the switch to the other gym.
          return asked == 1;
        },
      );
      await service.handleLink(Uri.parse('fitnation://g/$gymA'));

      final captured = await service.handleLink(
        Uri.parse('fitnation://g/$gymB'),
      );

      expect(asked, 2);
      expect(captured, isFalse);
      expect(store.runtimeGymUuid, gymA);
    });
  });

  group('init', () {
    test('captures the cold-start link', () async {
      platform.initialLink = Uri.parse('https://app.yougetfitwithus.com/g/$gymA');

      final service = build(withLinks: true);
      await service.init();
      await service.dispose();

      expect(store.runtimeGymUuid, gymA);
    });

    test('captures a warm link delivered after init', () async {
      final service = build(withLinks: true);
      await service.init();

      platform.warmLinks.add(Uri.parse('fitnation://g/$gymA'));
      await Future<void>.delayed(Duration.zero);

      expect(store.runtimeGymUuid, gymA);
      await service.dispose();
    });

    test('reads the install referrer and stores the gym', () async {
      final service = build(
        readInstallReferrer: () async => 'gym%3D$gymA',
      );

      await service.init();

      expect(store.runtimeGymUuid, gymA);
    });

    test('the referrer does not overwrite a runtime anchor', () async {
      await store.save(gymUuid: gymA);

      final service = build(
        readInstallReferrer: () async => 'gym%3D$gymB',
      );
      await service.init();

      expect(store.runtimeGymUuid, gymA);
    });
  });
}
