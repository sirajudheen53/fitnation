// Play Store phone screenshot capture.
//
// Renders the REAL app screens (app theme, real fonts, demo member data)
// headlessly at a phone resolution and writes 1080x1920 PNGs to
// store/screenshots/. This is not marketing art — it is the actual widget
// tree, captured via a RepaintBoundary.
//
// Regenerate with (from mobile/):
//   flutter test test/store/screenshot_capture_test.dart
//
// The PNGs are RGB-flattened + verified by tools/check (see store/README.md).
//
// Mocking follows the existing harness patterns:
//   - test/features/dashboard/screens/dashboard_screen_test.dart
//   - test/features/workouts/screens/workout_list_screen_test.dart
//   - test/features/diet/screens/diet_plan_screen_test.dart
//   - test/features/access/pages/enrollment_qr_page_test.dart
import 'dart:io';
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart' show FontLoader;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';
// Faked to seed the google_fonts device cache below; it is a transitive
// dependency of google_fonts, not a direct dependency of this app.
// ignore: depend_on_referenced_packages
import 'package:path_provider_platform_interface/path_provider_platform_interface.dart';

import 'package:fitnation_app/features/access/presentation/pages/enrollment_qr_page.dart';
import 'package:fitnation_app/features/attendance/data/models/attendance_record.dart';
import 'package:fitnation_app/features/attendance/presentation/providers/attendance_provider.dart';
import 'package:fitnation_app/features/auth/data/data_sources/auth_local_data_source.dart';
import 'package:fitnation_app/features/auth/data/data_sources/auth_remote_data_source.dart';
import 'package:fitnation_app/features/auth/data/models/entitlement.dart';
import 'package:fitnation_app/features/auth/data/models/user_model.dart';
import 'package:fitnation_app/features/auth/domain/repositories/auth_repository.dart';
import 'package:fitnation_app/features/auth/presentation/providers/auth_notifier.dart';
import 'package:fitnation_app/features/auth/presentation/providers/auth_providers.dart';
import 'package:fitnation_app/core/theme/app_theme.dart';
import 'package:fitnation_app/features/dashboard/presentation/screens/dashboard_screen.dart';
import 'package:fitnation_app/features/diet/data/models/diet_plan.dart';
import 'package:fitnation_app/features/diet/data/models/meal.dart';
import 'package:fitnation_app/features/diet/presentation/providers/diet_provider.dart';
import 'package:fitnation_app/features/diet/presentation/screens/diet_plan_screen.dart';
import 'package:fitnation_app/features/progress/data/models/body_measurement.dart';
import 'package:fitnation_app/features/progress/presentation/providers/progress_provider.dart';
import 'package:fitnation_app/features/workouts/data/models/exercise.dart';
import 'package:fitnation_app/features/workouts/data/models/workout_exercise.dart';
import 'package:fitnation_app/features/workouts/data/models/workout_plan.dart';
import 'package:fitnation_app/features/workouts/presentation/providers/workout_provider.dart';
import 'package:fitnation_app/features/workouts/presentation/screens/workout_list_screen.dart';

/// 1080x1920 physical pixels at dpr 2.0 = a 540x960 logical phone (the xhdpi
/// 1080p Android device profile; narrower 360/432dp profiles overflow the
/// plan header meta rows in the real screens).
const _physicalSize = Size(1080, 1920);
const _devicePixelRatio = 2.0;
const _boundaryKey = ValueKey('store_screenshot_boundary');
const _outputDir = 'store/screenshots';

