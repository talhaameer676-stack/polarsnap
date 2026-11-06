# Project: PolarSnap — by Trandif

## Architecture Overview
PolarSnap is an ultra-fast, modern, commercial-grade native Android video and audio capture utility built on Jetpack Compose and Material 3 Expressive principles. It embeds `youtubedl-android` (Python + yt-dlp + FFmpeg natively on ARM64) with a zero-leak whitelabeled engine interface, CapCut-grade cinematic Hald CLUT color grading, 4K/HD Lanczos super-resolution remastering, multi-threaded queue management, Scoped Storage MediaStore publishing, isolated Cloudflare D1/Worker licensing, and silent GitHub OTA updates.

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         Presentation Layer (Jetpack Compose)                    │
│   HomeScreen ─── DownloadsScreen ─── SettingsScreen ─── ConfigureBottomSheet     │
│                     │                       │                       │            │
│                     ▼                       ▼                       ▼            │
│               HomeViewModel         DownloadsViewModel      SettingsViewModel    │
└───────────────────────────────────────┬──────────────────────────────────────────┘
                                        │
┌───────────────────────────────────────▼──────────────────────────────────────────┐
│                             Domain & Application Layer                           │
│   ┌───────────────────────────┐                ┌─────────────────────────────┐   │
│   │   DownloadQueueManager    │                │   PolarCommandTranslator    │   │
│   │  (2 Concurrency Slots)    │                │  (4 High-Level User Cards)  │   │
│   └─────────────┬─────────────┘                └──────────────┬──────────────┘   │
│                 │                                             │                  │
│   ┌─────────────▼─────────────┐                ┌──────────────▼──────────────┐   │
│   │   DownloadForegroundSvc   │                │     PolarLogSanitizer       │   │
│   │ (FOREGROUND_SERVICE_SYNC) │                │ (Zero-Leak Output Scrubber) │   │
│   └─────────────┬─────────────┘                └──────────────┬──────────────┘   │
└─────────────────┼─────────────────────────────────────────────┼──────────────────┘
                  │                                             │
