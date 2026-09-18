-- Proposed migration. Integrate with the existing UDH migration engine.
CREATE TABLE quality_requests (
    request_id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL,
    payload_digest TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('RUNNING', 'FINISHED', 'ERROR')),
    report_id TEXT,
    lease_owner TEXT,
    lease_expires_at TEXT,
    created_at TEXT NOT NULL,
    CHECK (state != 'FINISHED' OR report_id IS NOT NULL)
);

CREATE TABLE quality_reports (
    report_id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL,
    snapshot_digest TEXT NOT NULL,
    policy_digest TEXT NOT NULL,
    toolchain_digest TEXT NOT NULL,
    suite_digest TEXT NOT NULL,
    report_digest TEXT NOT NULL UNIQUE,
    runner_receipt_id TEXT NOT NULL UNIQUE,
    verdict TEXT NOT NULL CHECK (
        verdict IN (
            'PASS', 'PASS_WITH_BASELINE', 'FAIL',
            'ERROR', 'BLOCKED', 'STALE'
        )
    ),
    report_blob_ref TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX quality_reports_attempt_idx
ON quality_reports(attempt_id, created_at);
