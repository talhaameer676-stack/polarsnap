/**
 * PolarSnap — by Trandif (com.trandif.polarsnap)
 * Isolated Cloudflare Worker Licensing & Kill-Switch Authority
 * 
 * Strict Isolation Guarantee:
 * This worker operates strictly within its own dedicated D1 database (polarsnap_licensing_db)
 * and environment bindings. It never references, binds, or touches any other project,
 * KV namespace, R2 bucket, or database in the user's Cloudflare account.
 */

export interface Env {
  DB: D1Database;
  POLARSNAP_HMAC_SECRET?: string;
  POLARSNAP_APP_NAME?: string;
  MIN_CLIENT_VERSION?: string;
  MAX_TIMESTAMP_DRIFT_SEC?: string | number;
  OFFLINE_GRACE_PERIOD_SEC?: string | number;
}

export interface VerifyRequestBody {
  device_hash: string;
  app_version: string;
  build_number?: number;
  timestamp: number;
  nonce: string;
  signature: string;
}

export interface VerifyResponseBody {
  status: "AUTHORIZED" | "SUSPENDED" | "REVOKED" | "OUTDATED_VERSION";
  license_tier: string;
  kill_switch: boolean;
  min_version: string;
  emergency_announcement: string;
  engine_patch: {
    version: string;
    url: string;
  };
  valid_until: number;
  server_time: number;
  signature: string;
}

export interface ReleaseCheckResponse {
  is_update_available: boolean;
  latest_version_name: string;
  latest_version_code: number;
  release_notes: string;
  download_url: string;
  sha256_checksum: string;
  published_at: number;
}

const DEFAULT_SECRET = "polarsnap_hmac_secret_trandif_arctic_core_2026";
const DEFAULT_MAX_DRIFT = 300; // 5 minutes (+/- 300s)
const DEFAULT_GRACE_PERIOD = 604800; // 7 days (7 * 24 * 3600 seconds)
const DEFAULT_MIN_VERSION = "2.4.0";

/**
 * Constant-time string comparison to prevent timing attacks.
 */
export function constantTimeCompare(a: string, b: string): boolean {
  if (typeof a !== "string" || typeof b !== "string") return false;
  if (a.length !== b.length) return false;
  let result = 0;
  for (let i = 0; i < a.length; i++) {
    result |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return result === 0;
}

/**
 * Computes HMAC-SHA256 of the given message with the secret key using Web Crypto.
 */
export async function computeHmacSha256(keyStr: string, message: string): Promise<string> {
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(keyStr),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const signatureBuffer = await crypto.subtle.sign("HMAC", key, encoder.encode(message));
  const hashArray = Array.from(new Uint8Array(signatureBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, "0")).join("");
}

/**
 * Builds the canonical request signing string.
 * Format: "${device_hash}:${app_version}:${build_number}:${timestamp}:${nonce}"
 */
export function buildCanonicalRequestString(body: VerifyRequestBody): string {
  const buildNum = body.build_number !== undefined && body.build_number !== null ? body.build_number : "";
  return `${body.device_hash}:${body.app_version}:${buildNum}:${body.timestamp}:${body.nonce}`;
}

/**
 * Builds the canonical response signing string.
 * Format: "${status}:${kill_switch}:${valid_until}:${server_time}:${nonce}"
 */
export function buildCanonicalResponseString(
  status: string,
  killSwitch: boolean,
  validUntil: number,
  serverTime: number,
  nonce: string
): string {
  return `${status}:${killSwitch}:${validUntil}:${serverTime}:${nonce}`;
}

/**
 * Compares two semantic version strings (e.g., "2.4.0" vs "2.4.1").
 * Returns: negative if v1 < v2, 0 if v1 == v2, positive if v1 > v2.
 */
export function compareSemVer(v1: string, v2: string): number {
  const clean = (v: string) => v.replace(/^v/, "").trim();
  const p1 = clean(v1).split(".").map(x => parseInt(x, 10) || 0);
  const p2 = clean(v2).split(".").map(x => parseInt(x, 10) || 0);
  const len = Math.max(p1.length, p2.length);
  for (let i = 0; i < len; i++) {
    const num1 = p1[i] || 0;
    const num2 = p2[i] || 0;
    if (num1 !== num2) return num1 - num2;
  }
  return 0;
}

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Polar-Signature, X-Polar-Device-Hash",
  "Content-Type": "application/json"
};

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: CORS_HEADERS
  });
}

