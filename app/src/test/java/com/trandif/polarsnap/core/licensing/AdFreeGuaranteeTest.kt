package com.trandif.polarsnap.core.licensing

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

class AdFreeGuaranteeTest {

    private val forbiddenAdKeywords = listOf(
        "com.monetag",
        "monetag",
        "com.google.android.gms.ads",
        "com.unity3d.ads",
        "com.applovin",
        "com.facebook.ads",
        "AdMob",
        "AdView",
        "BannerAd",
        "InterstitialAd"
    )

    @Test
    fun testZeroMonetagAndAdTokensInLicensingPackage() {
        val projectDir = File(".")
        val licensingDir = File(projectDir, "app/src/main/java/com/trandif/polarsnap/core/licensing")
        val domainLicensingDir = File(projectDir, "app/src/main/java/com/trandif/polarsnap/domain/licensing")

        val filesToScan = mutableListOf<File>()
        if (licensingDir.exists()) filesToScan.addAll(licensingDir.walkTopDown().filter { it.isFile }.toList())
        if (domainLicensingDir.exists()) filesToScan.addAll(domainLicensingDir.walkTopDown().filter { it.isFile }.toList())

        assertTrue("Source files should exist for scanning", filesToScan.isNotEmpty())

        val violations = mutableListOf<String>()

        for (file in filesToScan) {
            val content = file.readText()
            for (keyword in forbiddenAdKeywords) {
                if (content.contains(keyword, ignoreCase = true)) {
                    violations.add("Found forbidden ad keyword '$keyword' in ${file.name}")
                }
            }
        }

        assertTrue("Zero ad violations allowed. Violations: $violations", violations.isEmpty())
    }

    @Test
    fun testAdScannerDetectsProhibitedTokens() {
        val dummyDirtySource = "import com.monetag.mobile.ads.AdView;"
        var detected = false
        for (keyword in forbiddenAdKeywords) {
            if (dummyDirtySource.contains(keyword, ignoreCase = true)) {
                detected = true
                break
            }
        }
        assertTrue("Ad scanner must detect forbidden Monetag import", detected)
    }
}
