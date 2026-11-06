import { describe, it, beforeEach } from "node:test";
import assert from "node:assert/strict";
import worker, {
  computeHmacSha256,
  buildCanonicalRequestString,
  buildCanonicalResponseString,
  compareSemVer,
  constantTimeCompare
} from "../src/index.ts";

// In-Memory D1 Mock Database
function createMockD1() {
  const nonces = new Map();
  const devices = new Map();
  const policies = new Map([
    ["kill_switch_active", "false"],
    ["min_supported_version", "2.4.0"],
    ["emergency_announcement", ""],
    ["engine_hotpatch_version", "2024.11.04"],
    ["engine_hotpatch_url", "https://releases.polarsnap.app/engine/2024.11.04/usr.zip"]
  ]);

  return {
    nonces,
    devices,
    policies,
    prepare(query) {
      const q = query.trim();
      let boundParams = [];

      const stmt = {
        bind(...params) {
          boundParams = params;
          return stmt;
        },
        async first() {
          if (q.includes("SELECT nonce FROM request_nonces")) {
            const nonce = boundParams[0];
            if (nonces.has(nonce)) return { nonce };
            return null;
          }
          if (q.includes("SELECT device_hash, status, license_tier, revocation_reason FROM devices")) {
            const hash = boundParams[0];
            return devices.get(hash) || null;
          }
          return null;
        },
        async all() {
          if (q.includes("SELECT policy_key, policy_value FROM global_policy")) {
            const results = [];
            for (const [key, value] of policies.entries()) {
              results.push({ policy_key: key, policy_value: value });
            }
            return { results };
          }
          return { results: [] };
        },
        async run() {
          if (q.includes("INSERT INTO request_nonces")) {
            const [nonce, created_at] = boundParams;
            nonces.set(nonce, created_at);
            return { success: true };
          }
          if (q.includes("DELETE FROM request_nonces")) {
            const [olderThan] = boundParams;
            for (const [n, created] of nonces.entries()) {
              if (created < olderThan) nonces.delete(n);
            }
            return { success: true };
          }
          if (q.includes("INSERT INTO devices")) {
            const [device_hash, app_version, first_seen, last_seen, ip_country] = boundParams;
            devices.set(device_hash, {
              device_hash,
              app_version,
              first_seen,
              last_seen,
              status: "ACTIVE",
              license_tier: "FREE",
              revocation_reason: null,
              ip_country
            });
            return { success: true };
          }
          if (q.includes("UPDATE devices SET")) {
            const [last_seen, app_version, ip_country, device_hash] = boundParams;
            const existing = devices.get(device_hash);
            if (existing) {
              existing.last_seen = last_seen;
              existing.app_version = app_version;
              existing.ip_country = ip_country;
            }
            return { success: true };
          }
          return { success: true };
        }
      };

      return stmt;
    }
  };
}

