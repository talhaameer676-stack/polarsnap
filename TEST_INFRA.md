# TEST_INFRA — PolarSnap Testing Infrastructure & Methodology Specification

## 1. Executive Summary & Purpose
This document defines the authoritative End-to-End (E2E) testing infrastructure, philosophy, methodology, and verification matrix for **PolarSnap — by Trandif** (`com.trandif.polarsnap`).

The PolarSnap test suite guarantees that all 32 commercial features specified in `PROJECT.md` operate with absolute functional correctness, boundary resilience, multi-subsystem interoperability, and real-world stability. The test harness runs independently of private implementation details, treating the system as an opaque box driven by public interfaces, contracts, configuration parameters, and observable outputs.

---

## 2. Core Test Philosophy

### 2.1 Opaque-Box & Contract-Driven Verification
- **Zero Internals Coupling**: Tests never inspect private properties, reflection fields, or internal class decorators. Tests interface strictly with public contracts, domain models, CLI invocations, serialized data schemas, file system artifacts, and network payloads.
- **Requirement-Driven Assertions**: Every assertion maps directly to an explicit requirement in `PROJECT.md` or `ORIGINAL_REQUEST.md`.
- **Expected Output Derivation**: Expected outputs are derived authoritatively from mathematical formulas (e.g. bijective LUT coordinates, Lanczos scaling ratios, RAM calculation), RFC/security standards (HMAC-SHA256, ISO 8601 timestamps), Android OS platform contracts (API 34 Scoped Storage `IS_PENDING`, `dataSync` foreground service), and regex scrubbing rules.

### 2.2 Progressive Testability & Deterministic Isolation
- **Self-Contained Execution**: Each test sets up its own isolated state, isolated temp directory, and mock boundaries, eliminating execution order dependencies.
- **Progressive Milestone Verification**: Tests can execute against discrete subsystem contracts (M1 through M5) independently or in holistic integration (M6).
- **Zero Flakiness**: Time-dependent assertions use monotonic clocks, injected time providers, and bounded virtual clock advances. Non-deterministic properties (random nonces, temp file paths) are verified via formal schemas and regex pattern validators.

### 2.3 Adversarial Integrity
- **No Facade or Dummy Tests**: Facade tests that trivially return `true` or pass without validating actual logic are strictly forbidden.
- **Strict Oracles**: Every test asserts both positive success invariants and negative error-rejection invariants.
- **Independent Runner**: Tests run via an independent, self-contained test engine (`tests/e2e/runner.py`) executable on any workstation or CI runner without external dependencies.

---

## 3. Testing Methodologies

### 3.1 Tier 1: Category-Partition Method (TSL)
Every feature's input space is categorized into independent partitions and parameter choices:
1. **Domain Parameters**: Primary inputs, format selections, toggle switches, and network URIs.
2. **Environment Conditions**: Network state (online, offline, throttled), hardware encoder availability (MediaCodec HEVC/H.264, software fallback), and storage permissions.
3. **Partition Coverage**: Minimum 5 tests per feature covering valid equivalence classes, distinct operational modes, and contract invariants.

### 3.2 Tier 2: Boundary Value Analysis (BVA) & Corner Cases
Critical thresholds and stress boundaries are tested at `[min-1, min, nominal, max, max+1]`:
- **Length & String Boundaries**: Empty URLs, 8192-char URLs, null characters, UTF-8 emoji streams, shell metacharacter injections.
- **Resource & Hardware Limits**: 4K UHD frame memory exhaustion (24.88 MB unoptimized vs 6.22 MB optimized), 2-slot concurrency ceiling, 16 aria2c sub-sockets saturation, 0 fps edge streams.
- **Time & Clock Skew Boundaries**: Replay nonce collisions, timestamp drift at exactly `T - 301s`, `T - 300s`, `T + 300s`, `T + 301s`, and 7-day offline grace expiry at `604800s`.
- **Stream Integrity**: Corrupted video containers, truncated Hald CLUT PNGs, non-16KB ELF binaries, partial aria2c downloads.

### 3.3 Tier 3: Pairwise Combinatorial Interaction Testing (Orthogonal Arrays)
Complex multi-feature interactions are generated using pairwise combinatorial techniques:
- **Combinatorial Orthogonal Matrix**: `PolarCommandTranslator` flags x `RemasterPipeline` filters x `DownloadQueueManager` slots x `MediaStorePublisher` phases x `LicensingAuthority` status.
- **Critical Conflict Tests**: Concurrency saturation during 4K remastering, pause/resume across network drops, and silent OTA background downloads while video remastering is in progress.