void main() {
  setUpAll(() async {
    await _seedGoogleFontsDeviceCache();
    await _loadRealFonts();
    // Kick google_fonts for every Inter face the app theme uses — it reads
    // the seeded device cache. Then wait until the engine has actually
    // registered the families (an Ahem 'Wilma' at fontSize 100 measures
    // exactly 500.0; real Inter is narrower).
    GoogleFonts.inter();
    GoogleFonts.inter(fontWeight: FontWeight.w500);
    GoogleFonts.inter(fontWeight: FontWeight.w600);
    GoogleFonts.inter(fontWeight: FontWeight.w700);
    const families = ['Inter_regular', 'Inter_500', 'Inter_600', 'Inter_700'];
    for (var attempt = 0; attempt < 100; attempt++) {
      await Future<void>.delayed(const Duration(milliseconds: 20));
      if (families.every(_familyRegistered)) return;
    }
    final widths = families.map((f) => '$f=${_glyphWidth(f)}').join(', ');
    fail('google_fonts did not register the Inter faces: $widths');
  });

  Future<void> pumpAndCapture(
    WidgetTester tester,
    Widget app,
    String fileName,
  ) async {
    tester.view.physicalSize = _physicalSize;
    tester.view.devicePixelRatio = _devicePixelRatio;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(RepaintBoundary(key: _boundaryKey, child: app));
    await tester.pumpAndSettle();

    Directory(_outputDir).createSync(recursive: true);
    await tester.binding.runAsync(() async {
      final boundary = tester.renderObject<RenderRepaintBoundary>(
        find.byKey(_boundaryKey),
      );
      final image = await boundary.toImage(pixelRatio: _devicePixelRatio);
      expect(image.width, 1080, reason: fileName);
      expect(image.height, 1920, reason: fileName);
      final byteData = await image.toByteData(format: ui.ImageByteFormat.png);
      File('$_outputDir/$fileName')
          .writeAsBytesSync(byteData!.buffer.asUint8List());
      image.dispose();
    });
    expect(File('$_outputDir/$fileName').existsSync(), isTrue);
  }

  testWidgets('captures 01-dashboard.png', (tester) async {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    DateTime at(int daysAgo, int hour, int minute) =>
        today.subtract(Duration(days: daysAgo)).add(Duration(hours: hour, minutes: minute));
    final attendance = [
      AttendanceRecord(id: 106, checkInTime: at(0, 7, 30), method: 'qr'),
      AttendanceRecord(id: 105, checkInTime: at(1, 7, 10), method: 'qr'),
      AttendanceRecord(id: 104, checkInTime: at(2, 18, 5), method: 'biometric'),
      AttendanceRecord(id: 103, checkInTime: at(3, 7, 25), method: 'biometric'),
      AttendanceRecord(id: 102, checkInTime: at(4, 7, 15), method: 'qr'),
      AttendanceRecord(id: 101, checkInTime: at(5, 18, 40), method: 'qr'),
    ];
    const workoutPlan = WorkoutPlan(
      id: 20,
      name: 'Hypertrophy PPL',
      difficulty: 'intermediate',
      durationWeeks: 8,
      sessionsPerWeek: 5,
      days: [
        WorkoutDay(
          id: 1,
          name: 'Push Day',
          dayNumber: 1,
          exercises: [
            WorkoutExercise(
              id: 1,
              exercise: Exercise(id: 1, name: 'Bench Press'),
              targetSets: 4,
              targetReps: 8,
            ),
            WorkoutExercise(
              id: 2,
              exercise: Exercise(id: 2, name: 'Overhead Press'),
              targetSets: 3,
              targetReps: 10,
            ),
            WorkoutExercise(
              id: 3,
              exercise: Exercise(id: 3, name: 'Incline DB Press'),
              targetSets: 3,
              targetReps: 10,
            ),
          ],
        ),
      ],
    );
    const workoutAssignment = WorkoutAssignment(
      id: 1,
      customerId: 42,
      planId: 20,
      planName: 'Hypertrophy PPL',
      isActive: true,
    );
    const dietPlan = DietPlan(
      id: 30,
      name: 'Lean Cut — 8 Weeks',
      targetCalories: 1800,
      durationWeeks: 8,
      mealsPerDay: 4,
      days: [
        DietDay(
          id: 1,
          name: 'Day 1',
          dayNumber: 1,
          meals: [
            Meal(
              id: 1,
              name: 'Breakfast',
              mealType: 'breakfast',
              foodItems: [
                FoodItem(id: 1, name: 'Poha', calories: 250, protein: 6.0),
                FoodItem(id: 2, name: 'Banana', calories: 105, protein: 1.3),
              ],
            ),
            Meal(
              id: 2,
              name: 'Lunch',
              mealType: 'lunch',
              foodItems: [
                FoodItem(
                  id: 3,
                  name: 'Grilled Chicken',
                  calories: 280,
                  protein: 32.0,
                ),
                FoodItem(id: 4, name: 'Brown Rice', calories: 220, protein: 5.0),
              ],
            ),
          ],
        ),
      ],
    );
    const dietAssignment = DietAssignment(
      id: 2,
      customerId: 42,
      planId: 30,
      planName: 'Lean Cut — 8 Weeks',
      isActive: true,
    );
    const measurement = BodyMeasurement(
      id: 1,
      measuredAt: null,
      weight: 72.4,
      bmi: 23.6,
    );

    await pumpAndCapture(
      tester,
      ProviderScope(
        overrides: [
          authRepositoryProvider.overrideWithValue(_DemoAuthRepository()),
          authProvider.overrideWith(
            (ref) => _DemoAuthNotifier(_DemoAuthRepository()),
          ),
          activeWorkoutAssignmentProvider
              .overrideWith((ref) async => workoutAssignment),
          workoutPlanProvider(20).overrideWith((ref) async => workoutPlan),
          activeDietAssignmentProvider
              .overrideWith((ref) async => dietAssignment),
          dietPlanProvider(30).overrideWith((ref) async => dietPlan),
          attendanceHistoryProvider.overrideWith((ref) async => attendance),
          bodyMeasurementsProvider.overrideWith((ref) async => [measurement]),
          fitnessGoalsProvider.overrideWith((ref) async => const []),
        ],
        child: MaterialApp(
          debugShowCheckedModeBanner: false,
          theme: AppTheme.light,
          home: const DashboardScreen(),
        ),
      ),
      '01-dashboard.png',
    );
  });

  testWidgets('captures 02-workouts.png', (tester) async {
    const day1 = WorkoutDay(
      id: 1,
      name: 'Push Day',
      dayNumber: 1,
      exercises: [
        WorkoutExercise(
          id: 1,
          exercise: Exercise(id: 1, name: 'Bench Press'),
          targetSets: 4,
          targetReps: 8,
        ),
        WorkoutExercise(
          id: 2,
          exercise: Exercise(id: 2, name: 'Overhead Press'),
          targetSets: 3,
          targetReps: 10,
        ),
        WorkoutExercise(
          id: 3,
          exercise: Exercise(id: 3, name: 'Incline DB Press'),
          targetSets: 3,
          targetReps: 10,
        ),
        WorkoutExercise(
          id: 4,
          exercise: Exercise(id: 4, name: 'Tricep Pushdown'),
          targetSets: 3,
          targetReps: 12,
        ),
      ],
    );
    const day2 = WorkoutDay(
      id: 2,
      name: 'Pull Day',
      dayNumber: 2,
      exercises: [
        WorkoutExercise(
          id: 5,
          exercise: Exercise(id: 5, name: 'Deadlift'),
          targetSets: 3,
          targetReps: 5,
        ),
        WorkoutExercise(
          id: 6,
          exercise: Exercise(id: 6, name: 'Lat Pulldown'),
          targetSets: 4,
          targetReps: 10,
        ),
        WorkoutExercise(
          id: 7,
          exercise: Exercise(id: 7, name: 'Barbell Row'),
          targetSets: 4,
          targetReps: 8,
        ),
        WorkoutExercise(
          id: 8,
          exercise: Exercise(id: 8, name: 'Bicep Curl'),
          targetSets: 3,
          targetReps: 12,
        ),
      ],
    );
    const day3 = WorkoutDay(
      id: 3,
      name: 'Legs Day',
      dayNumber: 3,
      exercises: [
        WorkoutExercise(
          id: 9,
          exercise: Exercise(id: 9, name: 'Squat'),
          targetSets: 4,
          targetReps: 8,
        ),
        WorkoutExercise(
          id: 10,
          exercise: Exercise(id: 10, name: 'Leg Press'),
          targetSets: 3,
          targetReps: 10,
        ),
        WorkoutExercise(
          id: 11,
          exercise: Exercise(id: 11, name: 'Leg Curl'),
          targetSets: 3,
          targetReps: 12,
        ),
        WorkoutExercise(
          id: 12,
          exercise: Exercise(id: 12, name: 'Calf Raise'),
          targetSets: 4,
          targetReps: 15,
        ),
      ],
    );
    const plan = WorkoutPlan(
      id: 20,
      name: 'Hypertrophy PPL',
      difficulty: 'intermediate',
      durationWeeks: 8,
      sessionsPerWeek: 5,
      days: [day1, day2, day3],
    );
    const assignment = WorkoutAssignment(
      id: 1,
      customerId: 42,
      planId: 20,
      planName: 'Hypertrophy PPL',
      isActive: true,
    );

    await pumpAndCapture(
      tester,
      ProviderScope(
        overrides: [
          activeWorkoutAssignmentProvider
              .overrideWith((ref) async => assignment),
          workoutPlanProvider.overrideWith((ref, planId) async => plan),
        ],
        child: MaterialApp(
          debugShowCheckedModeBanner: false,
          theme: AppTheme.light,
          home: const WorkoutListScreen(),
        ),
      ),
      '02-workouts.png',
    );
  });

  testWidgets('captures 03-diet-plan.png', (tester) async {
    const plan = DietPlan(
      id: 30,
      name: 'Lean Cut — 8 Weeks',
      targetCalories: 1800,
      durationWeeks: 8,
      mealsPerDay: 4,
      days: [
        DietDay(
          id: 1,
          name: 'Day 1',
          dayNumber: 1,
          meals: [
            Meal(
              id: 1,
              name: 'Breakfast',
              mealType: 'breakfast',
              foodItems: [
                FoodItem(id: 1, name: 'Poha', calories: 250, protein: 6.0),
                FoodItem(id: 2, name: 'Banana', calories: 105, protein: 1.3),
                FoodItem(id: 3, name: 'Milk', calories: 150, protein: 8.0),
              ],
            ),
            Meal(
              id: 2,
              name: 'Lunch',
              mealType: 'lunch',
              foodItems: [
                FoodItem(
                  id: 4,
                  name: 'Grilled Chicken',
                  calories: 280,
                  protein: 32.0,
                ),
                FoodItem(id: 5, name: 'Brown Rice', calories: 220, protein: 5.0),
                FoodItem(id: 6, name: 'Dal', calories: 150, protein: 9.0),
                FoodItem(id: 7, name: 'Cucumber Salad', calories: 40, protein: 1.5),
              ],
            ),
            Meal(
              id: 3,
              name: 'Evening Snack',
              mealType: 'snack',
              foodItems: [
                FoodItem(id: 8, name: 'Buttermilk', calories: 60, protein: 2.0),
                FoodItem(id: 9, name: 'Roasted Chana', calories: 130, protein: 7.0),
              ],
            ),
            Meal(
              id: 4,
              name: 'Dinner',
              mealType: 'dinner',
              foodItems: [
                FoodItem(id: 10, name: 'Paneer Bhurji', calories: 290, protein: 18.0),
                FoodItem(id: 11, name: 'Chapati', calories: 200, protein: 6.0),
              ],
            ),
          ],
        ),
      ],
    );
    const assignment = DietAssignment(
      id: 2,
      customerId: 42,
      planId: 30,
      planName: 'Lean Cut — 8 Weeks',
      isActive: true,
    );

    await pumpAndCapture(
      tester,
      ProviderScope(
        overrides: [
          activeDietAssignmentProvider.overrideWith((ref) async => assignment),
          dietPlanProvider.overrideWith((ref, planId) async => plan),
        ],
        child: MaterialApp(
          debugShowCheckedModeBanner: false,
          theme: AppTheme.light,
          home: const DietPlanScreen(),
        ),
      ),
      '03-diet-plan.png',
    );
  });

  testWidgets('captures 04-qr-checkin.png', (tester) async {
    await pumpAndCapture(
      tester,
      ProviderScope(
        overrides: [
          authRepositoryProvider.overrideWithValue(_DemoAuthRepository()),
          authProvider.overrideWith(
            (ref) => _DemoAuthNotifier(_DemoAuthRepository()),
          ),
        ],
        child: MaterialApp(
          debugShowCheckedModeBanner: false,
          theme: AppTheme.light,
          home: const EnrollmentQrPage(),
        ),
      ),
      '04-qr-checkin.png',
    );
  });
}

