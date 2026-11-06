package com.trandif.polarsnap.core.licensing

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class LocalLicenseStoreTest {

    private lateinit var delegate: InMemoryLicenseStorageDelegate
    private lateinit var store: LocalLicenseStore

    @Before
    fun setUp() {
        delegate = InMemoryLicenseStorageDelegate()
        store = LocalLicenseStore(storage = delegate)
    }

    @Test
    fun testEmptyStoreReturnsUnlicensed() {
        val status = store.loadStatus(currentTimestampSeconds = 1730000000L)
        assertFalse(status.isAuthorized)
        assertFalse(status.isKillSwitchTriggered)
        assertEquals(0L, status.offlineGraceExpiresAt)
    }

    @Test
    fun testOfflineGracePeriodValidWithin7Days() {
        val t0 = 1730000000L
        val graceExpiresAt = t0 + LocalLicenseStore.OFFLINE_GRACE_PERIOD_SECONDS // t0 + 604,800s

        store.saveLicense(
            status = "AUTHORIZED",
            isKillSwitch = false,
            graceExpiresAt = graceExpiresAt,
            verifiedAt = t0,
            tier = "PRO"
        )

        // Day 3 check (259,200s elapsed)
        val day3 = t0 + (3 * 86400L)
        assertTrue("Device on Day 3 must be within grace", store.isWithinGracePeriod(day3))
        val statusDay3 = store.loadStatus(day3)
        assertTrue(statusDay3.isAuthorized)
        assertFalse(statusDay3.isKillSwitchTriggered)

        // Exact boundary check (604,800s elapsed)
        assertTrue("Device on exact 7th day boundary must be within grace", store.isWithinGracePeriod(graceExpiresAt))
    }

    @Test
    fun testOfflineGracePeriodExpiresPast7Days() {
        val t0 = 1730000000L
        val graceExpiresAt = t0 + 604800L

        store.saveLicense(
            status = "AUTHORIZED",
            isKillSwitch = false,
            graceExpiresAt = graceExpiresAt,
            verifiedAt = t0
        )

        // 7 days + 1 second
        val tExpired = graceExpiresAt + 1L
        assertFalse("Grace must expire past 604,800s", store.isWithinGracePeriod(tExpired))

        val statusExpired = store.loadStatus(tExpired)
        assertFalse(statusExpired.isAuthorized)
        assertTrue(statusExpired.statusMessage.contains("expired", ignoreCase = true))
    }

    @Test
    fun testClockTamperingDetectedWhenTimeMovesBackwards() {
        val t0 = 1730000000L
        val graceExpiresAt = t0 + 604800L

        store.saveLicense(
            status = "AUTHORIZED",
            isKillSwitch = false,
            graceExpiresAt = graceExpiresAt,
            verifiedAt = t0
        )

        // User sets clock backwards to before verification
        val tTampered = t0 - 5000L
        assertFalse("Backwards clock manipulation must fail grace validation", store.isWithinGracePeriod(tTampered))
    }

    @Test
    fun testKillSwitchImmediatelyVoidsGracePeriod() {
        val t0 = 1730000000L
        val graceExpiresAt = t0 + 604800L

        store.saveLicense(
            status = "REVOKED",
            isKillSwitch = true,
            graceExpiresAt = graceExpiresAt,
            verifiedAt = t0
        )

        // Even though time is within 7 days, kill-switch overrides
        val day1 = t0 + 3600L
        assertFalse("Kill switch must void grace period immediately", store.isWithinGracePeriod(day1))

        val status = store.loadStatus(day1)
        assertFalse(status.isAuthorized)
        assertTrue(status.isKillSwitchTriggered)
    }

    @Test
    fun testClearWipesLicenseData() {
        store.saveLicense(
            status = "AUTHORIZED",
            isKillSwitch = false,
            graceExpiresAt = 1730604800L,
            verifiedAt = 1730000000L
        )
        store.clear()

        val status = store.loadStatus(1730000000L)
        assertFalse(status.isAuthorized)
    }
}