### 3.4 Tier 4: Real-World Workload Scenarios
Multi-step end-to-end user journeys mirroring actual daily usage:
- **Scenario A (Viral 4K Remaster Workflow)**: URL paste -> Bottom sheet 4K selection -> Teal & Orange CapCut grading -> Lanczos 4K scaling -> MediaStore Movies export.
- **Scenario B (Social Media Watermark & Lossless Audio Extraction)**: TikTok/IG URL -> Clean Watermark toggle -> Lossless Audio toggle (FLAC) -> Metadata tag embedding -> Music directory export.
- **Scenario C (High-Throughput Playlist Batch)**: 20-video playlist extraction -> Bounded 2-slot queueing -> Live throughput notification -> Selective cancellation & resume.
- **Scenario D (Licensing Grace & Silent In-App Update)**: Air-gapped offline operation (Day 1-7) -> Grace expiry -> Reconnect & HMAC auth -> Background GitHub release check -> Silent APK verification.

---

## 4. Feature Inventory Coverage Mapping (All 32 Features)

| Feature # | Feature Name | Milestone | Tier 1 (TSL Tests) | Tier 2 (Boundary Tests) | Tier 3 (Pairwise Tests) | Tier 4 (Workloads) |
|:---:|:---|:---:|:---|:---|:---|:---|
| **1** | Embedded ARM64 Engine | M1 | >=5 | >=5 | Pairwise with M3 Queue | Workflow A, C |
| **2** | Whitelabeled Engine Rebranding | M1 | >=5 | >=5 | Pairwise with UI/Logs | Workflow A, B, C, D |
| **3** | Turbo Acceleration Toggle Card | M1 | >=5 | >=5 | Pairwise with Multi-Socket | Workflow A, C |
| **4** | Lossless Audio Toggle Card | M1 | >=5 | >=5 | Pairwise with Scoped Storage | Workflow B |
| **5** | Clean Watermark Toggle Card | M1 | >=5 | >=5 | Pairwise with Crop Pipeline | Workflow B |
| **6** | Sponsor Stripper Toggle Card | M1 | >=5 | >=5 | Pairwise with Metadata Splicing| Workflow A, C |
| **7** | Zero-Leak Log Scrubber | M1 | >=5 | >=5 | Pairwise with All Errors/Logs | Workflow A, B, C, D |
| **8** | Domain Exception Sanitizer | M1 | >=5 | >=5 | Pairwise with HTTP 429/403/500 | Workflow A, D |
| **9** | CapCut LUT Asset Bundling | M2 | >=5 | >=5 | Pairwise with Filtergraph | Workflow A |
| **10** | Bijective LUT Transformer | M2 | >=5 | >=5 | Pairwise with 64^3 Transform | Workflow A |
| **11** | FFmpeg 4K/HD Remaster Filtergraph| M2 | >=5 | >=5 | Pairwise with MediaCodec | Workflow A |
| **12** | Pre-Upscale Memory Optimization| M2 | >=5 | >=5 | Pairwise with 4K Render | Workflow A |
| **13** | ARM64 MediaCodec Acceleration | M2 | >=5 | >=5 | Pairwise with 3-Tier Fallback | Workflow A |
| **14** | Uncompressed 4K Master Extract | M2 | >=5 | >=5 | Pairwise with Container Switch | Workflow A |
| **15** | Bounded Concurrency Queue | M3 | >=5 | >=5 | Pairwise with 16 Sub-Sockets | Workflow C |
| **16** | Bulk / Playlist Batch Processor| M3 | >=5 | >=5 | Pairwise with State Flow | Workflow C |
| **17** | Download Lifecycle Control | M3 | >=5 | >=5 | Pairwise with Network Reconnect| Workflow C |
| **18** | Foreground Service Notification| M3 | >=5 | >=5 | Pairwise with Telemetry | Workflow A, C |
| **19** | Scoped Storage MediaStore Export| M3 | >=5 | >=5 | Pairwise with Two-Phase Publish| Workflow A, B, C |
| **20** | Arctic Streamline Design System| M4 | >=5 | >=5 | Pairwise with Compose Theme | Workflow A, B, C, D |
| **21** | Polar Bear Cub Mascot Branding | M4 | >=5 | >=5 | Pairwise with Empty States | Workflow A, B, C, D |
| **22** | Main Home Screen (Screen 4) | M4 | >=5 | >=5 | Pairwise with Paste Dock | Workflow A, B, C |
| **23** | Pre-Download Bottom Sheet (3) | M4 | >=5 | >=5 | Pairwise with Resolution Switch| Workflow A, B |
| **24** | Downloads & Queue Screen (1) | M4 | >=5 | >=5 | Pairwise with Telemetry Hub | Workflow C |
| **25** | Settings & Config Screen (2) | M4 | >=5 | >=5 | Pairwise with 7-Tap Dev Console| Workflow D |
| **26** | Isolated Cloudflare Licensing | M5 | >=5 | >=5 | Pairwise with D1 Contract | Workflow D |
| **27** | HMAC Signature & Replay Prevention| M5 | >=5 | >=5 | Pairwise with Nonce Tracker | Workflow D |
| **28** | Offline Grace Period Protocol | M5 | >=5 | >=5 | Pairwise with Cache Cipher | Workflow D |
| **29** | Silent In-App GitHub OTA Updater| M5 | >=5 | >=5 | Pairwise with PackageInstaller | Workflow D |
| **30** | Milestone 1 Ad-Free Guarantee | M5 | >=5 | >=5 | Pairwise with AST Static Scan | Workflow A, B, C, D |
| **31** | End-to-End Test Suite (Tiers 1-4)| M6 | >=5 | >=5 | Meta-validation across Tiers | All Workflows |
| **32** | Adversarial Hardening (Tier 5) | M6 | >=5 | >=5 | LMK / Memory / Injection | All Workflows |