double _glyphWidth(String family) {
  final tp = TextPainter(
    text: TextSpan(
      text: 'Wilma',
      style: TextStyle(fontFamily: family, fontSize: 100),
    ),
    textDirection: TextDirection.ltr,
  )..layout();
  final width = tp.width;
  tp.dispose();
  return width;
}

/// True once [family] renders with real glyphs instead of the Ahem fallback.
bool _familyRegistered(String family) => _glyphWidth(family) < 480;

/// Seeds the google_fonts device-file cache with the real Inter TTFs so the
/// app theme (AppTheme.light -> GoogleFonts.interTextTheme) loads its fonts
/// from the fake application-support directory instead of hitting the network
/// (blocked inside widget tests). File names follow google_fonts' own scheme:
/// `<family>_<variant>_<hash>.ttf` under getApplicationSupportDirectory().
Future<void> _seedGoogleFontsDeviceCache() async {
  // Hashes from the google_fonts package data (Inter family, normal style) —
  // the fixtures were fetched from fonts.gstatic.com and must match them.
  const interHashes = {
    'inter-regular.ttf':
        'ecdb53099b1a68cd24c6900ea5beeafec81bd3c8cb9d0f3c51b9986583ba3982',
    'inter-500.ttf':
        '492dec3bc33255f9d81bd5fb18704ad72f96f9b9318e4171bc9f9be9dd4bf44b',
    'inter-600.ttf':
        'd7ba633bab7f40576e539a7e934a1301d7618dceea59c743de477c2c493462fc',
    'inter-700.ttf':
        'b7e339223d56e8c4210c86f1ba87b3d43d6c47e03956ea56f0a7a938ae61b2a3',
  };
  final supportDir =
      await Directory.systemTemp.createTemp('fitnation_store_screens');
  for (final entry in interHashes.entries) {
    final fixture = File('test/store/fonts/${entry.key}');
    if (!fixture.existsSync()) {
      fail('Missing font fixture ${fixture.path}');
    }
    // Variant naming follows GoogleFontsVariant.toString(): w400 normal is
    // 'regular' (lowercase), other weights are their numeric value (e.g. 700).
    final variant = entry.key.replaceAll('inter-', '').replaceAll('.ttf', '');
    fixture.copySync('${supportDir.path}/Inter_${variant}_${entry.value}.ttf');
  }
  PathProviderPlatform.instance = _FakePathProviderPlatform(supportDir.path);
}

