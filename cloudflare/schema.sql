-- PolarSnap Isolated D1 Database Schema
-- Database: polarsnap_licensing_db
-- Strictly scoped to PolarSnap device verification, replay prevention, and global policy

CREATE TABLE IF NOT EXISTS devices (
    device_hash TEXT PRIMARY KEY,
    app_version TEXT NOT NULL,
    first_seen INTEGER NOT NULL,
    last_seen INTEGER NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('ACTIVE', 'SUSPENDED', 'REVOKED')),
    license_tier TEXT NOT NULL DEFAULT 'FREE',
    revocation_reason TEXT,
    ip_country TEXT
);

CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status);

CREATE TABLE IF NOT EXISTS global_policy (
    policy_key TEXT PRIMARY KEY,
    policy_value TEXT NOT NULL
);

-- Seed baseline global policies
INSERT OR IGNORE INTO global_policy (policy_key, policy_value) VALUES 
('kill_switch_active', 'false'),
('min_supported_version', '2.4.0'),
('emergency_announcement', ''),
('engine_hotpatch_version', '2024.11.04'),
('engine_hotpatch_url', 'https://releases.polarsnap.app/engine/2024.11.04/usr.zip');

CREATE TABLE IF NOT EXISTS request_nonces (
    nonce TEXT PRIMARY KEY,
    created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_nonces_created ON request_nonces(created_at);