describe("Cloudflare Worker — PolarSnap Licensing & Kill-Switch Authority", () => {
  const SECRET = "test_polarsnap_secret_key_123";
  let mockDb;
  let env;

  beforeEach(() => {
    mockDb = createMockD1();
    env = {
      DB: mockDb,
      POLARSNAP_HMAC_SECRET: SECRET,
      POLARSNAP_APP_NAME: "PolarSnap — by Trandif",
      MIN_CLIENT_VERSION: "2.4.0",
      MAX_TIMESTAMP_DRIFT_SEC: 300,
      OFFLINE_GRACE_PERIOD_SEC: 604800
    };
  });

  it("should respond to GET /health with isolated status and timestamp", async () => {
    const req = new Request("https://licensing.polarsnap.app/health");
    const res = await worker.fetch(req, env);
    assert.equal(res.status, 200);
    const body = await res.json();
    assert.equal(body.status, "ok");
    assert.equal(body.service, "polarsnap-licensing");
    assert.equal(body.isolated, true);
    assert.ok(typeof body.server_time === "number");
  });

  it("should respond to GET /api/v1/releases/latest with OTA release metadata", async () => {
    const req = new Request("https://licensing.polarsnap.app/api/v1/releases/latest?current_version=2.4.0&current_code=240");
    const res = await worker.fetch(req, env);
    assert.equal(res.status, 200);
    const body = await res.json();
    assert.equal(body.is_update_available, true);
    assert.equal(body.latest_version_name, "2.4.1");
    assert.equal(body.latest_version_code, 241);
    assert.ok(body.download_url.includes(".apk"));
    assert.ok(body.sha256_checksum.length === 64);
  });

  it("should verify valid client HMAC-SHA256 signature and return AUTHORIZED status", async () => {
    const now = Math.floor(Date.now() / 1000);
    const rawReq = {
      device_hash: "polar_dev_001_abc",
      app_version: "2.4.0",
      build_number: 240,
      timestamp: now,
      nonce: "nonce_valid_001"
    };
    const canonical = buildCanonicalRequestString(rawReq);
    const signature = await computeHmacSha256(SECRET, canonical);

    const req = new Request("https://licensing.polarsnap.app/api/v1/license/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...rawReq, signature })
    });

    const res = await worker.fetch(req, env);
    assert.equal(res.status, 200);
    const body = await res.json();
    assert.equal(body.status, "AUTHORIZED");
    assert.equal(body.kill_switch, false);
    assert.equal(body.min_version, "2.4.0");
    assert.ok(body.valid_until > now + 600000); // 7-day grace period

    // Verify server signature
    const canonicalResp = buildCanonicalResponseString(
      body.status,
      body.kill_switch,
      body.valid_until,
      body.server_time,
      rawReq.nonce
    );
    const expectedServerSig = await computeHmacSha256(SECRET, canonicalResp);
    assert.equal(body.signature, expectedServerSig);
  });

  it("should reject tampered payload or invalid HMAC signature with 401", async () => {
    const now = Math.floor(Date.now() / 1000);
    const rawReq = {
      device_hash: "polar_dev_002_tamper",
      app_version: "2.4.0",
      build_number: 240,
      timestamp: now,
      nonce: "nonce_tamper_002",
      signature: "000000000000000000000000000000000000000000000000000000000000dead"
    };

    const req = new Request("https://licensing.polarsnap.app/api/v1/license/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(rawReq)
    });

    const res = await worker.fetch(req, env);
    assert.equal(res.status, 401);
    const body = await res.json();
    assert.equal(body.code, "INVALID_SIGNATURE");
  });

  it("should reject requests exceeding timestamp drift window (+/- 300s) with 400", async () => {
    const now = Math.floor(Date.now() / 1000);
    const expiredTimestamp = now - 350; // 350s in the past (> 300s)

    const rawReq = {
      device_hash: "polar_dev_003_drift",
      app_version: "2.4.0",
      build_number: 240,
      timestamp: expiredTimestamp,
      nonce: "nonce_drift_003"
    };
    const canonical = buildCanonicalRequestString(rawReq);
    const signature = await computeHmacSha256(SECRET, canonical);

    const req = new Request("https://licensing.polarsnap.app/api/v1/license/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...rawReq, signature })
    });

    const res = await worker.fetch(req, env);
    assert.equal(res.status, 400);
    const body = await res.json();
    assert.equal(body.code, "TIMESTAMP_DRIFT_EXCEEDED");
  });

  it("should reject replay attacks when the same nonce is presented twice with 409", async () => {
    const now = Math.floor(Date.now() / 1000);
    const rawReq = {
      device_hash: "polar_dev_004_replay",
      app_version: "2.4.0",
      build_number: 240,
      timestamp: now,
      nonce: "single_use_nonce_999"
    };
    const canonical = buildCanonicalRequestString(rawReq);
    const signature = await computeHmacSha256(SECRET, canonical);

    const makeReq = () => new Request("https://licensing.polarsnap.app/api/v1/license/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...rawReq, signature })
    });

    // 1st request -> Success
    const res1 = await worker.fetch(makeReq(), env);
    assert.equal(res1.status, 200);

    // 2nd request with same nonce -> 409 Nonce Replay
    const res2 = await worker.fetch(makeReq(), env);
    assert.equal(res2.status, 409);
    const body2 = await res2.json();
    assert.equal(body2.code, "NONCE_REPLAY_DETECTED");
  });

  it("should immediately enforce global kill-switch when kill_switch_active is true", async () => {
    mockDb.policies.set("kill_switch_active", "true");

    const now = Math.floor(Date.now() / 1000);
    const rawReq = {
      device_hash: "polar_dev_005_killswitch",
      app_version: "2.4.0",
      build_number: 240,
      timestamp: now,
      nonce: "nonce_killswitch_005"
    };
    const canonical = buildCanonicalRequestString(rawReq);
    const signature = await computeHmacSha256(SECRET, canonical);

    const req = new Request("https://licensing.polarsnap.app/api/v1/license/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...rawReq, signature })
    });

    const res = await worker.fetch(req, env);
    assert.equal(res.status, 200);
    const body = await res.json();
    assert.equal(body.kill_switch, true);
    assert.equal(body.status, "REVOKED");
  });

  it("should return OUTDATED_VERSION if client app_version is below min_supported_version", async () => {
    mockDb.policies.set("min_supported_version", "2.5.0");

    const now = Math.floor(Date.now() / 1000);
    const rawReq = {
      device_hash: "polar_dev_006_outdated",
      app_version: "2.4.0", // 2.4.0 < 2.5.0
      build_number: 240,
      timestamp: now,
      nonce: "nonce_outdated_006"
    };
    const canonical = buildCanonicalRequestString(rawReq);
    const signature = await computeHmacSha256(SECRET, canonical);

    const req = new Request("https://licensing.polarsnap.app/api/v1/license/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...rawReq, signature })
    });

    const res = await worker.fetch(req, env);
    assert.equal(res.status, 200);
    const body = await res.json();
    assert.equal(body.status, "OUTDATED_VERSION");
    assert.equal(body.kill_switch, false);
  });

  it("should enforce REVOKED device status for blacklisted device_hash", async () => {
    mockDb.devices.set("banned_device_999", {
      device_hash: "banned_device_999",
      app_version: "2.4.0",
      first_seen: 1000,
      last_seen: 2000,
      status: "REVOKED",
      license_tier: "FREE",
      revocation_reason: "Fraudulent activity detected",
      ip_country: "US"
    });

    const now = Math.floor(Date.now() / 1000);
    const rawReq = {
      device_hash: "banned_device_999",
      app_version: "2.4.0",
      build_number: 240,
      timestamp: now,
      nonce: "nonce_revoked_007"
    };
    const canonical = buildCanonicalRequestString(rawReq);
    const signature = await computeHmacSha256(SECRET, canonical);

    const req = new Request("https://licensing.polarsnap.app/api/v1/license/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...rawReq, signature })
    });

    const res = await worker.fetch(req, env);
    assert.equal(res.status, 200);
    const body = await res.json();
    assert.equal(body.status, "REVOKED");
  });

  it("should correctly compare semantic versions in compareSemVer", () => {
    assert.ok(compareSemVer("2.4.0", "2.4.1") < 0);
    assert.ok(compareSemVer("2.4.1", "2.4.0") > 0);
    assert.equal(compareSemVer("2.4.0", "2.4.0"), 0);
    assert.ok(compareSemVer("v2.4.0", "2.4.0") === 0);
    assert.ok(compareSemVer("3.0.0", "2.9.9") > 0);
  });

  it("should verify constant-time comparison helper", () => {
    assert.equal(constantTimeCompare("abcdef", "abcdef"), true);
    assert.equal(constantTimeCompare("abcdef", "abcdeg"), false);
    assert.equal(constantTimeCompare("abc", "abcdef"), false);
  });
});
