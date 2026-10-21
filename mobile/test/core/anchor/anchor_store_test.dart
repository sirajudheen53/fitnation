import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:hive/hive.dart';

import 'package:fitnation_app/core/anchor/anchor_store.dart';

void main() {
  late Directory hiveDir;
  late Box<String> box;

  const gymA = '3f7c1a2b-4d5e-6f70-8192-a3b4c5d6e7f8';
  const gymB = '11111111-2222-3333-4444-555555555555';

  setUp(() async {
    hiveDir = await Directory.systemTemp.createTemp('anchor_store_test');
    Hive.init(hiveDir.path);
    box = await Hive.openBox<String>('anchor_box_test');
  });

  tearDown(() async {
    await box.close();
    await hiveDir.delete(recursive: true);
  });

  group('runtime anchor capture', () {
    test('starts with no runtime anchor', () {
      final store = AnchorStore(box: box);

      expect(store.runtimeGymUuid, isNull);
      expect(store.inviteToken, isNull);
    });

    test('saves the gym uuid', () async {
      final store = AnchorStore(box: box);

      await store.save(gymUuid: gymA);

      expect(store.runtimeGymUuid, gymA);
    });

    test('saves the invite token alongside the gym', () async {
      final store = AnchorStore(box: box);

      await store.save(gymUuid: gymA, inviteToken: 'inv-9');

      expect(store.runtimeGymUuid, gymA);
      expect(store.inviteToken, 'inv-9');
    });

    test('a later capture replaces the previous gym', () async {
      final store = AnchorStore(box: box);

      await store.save(gymUuid: gymA);
      await store.save(gymUuid: gymB);

      expect(store.runtimeGymUuid, gymB);
    });

    test('clear removes the anchor', () async {
      final store = AnchorStore(box: box);
      await store.save(gymUuid: gymA, inviteToken: 'inv-9');

      await store.clear();

      expect(store.runtimeGymUuid, isNull);
      expect(store.inviteToken, isNull);
    });
  });

  group('anchor precedence', () {
    test('runtime anchor wins over the build-time anchor', () async {
      final store = AnchorStore(box: box);
      await store.save(gymUuid: gymA);

      expect(
        store.effectiveAnchor(buildTimeAnchor: gymB),
        gymA,
      );
    });

    test('build-time anchor applies when no runtime anchor was captured', () {
      final store = AnchorStore(box: box);

      expect(
        store.effectiveAnchor(buildTimeAnchor: gymB),
        gymB,
      );
    });

    test('no anchor at all yields null', () {
      final store = AnchorStore(box: box);

      expect(store.effectiveAnchor(buildTimeAnchor: null), isNull);
      expect(store.effectiveAnchor(buildTimeAnchor: ''), isNull);
    });

    test('a runtime anchor still wins after the build-time one is set', () async {
      final store = AnchorStore(box: box);
      await store.save(gymUuid: gymA);

      expect(store.effectiveAnchor(buildTimeAnchor: gymA), gymA);
    });
  });

  group('persistence across restarts', () {
    test('the anchor survives a new store instance on the same box', () async {
      final first = AnchorStore(box: box);
      await first.save(gymUuid: gymA, inviteToken: 'inv-9');

      // A fresh instance = a fresh app launch reading the same disk box.
      final second = AnchorStore(box: box);

      expect(second.runtimeGymUuid, gymA);
      expect(second.inviteToken, 'inv-9');
    });

    test('the anchor survives closing and reopening the box', () async {
      final store = AnchorStore(box: box);
      await store.save(gymUuid: gymA);
      await box.close();

      final reopened = await Hive.openBox<String>('anchor_box_test');
      final afterRestart = AnchorStore(box: reopened);

      expect(afterRestart.runtimeGymUuid, gymA);
    });
  });
}
