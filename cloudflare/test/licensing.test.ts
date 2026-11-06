import { describe, it, beforeEach } from "node:test";
import assert from "node:assert/strict";
import worker, {
  computeHmacSha256,
  buildCanonicalRequestString,
  buildCanonicalResponseString,
  compareSemVer,
  constantTimeCompare,
  Env,
  VerifyRequestBody
} from "../src/index.ts";

// In-Memory D1 Mock Database for TypeScript test execution
function createMockD1(): any {
  const nonces = new Map<string, number>();
  const devices = new Map<string, any>();
  const policies = new Map<string, string>([
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
    prepare(query: string) {
      const q = query.trim();
      let boundParams: any[] = [];

      const stmt = {
        bind(...params: any[]) {
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

describe("Cloudflare Worker — PolarSnap Licensing & Kill-Switch Authority (TS)", () => {
  const SECRET = "test_polarsnap_secret_key_123";
  let mockDb: any;
  let env: Env;

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
    const body: any = await res.json();
    assert.equal(body.status, "ok");
    assert.equal(body.service, "polarsnap-licensing");
    assert.equal(body.isolated, true);
    assert.ok(typeof body.server_time === "number");
  });

  it("should verify valid client HMAC-SHA256 signature and return AUTHORIZED status", async () => {
    const now = Math.floor(Date.now() / 1000);
    const rawReq: VerifyRequestBody = {
      device_hash: "polar_dev_001_abc",
      app_version: "2.4.0",
      build_number: 240,
      timestamp: now,
      nonce: "nonce_valid_001",
      signature: ""
    };
    const canonical = buildCanonicalRequestString(rawReq);
    rawReq.signature = await computeHmacSha256(SECRET, canonical);

    const req = new Request("https://licensing.polarsnap.app/api/v1/license/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(rawReq)
    });

    const res = await worker.fetch(req, env);
    assert.equal(res.status, 200);
    const body: any = await res.json();
    assert.equal(body.status, "AUTHORIZED");
    assert.equal(body.kill_switch, false);
    assert.equal(body.min_version, "2.4.0");
    assert.ok(body.valid_until > now + 600000); // 7-day grace period
  });
});