┌─────────────────▼─────────────────────────────────────────────▼──────────────────┐
│                            Core Native Engine Layer                              │
│   ┌────────────────────────────────────────┐ ┌───────────────────────────────┐   │
│   │        Polar Core Engine v2.4          │ │     FFmpeg Remaster Engine    │   │
│   │ (youtubedl-android, Python C-API JNI)  │ │ (MediaCodec, Lanczos, HaldCLUT│   │
│   └────────────────────────────────────────┘ └───────────────────────────────┘   │
└───────────────────────────────────────┬──────────────────────────────────────────┘
                                        │
┌───────────────────────────────────────▼──────────────────────────────────────────┐
│                      Infrastructure & Remote Services Layer                      │
│   ┌────────────────────────────────────────┐ ┌───────────────────────────────┐   │
│   │   Isolated Cloudflare D1/Worker Auth   │ │      Silent GitHub OTA        │   │
│   │ (HMAC-SHA256, 7-Day Offline Grace)     │ │ (PackageInstaller Session)    │   │
│   └────────────────────────────────────────┘ └───────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Feature Inventory
Every feature identified during the comprehensive survey phase is enumerated below with its assigned milestone:

| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Embedded ARM64 Engine | Embed `youtubedl-android` (Python 3.11, yt-dlp, FFmpeg native libraries) with 16KB ELF page alignment | M1 | Survey / Reference |
| 2 | Whitelabeled Engine Rebranding | Rebrand core engine in UI and logs as "Polar Core Engine v2.4 (Active)" | M1 | ORIGINAL_REQUEST §3 |
| 3 | Turbo Acceleration Toggle Card | Map user toggle to `-N 16 --downloader libaria2c.so` multi-connection download | M1 | ORIGINAL_REQUEST §3 |
| 4 | Lossless Audio Toggle Card | Map user toggle to `-x --audio-format flac/best` high-fidelity audio extraction | M1 | ORIGINAL_REQUEST §3 |
| 5 | Clean Watermark Toggle Card | Map user toggle to post-processing crop or clean stream extractor for TikTok/IG/Shorts | M1 | ORIGINAL_REQUEST §3 |
| 6 | Sponsor Stripper Toggle Card | Map user toggle to `--sponsorblock-remove default` metadata splicing | M1 | ORIGINAL_REQUEST §3 |
| 7 | Zero-Leak Log Scrubber | Regex interception and scrubbing of all stdout/stderr strings preventing yt-dlp/Python leakage | M1 | ORIGINAL_REQUEST §3 |
| 8 | Domain Exception Sanitizer | Catch and transform raw CLI/Python exceptions into clean user-friendly domain errors | M1 | Survey / Arch |
| 9 | CapCut LUT Asset Bundling | Pre-compiled 512x512 Hald CLUT Level 8 PNGs for Teal & Orange, Viral Warm Pop, Moody Noir, Studio Bright | M2 | ORIGINAL_REQUEST §3 / Survey |
| 10 | Bijective LUT Transformer | Mathematical coordinate transformation mapping CapCut 8x8 tiled 64^3 3D LUTs to FFmpeg Hald CLUTs | M2 | Survey / Reverse Eng |
| 11 | FFmpeg 4K/HD Remaster Filtergraph | 5-stage filtergraph: CAS sharpening, eq/vibrance, Hald CLUT grading, Lanczos upscaling, unsharp recovery | M2 | ORIGINAL_REQUEST §3 / Survey |
| 12 | Pre-Upscale Memory Optimization | Apply grading & sharpening before Lanczos scaling saving 75% frame RAM on Android | M2 | Survey / Hardware Arch |
| 13 | ARM64 MediaCodec Acceleration | Hardware-accelerated encoding (`hevc_mediacodec`/`h264_mediacodec`) with 3-tier fallback matrix | M2 | Survey / Hardware Arch |
| 14 | Uncompressed 4K Master Extraction | Stream selection logic extracting highest available raw 4K stream before transcode | M2 | ORIGINAL_REQUEST §3 |
| 15 | Bounded Concurrency Queue | 2-slot active download queue with up to 16 aria2c sub-sockets per slot preventing socket exhaustion | M3 | ORIGINAL_REQUEST §3 / Survey |
| 16 | Bulk / Playlist Batch Processor | Batch extraction, bulk queueing, multi-item progress tracking, and selective item download | M3 | ORIGINAL_REQUEST §3 |
| 17 | Download Lifecycle Control | Pause, resume, retry, cancel, and persistent task state management | M3 | Survey / UX |
| 18 | Foreground Service Notification | Android 14 `dataSync` foreground service with live throughput, eta, and cancel/pause actions | M3 | Survey / Android API 34 |
| 19 | Scoped Storage MediaStore Exporter | Two-phase publishing (`IS_PENDING = 1` -> copy -> `IS_PENDING = 0`) to Movies/Music folders | M3 | Survey / Android API 34 |
| 20 | Arctic Streamline Design System | Material 3 Expressive theme with custom Arctic color palette, shapes, and Inter typography | M4 | Stitch screen_1-4 / Survey |
| 21 | Polar Bear Cub Mascot Branding | Mascot integration across Android Adaptive App Icon, AVD Splash Screen, TopBar avatars, empty states | M4 | ORIGINAL_REQUEST §1 / Survey |
| 22 | Main Home Screen (Screen 4) | Smart URL paste dock, auto-detect clipboard pill, mode selector chips, 4K remaster preview card | M4 | Stitch screen_4 / Survey |
| 23 | Pre-Download Bottom Sheet (Screen 3) | Resolution selector pills, container segmented switch, remaster toggles, playlist batch banner | M4 | Stitch screen_3 / Survey |
| 24 | Downloads & Queue Screen (Screen 1) | Active download cards, multi-gradient progress bars, live throughput telemetry hub, PiP completed card | M4 | Stitch screen_1 / Survey |
| 25 | Settings & Config Screen (Screen 2) | Engine status banner, 4 whitelabeled cards, battery/storage helpers, secret 7-tap developer console | M4 | Stitch screen_2 / Survey |
| 26 | Isolated Cloudflare Licensing Authority | Dedicated Cloudflare D1/Worker licensing verification strictly isolated to PolarSnap | M5 | ORIGINAL_REQUEST §3 |
| 27 | HMAC Signature & Replay Prevention | SHA-256 HMAC request signing, timestamp drift validation (+/- 300s), and single-use nonce tracking | M5 | Survey / Security Arch |
| 28 | Offline Grace Period Protocol | Encrypted local license cache allowing 7 days of full offline operation before verification | M5 | Survey / Security Arch |
| 29 | Silent In-App GitHub OTA Updater | Background GitHub release polling, APK download, SHA-256 verification, and PackageInstaller session | M5 | ORIGINAL_REQUEST §3 / Survey |
| 30 | Milestone 1 Ad-Free Guarantee | Strict enforcement of zero Monetag ads and zero ad trackers in v1.0.0 codebase | M5 | ORIGINAL_REQUEST §3 |
| 31 | End-to-End Test Suite (Tiers 1-4) | Comprehensive opaque-box test suite: Feature Coverage, Boundaries, Pairwise Combinations, Workloads | M6 | Project Pattern / Testing |
| 32 | Adversarial Hardening (Tier 5) | White-box stress testing, memory leak audits, Android LMK pressure tests, network recovery checks | M6 | Project Pattern / Testing |

---

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Polar Core Engine & Whitelabeling | Embedded `youtubedl-android` ARM64 runtime, 16KB page alignment, "Polar Core Engine v2.4", `PolarCommandTranslator` (4 toggle cards), `PolarLogSanitizer`, `PolarExceptionSanitizer` | none | PLANNED |
| M2 | Remaster & CapCut Color LUT Pipeline | CapCut Hald CLUT Level 8 presets (Teal & Orange, Viral Warm Pop, Moody Noir, Studio Bright), 5-stage FFmpeg remaster filtergraph (CAS, eq, haldclut, Lanczos, unsharp), pre-upscale memory optimization, MediaCodec acceleration & fallback | none | PLANNED |
| M3 | Download & Queue Management Subsystem | 2-slot concurrency queue, bulk/playlist extraction, pause/resume/cancel lifecycle, Android 14 `dataSync` Foreground Service with live notification, Scoped Storage MediaStore two-phase publishing | M1 | PLANNED |
| M4 | Modern Jetpack Compose UI & Mascot Branding | Arctic Streamline Material 3 theme, Polar Bear cub mascot (Adaptive Icon, AVD Splash, TopBar, Empty States), 4 Stitch screens (Home, Bottom Sheet, Downloads & Queue, Settings & Dev Console) | M1, M2, M3 | PLANNED |
| M5 | Isolated Licensing Kill-Switch & Silent OTA | Dedicated Cloudflare D1/Worker licensing authority, HMAC-SHA256 verification, 7-day offline grace period, background GitHub OTA via PackageInstaller sessions, zero-ad Milestone 1 enforcement | none | PLANNED |
| M6 | Final E2E Test Pass & Adversarial Hardening | Phase 1: 100% pass of E2E test suite (Tiers 1-4: Feature, Boundary, Combinations, Real-World Workloads). Phase 2: Tier 5 adversarial hardening (LMK pressure, memory audits, network resilience) | M1, M2, M3, M4, M5 | PLANNED |

---

## Interface Contracts

### 1. Presentation Layer ↔ Download Queue Subsystem (`M4 ↔ M3`)
```kotlin
package com.trandif.polarsnap.domain.queue

import kotlinx.coroutines.flow.StateFlow

data class DownloadTask(
    val id: String,
    val url: String,
    val title: String,
    val channel: String,
    val thumbnailUrl: String,
    val selectedFormat: SelectedFormat,
    val options: EngineOptions,
    val state: TaskState,
    val progress: Float, // 0.0f .. 1.0f
    val speedBytesPerSec: Long,
    val etaSeconds: Long,
    val totalBytes: Long,
    val downloadedBytes: Long,
    val activePhase: DownloadPhase // FetchingMetadata, Downloading, Remastering, Finalizing, Completed, Failed
)

interface DownloadQueueManager {
    val activeTasks: StateFlow<List<DownloadTask>>
    val completedTasks: StateFlow<List<DownloadTask>>
    val totalThroughputBytesPerSec: StateFlow<Long>

    suspend fun enqueue(request: DownloadRequest): String
    suspend fun enqueueBatch(requests: List<DownloadRequest>): List<String>
    suspend fun pause(taskId: String)
    suspend fun resume(taskId: String)
    suspend fun cancel(taskId: String)
    suspend fun retry(taskId: String)
    suspend fun clearCompleted()
}
```

### 2. Download Queue ↔ Polar Core Engine Subsystem (`M3 ↔ M1`)
```kotlin
package com.trandif.polarsnap.domain.engine

data class EngineOptions(
    val turboAcceleration: Boolean = true,
    val losslessAudio: Boolean = false,
    val cleanWatermark: Boolean = true,
    val sponsorStripper: Boolean = true,
    val customFormatContainer: FormatContainer = FormatContainer.MP4,
    val resolutionLimit: ResolutionLimit = ResolutionLimit.RES_1080P
)

data class SanitizedStreamEvent(
    val progressPercent: Float,
    val speedFormatted: String,
    val etaFormatted: String,
    val totalSizeFormatted: String,
    val statusMessage: String
)

interface PolarEngine {
    suspend fun initialize(): Result<Unit>
    suspend fun fetchMetadata(url: String): Result<MediaMetadata>
    suspend fun executeDownload(
        url: String,
        options: EngineOptions,
        outputDir: String,
        onProgress: (SanitizedStreamEvent) -> Unit
    ): Result<DownloadedArtifact>
    suspend fun cancelDownload(taskId: String)
}
```

### 3. Core Engine / Queue ↔ FFmpeg Remaster Subsystem (`M3 / M1 ↔ M2`)
```kotlin
package com.trandif.polarsnap.domain.remaster

enum class CapCutPreset {
    NONE,
    TEAL_AND_ORANGE,
    VIRAL_WARM_POP,
    MOODY_NOIR,
    STUDIO_BRIGHT
}

data class RemasterConfig(
    val enableSuperResolution: Boolean = true, // Lanczos 4K upscale
    val targetResolution: TargetResolution = TargetResolution.UHD_4K,
    val enableSharpening: Boolean = true,
    val colorGradingPreset: CapCutPreset = CapCutPreset.NONE,
    val lutIntensity: Float = 1.0f // 0.0f .. 1.0f
)

interface RemasterPipeline {
    suspend fun processMedia(
        sourceFile: String,
        destinationFile: String,
        config: RemasterConfig,
        onProgress: (Float) -> Unit
    ): Result<String>
}
```

### 4. Application ↔ Cloudflare Licensing & OTA Subsystem (`M4 / M3 ↔ M5`)
```kotlin
package com.trandif.polarsnap.domain.licensing

data class LicenseStatus(
    val isAuthorized: Boolean,
    val isKillSwitchTriggered: Boolean,
    val offlineGraceExpiresAt: Long,
    val statusMessage: String
)

data class UpdateInfo(
    val isUpdateAvailable: Boolean,
    val latestVersionName: String,
    val latestVersionCode: Int,
    val releaseNotes: String,
    val downloadUrl: String,
    val sha256Checksum: String
)

interface LicensingAuthority {
    suspend fun verifyDeviceAuthorization(deviceId: String): Result<LicenseStatus>
    suspend fun checkForOtaUpdate(): Result<UpdateInfo>
    suspend fun installOtaUpdateSilently(apkPath: String): Result<Unit>
}
```

---

## Code Layout
```
app/
├── src/main/
│   ├── AndroidManifest.xml
│   ├── assets/
│   │   └── luts/
│   │       ├── teal_and_orange.png       # 512x512 Hald CLUT Level 8
│   │       ├── viral_warm_pop.png        # 512x512 Hald CLUT Level 8
│   │       ├── moody_noir.png            # 512x512 Hald CLUT Level 8
│   │       └── studio_bright.png         # 512x512 Hald CLUT Level 8
│   ├── java/com/trandif/polarsnap/
│   │   ├── PolarSnapApp.kt
│   │   ├── core/
│   │   │   ├── engine/                   # M1: Polar Core Engine & Whitelabeling
│   │   │   │   ├── PolarCoreEngine.kt
│   │   │   │   ├── PolarCommandTranslator.kt
│   │   │   │   ├── PolarLogSanitizer.kt
│   │   │   │   └── PolarExceptionSanitizer.kt
│   │   │   ├── remaster/                 # M2: FFmpeg Remaster & CapCut LUT Pipeline
│   │   │   │   ├── FFmpegRemasterPipeline.kt
│   │   │   │   ├── FiltergraphBuilder.kt
│   │   │   │   ├── MediaCodecEncoderSelector.kt
│   │   │   │   └── HaldClutManager.kt
│   │   │   ├── queue/                    # M3: Download & Queue Manager
│   │   │   │   ├── DownloadQueueManagerImpl.kt
│   │   │   │   ├── DownloadTaskWorker.kt
│   │   │   │   ├── DownloadForegroundService.kt
│   │   │   │   └── MediaStorePublisher.kt
│   │   │   └── licensing/                # M5: Cloudflare Licensing & OTA Updater
│   │   │       ├── CloudflareLicensingAuthority.kt
│   │   │       ├── HmacSigner.kt
│   │   │       ├── LocalLicenseStore.kt
│   │   │       └── SilentOtaManager.kt
│   │   ├── domain/                       # Shared Models & Interfaces
│   │   │   ├── model/
│   │   │   └── repository/
│   │   └── ui/                           # M4: Jetpack Compose Presentation Layer
│   │       ├── theme/
│   │       │   ├── Color.kt              # Arctic Streamline Palette
│   │       │   ├── Theme.kt
│   │       │   ├── Type.kt
│   │       │   └── Shape.kt
│   │       ├── navigation/
│   │       │   └── PolarSnapNavGraph.kt
│   │       ├── components/
│   │       │   ├── PolarCubMascot.kt
│   │       │   ├── MultiGradientProgress.kt
│   │       │   ├── TelemetrySpeedHub.kt
│   │       │   └── FeatureToggleCard.kt
│   │       └── screens/
│   │           ├── home/ScreenHome.kt
│   │           ├── download/ScreenDownloads.kt
│   │           ├── settings/ScreenSettings.kt
│   │           └── bottomsheet/ConfigureBottomSheet.kt
│   └── res/
│       ├── drawable/                     # Mascot vectors, icons, AVD splash
│       └── values/
cloudflare/                               # M5: Isolated Cloudflare Licensing Worker
├── wrangler.toml
├── schema.sql                            # D1 SQL Schema
└── src/
    └── index.ts                          # Isolated Licensing Worker
tests/                                    # M6: Comprehensive E2E Testing Track
├── e2e/
│   ├── tier1_features/
│   ├── tier2_boundaries/
│   ├── tier3_combinations/
│   └── tier4_workloads/
└── adversarial/                          # Tier 5 Hardening
```
