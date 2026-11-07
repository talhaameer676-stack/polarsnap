# PolarSnap — by Trandif

<div align="center">
  <img src="app/src/main/res/mipmap-xxxhdpi/ic_launcher.png" width="128" height="128" alt="PolarSnap Mascot Logo" />
  <h3>Arctic-grade video capture, 4K Lanczos remastering, and offline media utility for Android.</h3>
  <p>Whitelabeled • Zero Leaks • Ad-Free Guarantee • Hardware-ID Secured</p>
</div>

---

## ⚡ Overview

**PolarSnap** is an ultra-fast, native Android media downloader and post-processing utility powered by the **Polar Core Engine v2.4**. It transforms video and audio from popular web platforms into crystal-clear 4K visual masterworks through hardware-accelerated Lanczos super-resolution and CapCut Level 8 (512×512) 3D Hald CLUT color grading.

### Key Highlights
- 🐻 **Arctic Mascot Branding**: Custom Polar Bear cub launcher icon and seamless dark Arctic Slate (`#0B0F19`) UI.
- 🚀 **16-Stream Parallel Acceleration**: High-speed segmented downloading engine.
- 🎬 **4K Master Remastering**: Up to 3840×2160 Lanczos scaling with unsharp masking and 3D LUT grading.
- 🔒 **Cloudflare D1 Licensing Authority**: Cryptographically verified hardware ID locking and remote kill-switch protection (`polarsnap-licensing`).
- 🛡️ **Zero Ad Networks**: 100% clean, non-intrusive user experience with zero third-party monetization libraries.
- 📱 **Silent OTA Package Sessions**: In-app self-updating via Android `PackageInstaller`.

---

## 📲 Download & Install

Download the latest release directly from GitHub:

| Architecture | Package | Direct Download |
| :--- | :--- | :--- |
| **All Devices (Universal)** | `PolarSnap-v1.0.0-universal.apk` | [Download APK](https://github.com/talhaameer676-stack/polarsnap/releases/download/v1.0.0/app-universal-debug.apk) |
| **64-bit ARM (Modern Phones)** | `PolarSnap-v1.0.0-arm64-v8a.apk` | [Download APK](https://github.com/talhaameer676-stack/polarsnap/releases/download/v1.0.0/app-arm64-v8a-debug.apk) |
| **32-bit ARM (Legacy Devices)** | `PolarSnap-v1.0.0-armeabi-v7a.apk` | [Download APK](https://github.com/talhaameer676-stack/polarsnap/releases/download/v1.0.0/app-armeabi-v7a-debug.apk) |

> **Local Copy**: If you are on the development workstation, the compiled APK is ready at:  
> `J:\Antigravity 2.0\New folder\PolarSnap-v1.0.0-universal.apk`

---

## 🛠️ Architecture

```
PolarSnap (Native Android)
 ├── UI Layer (Hardware-accelerated Dark Arctic Slate WebView)
 ├── JavaScript Bridge (`PolarSnap` interface to DownloadQueueManager)
 ├── Core Engine (`Polar Core Engine v2.4`)
 │    ├── Multi-stream download workers (16 parallel segments)
 │    └── FFmpeg Remaster Pipeline (Lanczos Super-Resolution + CapCut 3D Hald CLUT)
 └── Licensing Service (Cloudflare Worker + APAC D1 Database)
      └── HMAC-SHA256 Signed HWID Heartbeat & Dynamic Policy
```

---

## 📄 License & Attribution

Copyright © 2026 Trandif. All rights reserved.
