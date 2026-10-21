import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:hive/hive.dart';

import 'package:fitnation_app/features/auth/data/data_sources/auth_local_data_source.dart';
import 'package:fitnation_app/features/auth/data/models/entitlement.dart';
import 'package:fitnation_app/features/auth/data/models/user_model.dart';

void main() {
  late Directory hiveDir;
  late AuthLocalDataSource source;

  setUp(() async {
    hiveDir = await Directory.systemTemp.createTemp('auth_local_test');
    Hive.init(hiveDir.path);
    source = AuthLocalDataSource();
    await source.init();
  });

  tearDown(() async {
    await Hive.close();
    await hiveDir.delete(recursive: true);
  });

  test('token lifecycle: save, read, and isAuthenticated', () async {
    expect(source.isAuthenticated, isFalse);
    await source.saveToken('jwt-token');
    expect(source.getToken(), 'jwt-token');
    expect(source.isAuthenticated, isTrue);
  });

  test('user profile survives a JSON round-trip', () async {
    const user = UserModel(
      id: 1,
      email: 'asha@example.com',
      firstName: 'Asha',
      lastName: 'Kumar',
      role: 'customer',
      tenantId: 9,
      tenantName: 'Iron Temple',
      branchId: 2,
      branchName: 'Adyar',
      isOwner: false,
    );
    await source.saveUser(user);

    final restored = source.getUser();
    expect(restored!.id, 1);
    expect(restored.fullName, 'Asha Kumar');
    expect(restored.tenantId, 9);
    expect(restored.isOwner, isFalse);
  });

  test('getUser returns null when nothing is stored', () {
    expect(source.getUser(), isNull);
  });

  test('permissions round-trip and default to empty', () async {
    expect(source.getPermissions(), isEmpty);
    await source.savePermissions(['customers', 'billing']);
    expect(source.getPermissions(), ['customers', 'billing']);
  });

  test('entitlement round-trips through the box', () async {
    const entitlement = Entitlement(
      status: AppEntitlementStatus.grace,
      readOnly: true,
      planName: 'Gold',
      gymName: 'Iron Temple',
      gymUuid: '3f7c1a2b-4d5e-6f70-8192-a3b4c5d6e7f8',
    );
    await source.saveEntitlement(entitlement);

    final restored = source.getEntitlement();
    expect(restored!.status, AppEntitlementStatus.grace);
    expect(restored.readOnly, isTrue);
    expect(restored.planName, 'Gold');
    expect(restored.gymName, 'Iron Temple');
  });

  test('getEntitlement returns null when none is stored', () {
    expect(source.getEntitlement(), isNull);
  });

  test('clear wipes every stored key but keeps the box usable', () async {
    await source.saveToken('jwt-token');
    await source.savePermissions(['customers']);
    await source.saveEntitlement(
      const Entitlement(status: AppEntitlementStatus.active),
    );

    await source.clear();

    expect(source.getToken(), isNull);
    expect(source.getUser(), isNull);
    expect(source.getPermissions(), isEmpty);
    expect(source.getEntitlement(), isNull);
    expect(source.isAuthenticated, isFalse);

    await source.saveToken('second-login');
    expect(source.getToken(), 'second-login');
  });
}