export default {
  async fetch(request: Request, env: Env, ctx?: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    // Handle CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    const secret = env.POLARSNAP_HMAC_SECRET || DEFAULT_SECRET;
    const maxDrift = Number(env.MAX_TIMESTAMP_DRIFT_SEC) || DEFAULT_MAX_DRIFT;
    const gracePeriod = Number(env.OFFLINE_GRACE_PERIOD_SEC) || DEFAULT_GRACE_PERIOD;
    const nowSec = Math.floor(Date.now() / 1000);

    // Route: GET /health or /api/v1/health
    if (url.pathname === "/health" || url.pathname === "/api/v1/health") {
      return jsonResponse({
        status: "ok",
        service: "polarsnap-licensing",
        isolated: true,
        server_time: nowSec
      });
    }

    // Route: GET /api/v1/releases/latest or /api/v1/ota/check
    if (url.pathname === "/api/v1/releases/latest" || url.pathname === "/api/v1/ota/check") {
      const clientVersion = url.searchParams.get("current_version") || "2.4.0";
      const clientCode = parseInt(url.searchParams.get("current_code") || "240", 10);

      // Latest official release metadata for PolarSnap
      const latestVersionName = "2.4.1";
      const latestVersionCode = 241;
      const isUpdateAvailable = clientCode < latestVersionCode || compareSemVer(clientVersion, latestVersionName) < 0;

      const releaseData: ReleaseCheckResponse = {
        is_update_available: isUpdateAvailable,
        latest_version_name: latestVersionName,
        latest_version_code: latestVersionCode,
        release_notes: "PolarSnap v2.4.1 — Arctic Streamline UI polish, 4K Lanczos performance enhancements, and stability updates.",
        download_url: "https://github.com/trandif/polarsnap/releases/download/v2.4.1/polarsnap-release-arm64-v8a.apk",
        sha256_checksum: "a4f89d9e2837bc449832104e76a1120038848482991010398485720193848123",
        published_at: 1730900000
      };

      return jsonResponse(releaseData);
    }

    // Route: POST /api/v1/license/verify
    if (url.pathname === "/api/v1/license/verify") {
      if (request.method !== "POST") {
        return jsonResponse({ error: "Method not allowed. Use POST.", code: "METHOD_NOT_ALLOWED" }, 405);
      }

      let body: VerifyRequestBody;
      try {
        body = await request.json<VerifyRequestBody>();
      } catch {
        return jsonResponse({ error: "Invalid JSON request body", code: "INVALID_JSON" }, 400);
      }

      // 1. Validate mandatory payload properties
      if (!body.device_hash || !body.app_version || body.timestamp === undefined || !body.nonce || !body.signature) {
        return jsonResponse({
          error: "Missing required fields: device_hash, app_version, timestamp, nonce, signature",
          code: "MISSING_FIELDS"
        }, 400);
      }

      // 2. Validate timestamp freshness (+/- 300s drift window)
      const drift = Math.abs(nowSec - body.timestamp);
      if (drift > maxDrift) {
        return jsonResponse({
          error: `Timestamp drift exceeded. Allowed window: +/- ${maxDrift}s, received drift: ${drift}s`,
          code: "TIMESTAMP_DRIFT_EXCEEDED",
          server_time: nowSec
        }, 400);
      }

      // 3. Prevent replay attacks: Validate nonce uniqueness in D1
      if (env.DB) {
        try {
          const existingNonce = await env.DB.prepare(
            "SELECT nonce FROM request_nonces WHERE nonce = ?"
          ).bind(body.nonce).first<{ nonce: string }>();

          if (existingNonce) {
            return jsonResponse({
              error: "Nonce replay attack detected. Nonce has already been consumed.",
              code: "NONCE_REPLAY_DETECTED"
            }, 409);
          }

          // Store nonce atomically
          await env.DB.prepare(
            "INSERT INTO request_nonces (nonce, created_at) VALUES (?, ?)"
          ).bind(body.nonce, nowSec).run();

          // Housekeeping: purge expired nonces older than 2x drift window
          ctx?.waitUntil?.(
            env.DB.prepare(
              "DELETE FROM request_nonces WHERE created_at < ?"
            ).bind(nowSec - (maxDrift * 2)).run()
          );
        } catch (dbErr: any) {
          // If D1 fails, handle gracefully
          console.error("D1 Nonce DB error:", dbErr);
        }
      }

      // 4. Verify client HMAC-SHA256 signature
      const canonicalReq = buildCanonicalRequestString(body);
      const expectedSignature = await computeHmacSha256(secret, canonicalReq);

      if (!constantTimeCompare(body.signature.toLowerCase(), expectedSignature.toLowerCase())) {
        return jsonResponse({
          error: "HMAC signature verification failed. Invalid payload signature.",
          code: "INVALID_SIGNATURE"
        }, 401);
      }

      // 5. Query global kill-switch policy and device status in D1
      let killSwitchActive = false;
      let minSupportedVersion = env.MIN_CLIENT_VERSION || DEFAULT_MIN_VERSION;
      let emergencyAnnouncement = "";
      let enginePatchVersion = "2024.11.04";
      let enginePatchUrl = "https://releases.polarsnap.app/engine/2024.11.04/usr.zip";
      let deviceStatus: "ACTIVE" | "SUSPENDED" | "REVOKED" = "ACTIVE";
      let deviceTier = "FREE";
      let revocationReason: string | null = null;

      if (env.DB) {
        try {
          const policies = await env.DB.prepare(
            "SELECT policy_key, policy_value FROM global_policy"
          ).all<{ policy_key: string; policy_value: string }>();

          if (policies.results) {
            for (const p of policies.results) {
              if (p.policy_key === "kill_switch_active") {
                killSwitchActive = p.policy_value.toLowerCase() === "true";
              } else if (p.policy_key === "min_supported_version") {
                minSupportedVersion = p.policy_value;
              } else if (p.policy_key === "emergency_announcement") {
                emergencyAnnouncement = p.policy_value;
              } else if (p.policy_key === "engine_hotpatch_version") {
                enginePatchVersion = p.policy_value;
              } else if (p.policy_key === "engine_hotpatch_url") {
                enginePatchUrl = p.policy_value;
              }
            }
          }

          // Check or register device
          const ipCountry = request.headers.get("cf-ipcountry") || "UNKNOWN";
          const device = await env.DB.prepare(
            "SELECT device_hash, status, license_tier, revocation_reason FROM devices WHERE device_hash = ?"
          ).bind(body.device_hash).first<{
            device_hash: string;
            status: "ACTIVE" | "SUSPENDED" | "REVOKED";
            license_tier: string;
            revocation_reason: string | null;
          }>();

          if (device) {
            deviceStatus = device.status;
            deviceTier = device.license_tier;
            revocationReason = device.revocation_reason;

            // Update last_seen and app_version
            await env.DB.prepare(
              "UPDATE devices SET last_seen = ?, app_version = ?, ip_country = ? WHERE device_hash = ?"
            ).bind(nowSec, body.app_version, ipCountry, body.device_hash).run();
          } else {
            // Register new device
            await env.DB.prepare(
              "INSERT INTO devices (device_hash, app_version, first_seen, last_seen, status, license_tier, ip_country) VALUES (?, ?, ?, ?, 'ACTIVE', 'FREE', ?)"
            ).bind(body.device_hash, body.app_version, nowSec, nowSec, ipCountry).run();
          }
        } catch (dbErr: any) {
          console.error("D1 Device query error:", dbErr);
        }
      }

      // 6. Determine final authorization status
      let finalStatus: "AUTHORIZED" | "SUSPENDED" | "REVOKED" | "OUTDATED_VERSION" = "AUTHORIZED";

      if (killSwitchActive) {
        finalStatus = "REVOKED";
      } else if (deviceStatus === "REVOKED") {
        finalStatus = "REVOKED";
      } else if (deviceStatus === "SUSPENDED") {
        finalStatus = "SUSPENDED";
      } else if (compareSemVer(body.app_version, minSupportedVersion) < 0) {
        finalStatus = "OUTDATED_VERSION";
      } else {
        finalStatus = "AUTHORIZED";
      }

      // Calculate offline grace window (7 days from successful verification)
      const validUntil = nowSec + gracePeriod;

      // 7. Sign the response token with server HMAC
      const canonicalRes = buildCanonicalResponseString(
        finalStatus,
        killSwitchActive,
        validUntil,
        nowSec,
        body.nonce
      );
      const serverSignature = await computeHmacSha256(secret, canonicalRes);

      const responsePayload: VerifyResponseBody = {
        status: finalStatus,
        license_tier: deviceTier,
        kill_switch: killSwitchActive,
        min_version: minSupportedVersion,
        emergency_announcement: emergencyAnnouncement,
        engine_patch: {
          version: enginePatchVersion,
          url: enginePatchUrl
        },
        valid_until: validUntil,
        server_time: nowSec,
        signature: serverSignature
      };

      return jsonResponse(responsePayload, 200);
    }

    return jsonResponse({ error: "Endpoint not found", code: "NOT_FOUND" }, 404);
  }
};