/// Points path_provider at the seeded google_fonts cache directory.
class _FakePathProviderPlatform extends PathProviderPlatform {
  _FakePathProviderPlatform(this.supportPath);

  final String supportPath;

  @override
  Future<String?> getApplicationSupportPath() async => supportPath;
}

/// Loads the real Roboto + MaterialIcons fonts bundled with the Flutter SDK
/// so the screenshots show real glyphs. Without this the test framework
/// renders every glyph with the Ahem placeholder (solid blocks).
Future<void> _loadRealFonts() async {
  // resolvedExecutable sits inside the SDK (dart-sdk/bin/dart or
  // artifacts/engine/...), so walk up to <flutter-sdk>/bin/cache.
  var dir = File(Platform.resolvedExecutable).parent;
  Directory? fontsDir;
  for (var i = 0; i < 8; i++) {
    final candidate =
        Directory('${dir.path}/bin/cache/artifacts/material_fonts');
    if (candidate.existsSync()) {
      fontsDir = candidate;
      break;
    }
    final parent = dir.parent;
    if (parent.path == dir.path) break;
    dir = parent;
  }
  if (fontsDir == null) {
    fail('Material fonts not found under ${dir.path}');
  }

  final families = <String, List<Future<ByteData>>>{};
  for (final entity in fontsDir.listSync().whereType<File>()) {
    final name = entity.uri.pathSegments.last;
    final String? family;
    if (name.startsWith('Roboto-') && name.endsWith('.ttf')) {
      // Regular / Medium / Bold only — cover the weights the theme uses
      // without pulling in Thin/Light/Black/Italic faces.
      final weight = name.substring('Roboto-'.length, name.indexOf('.ttf'));
      family = const {'Regular', 'Medium', 'Bold'}.contains(weight)
          ? 'Roboto'
          : null;
    } else if (name == 'MaterialIcons-Regular.otf') {
      family = 'MaterialIcons';
    } else {
      family = null;
    }
    if (family == null) continue;
    final bytes = entity.readAsBytesSync();
    (families[family] ??= [])
        .add(Future.value(ByteData.view(bytes.buffer)));
  }

  for (final entry in families.entries) {
    final loader = FontLoader(entry.key);
    for (final font in entry.value) {
      loader.addFont(font);
    }
    try {
      await loader.load();
    } catch (_) {
      // MaterialIcons may already be registered by the test binding — a
      // duplicate load is harmless.
    }
  }
}