---

## 5. Test Suite Architecture & Directory Layout

```
tests/
└── e2e/
    ├── runner.py                          # Master test runner with tier filtering & metrics reporting
    ├── contracts/                         # Formal schema validators, oracles, and pure reference models
    │   ├── __init__.py
    │   ├── engine_contracts.py            # M1: Command translator, log scrubbing, exception mapping
    │   ├── remaster_contracts.py          # M2: Bijective LUT formula, filtergraph syntax, RAM formulas
    │   ├── queue_contracts.py             # M3: 2-slot concurrency, state machine, MediaStore publishing
    │   ├── ui_contracts.py                # M4: Arctic palette, mascot states, MVI action-state contracts
    │   └── licensing_contracts.py         # M5: HMAC-SHA256, nonce tracking, grace timer, OTA checksum
    ├── tier1_features/                    # Tier 1: Feature Coverage (>=5 tests per feature, >=160 tests)
    │   ├── __init__.py
    │   ├── test_m1_core_engine.py         # Features 1-8
    │   ├── test_m2_remaster_lut.py        # Features 9-14
    │   ├── test_m3_queue_subsystem.py     # Features 15-19
    │   ├── test_m4_ui_branding.py         # Features 20-25
    │   ├── test_m5_licensing_ota.py       # Features 26-30
    │   └── test_m6_test_hardening.py      # Features 31-32
    ├── tier2_boundaries/                  # Tier 2: Boundary Value & Corner Cases (>=5 tests per feature)
    │   ├── __init__.py
    │   ├── test_m1_boundaries.py          # Boundaries for Features 1-8
    │   ├── test_m2_boundaries.py          # Boundaries for Features 9-14
    │   ├── test_m3_boundaries.py          # Boundaries for Features 15-19
    │   ├── test_m4_boundaries.py          # Boundaries for Features 20-25
    │   ├── test_m5_boundaries.py          # Boundaries for Features 26-30
    │   └── test_m6_boundaries.py          # Boundaries for Features 31-32
    ├── tier3_combinations/                # Tier 3: Pairwise Combinations & Concurrency Interactions
    │   ├── __init__.py
    │   ├── test_pairwise_pipeline.py      # Full pipeline combinatorial matrix (>=16 tests)
    │   └── test_state_transitions.py      # Cross-feature lifecycle & error state matrix (>=16 tests)
    └── tier4_workloads/                   # Tier 4: Real-World Comprehensive Workload Scenarios
        ├── __init__.py
        ├── test_workload_youtube_4k_remaster.py         # Workflow A
        ├── test_workload_instagram_watermark_audio.py   # Workflow B
        ├── test_workload_playlist_batch_export.py       # Workflow C
        └── test_workload_licensing_ota_lifecycle.py     # Workflow D
```

---

## 6. Runner Execution Guide

### 6.1 Running the Full Test Suite
The standalone test runner discovers and executes all test tiers, tabulating metrics in real-time:
```bash
python tests/e2e/runner.py
```

### 6.2 Filtered Execution by Tier
```bash
# Run Tier 1 only (Feature Coverage)
python tests/e2e/runner.py --tier 1

# Run Tier 2 only (Boundary & Corner Cases)
python tests/e2e/runner.py --tier 2

# Run Tier 3 only (Pairwise Combinations)
python tests/e2e/runner.py --tier 3

# Run Tier 4 only (Real-World Workloads)
python tests/e2e/runner.py --tier 4
```

### 6.3 Filtered Execution by Feature
```bash
# Run all tests covering Feature 10 (Bijective LUT)
python tests/e2e/runner.py --feature 10

# Run all tests covering Milestone 1
python tests/e2e/runner.py --milestone M1
```

### 6.4 Structured Machine Output (JSON)
For CI/CD pipelines, forensic auditing, and automated gating:
```bash
python tests/e2e/runner.py --json-output test_results.json
```

---

## 7. Quality Gates & Standard Metrics

Every run must satisfy the following invariant criteria:
1. **0 Failures & 0 Errors**: All assertions must pass cleanly.
2. **Coverage Completeness**: 100% of the 32 features must be executed and asserted.
3. **Execution Time**: The complete synthetic/mocked E2E test suite should execute within < 30 seconds on modern multicore CPUs.
4. **Leak Verification**: 0 occurrences of "yt-dlp", "Python", or raw unscrubbed binary paths in sanitized outputs.
5. **Ad-Free Gate**: 0 occurrences of Monetag or foreign ad SDK imports across all scan paths.
