plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.performance.app"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.performance.app"
        minSdk = 26
        targetSdk = 34
        versionCode = 2
        versionName = "2.0.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables {
            useSupportLibrary = true
        }
    }

    /*
     * Release signing, only when the build has been handed a key.
     *
     * Read from the environment rather than a checked-in file: a signing key
     * is the one thing that must never be in the repository, since anyone
     * holding it can publish an update that installs over a real one.
     *
     * Without the variables the release build is simply unsigned, which
     * Android refuses to install -- a clear failure rather than an APK that
     * looks fine and cannot be upgraded later.
     */
    val keystorePath: String? = System.getenv("ANDROID_KEYSTORE_PATH")

    signingConfigs {
        if (!keystorePath.isNullOrBlank()) {
            create("release") {
                storeFile = file(keystorePath)
                storePassword = System.getenv("ANDROID_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("ANDROID_KEY_ALIAS")
                keyPassword = System.getenv("ANDROID_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            if (!keystorePath.isNullOrBlank()) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
    }
    kotlinOptions {
        jvmTarget = "1.8"
    }
    buildFeatures {
        compose = true
    }
    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.11"
    }
}

dependencies {
    // Health Connect Client SDK
    implementation("androidx.health.connect:connect-client:1.1.0-alpha07")

    // Jetpack Compose & Material 3
    implementation(platform("androidx.compose:compose-bom:2024.05.00"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.activity:activity-compose:1.9.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.0")

    // Background Sync WorkManager
    implementation("androidx.work:work-runtime-ktx:2.9.0")

    // FileProvider, for handing a saved report to a PDF viewer.
    implementation("androidx.core:core-ktx:1.13.1")

    // Networking (OkHttp & Gson)
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.google.code.gson:gson:2.10.1")

    // Coroutines
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
}