/// Fake auth repository that returns a logged-in customer without Hive.
class _DemoAuthRepository extends AuthRepository {
  _DemoAuthRepository()
      : super(
          AuthRemoteDataSource(Dio()),
          _DemoLocalDataSource(),
        );

  @override
  ({UserModel? user, List<String> permissions, String? token, Entitlement? entitlement})
      restoreSession() {
    return (
      user: _demoUser,
      permissions: const [],
      token: 'fake-token',
      entitlement: const Entitlement(status: AppEntitlementStatus.active),
    );
  }
}

/// Fake local data source that returns a stored session without Hive.
class _DemoLocalDataSource extends AuthLocalDataSource {
  @override
  String? getToken() => 'fake-token';

  @override
  UserModel? getUser() => _demoUser;

  @override
  List<String> getPermissions() => const [];

  @override
  bool get isAuthenticated => true;
}

/// Auth notifier pre-set to the demo member (enrollment QR page pattern).
class _DemoAuthNotifier extends AuthNotifier {
  _DemoAuthNotifier(super.repository) {
    state = AuthState(status: AuthStatus.authenticated, user: _demoUser);
  }
}

const _demoUser = UserModel(
  id: 42,
  role: 'customer',
  firstName: 'Raman',
  lastName: 'Kumar',
  tenantId: 7,
  tenantName: 'Hash Fit',
);
