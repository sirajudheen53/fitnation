import java.io.FileInputStream
import java.util.Properties

plugins {
    id("com.android.application")
    // START: FlutterFire Configuration
    id("com.google.gms.google-services")
    // END: FlutterFire Configuration
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// Release signing material lives in android/key.properties (gitignored —
// android/.gitignore covers key.properties and **/*.jks). Never commit or
// print the secrets. A release build without this material must FAIL —
// a binary signed with debug keys can never be updated on Play.
// See mobile/RELEASE.md for the keystore setup.
val keystorePropertiesFile = rootProject.file("key.properties")
val keystoreProperties = Properties()
if (keystorePropertiesFile.exists()) {
    FileInputStream(keystorePropertiesFile).use { keystoreProperties.load(it) }
}

android {
    namespace = "com.getfitwithus.app"
    compileSdk = flutter.compileSdkVersion
    // NDK line disabled: pure-Dart app needs no NDK, and the 750MB NDK download
    // was impractically slow on this connection. Restore if you ever add a plugin
    // with native C/C++ code (AGP will then ask for an NDK).
    // ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // Released Play Store identity — immutable after first upload (mobile report 2026-10-25).
        applicationId = "com.getfitwithus.app"
        minSdk = flutter.minSdkVersion
        // Play requires new apps to target API 36+. Pinned explicitly so the
        // policy floor does not move when flutter.targetSdkVersion changes.
        targetSdk = 36
        // Uses the version code from pubspec.yaml. When using split APKs, 1000 * ABI_VERSION
        // is added automatically by Flutter. (https://developer.android.com/studio/build/configure-apk-splits#configure-APK-versions)
        // You can force using the value of versionCode by specifying the `-P force-version-code-ignoring-abi=true`
        // flag during build.
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    val storeFilePath = keystoreProperties.getProperty("storeFile")
    val uploadStoreFile: File? = when {
        storeFilePath == null -> null
        File(storeFilePath).isAbsolute -> File(storeFilePath)
        else -> rootProject.file(storeFilePath)
    }

    if (keystorePropertiesFile.exists() && uploadStoreFile?.exists() == true) {
        signingConfigs {
            create("upload") {
                storeFile = uploadStoreFile
                storePassword = keystoreProperties.getProperty("storePassword")
                keyAlias = keystoreProperties.getProperty("keyAlias")
                keyPassword = keystoreProperties.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        release {
            signingConfig = when {
                signingConfigs.findByName("upload") != null ->
                    signingConfigs.getByName("upload")
                gradle.startParameter.taskNames.any { it.contains("release", ignoreCase = true) } ->
                    throw GradleException(
                        "Release build refused: mobile/android/key.properties (upload-key " +
                            "signing material) is missing or points at a missing keystore. " +
                            "Signing a release with debug keys would publish a binary that " +
                            "can never be updated on Play. See mobile/RELEASE.md."
                    )
                else -> {
                    // Only reachable while configuring non-release gradle runs
                    // (e.g. `flutter run --debug` on a machine without the
                    // keystore). Debug builds do not use this anyway.
                    logger.warn("release buildType has no upload signing material; falling back to debug signing for configuration only")
                    signingConfigs.getByName("debug")
                }
            }
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}

dependencies {
    // WhatsApp zero-tap authentication (OTP Android SDK):
    // https://developers.facebook.com/docs/whatsapp/business-management-api/authentication-templates/zero-tap-authentication-templates
    implementation("com.whatsapp.otp:whatsapp-otp-android-sdk:1.0.0")
    testImplementation("junit:junit:4.13.2")
}
