import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:hive/hive.dart';

import 'package:fitnation_app/core/preferences/dial_code_store.dart';
import 'package:fitnation_app/core/utils/country_code.dart';

void main() {
  late Directory hiveDir;
  late DialCodeStore store;

  setUp(() async {
    hiveDir = await Directory.systemTemp.createTemp('dial_code_test');
    Hive.init(hiveDir.path);
    store = DialCodeStore();
    await store.init();
  });

  tearDown(() async {
    await Hive.close();
    await hiveDir.delete(recursive: true);
  });

  test('load returns null before anything is saved', () {
    expect(store.load(), isNull);
  });

  test('save/load round-trips the selected country', () async {
    final uae = CountryCodes.findByIso('AE')!;
    await store.save(uae);

    final loaded = store.load();
    expect(loaded?.code, 'AE');
    expect(loaded?.displayDialCode, '+971');
  });

  test('a saved selection survives reopening the box', () async {
    await store.save(CountryCodes.defaultCode);
    await Hive.close();

    final reopened = DialCodeStore();
    await reopened.init();
    expect(reopened.load()?.code, 'IN');
  });

  test('an unsupported saved code loads as null instead of crashing', () async {
    await store.box?.put('last_dial_code_iso', 'XX');
    expect(store.load(), isNull);
  });
}
