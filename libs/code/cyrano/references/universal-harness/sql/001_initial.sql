-- UDH initial storage contract. Migration runner checks checksum/version.
-- Business authority, signatures, graph semantics and scope are service checks.
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;

CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY,
    checksum TEXT NOT NULL,
    applied_at TEXT NOT NULL
);
CREATE TABLE principals (
    principal_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('user','host','worker','broker','runner','service')),
    status TEXT NOT NULL CHECK (status IN ('active','revoked')),
    metadata_json TEXT NOT NULL CHECK (json_valid(metadata_json))
);
CREATE TABLE workspaces (
    workspace_id TEXT PRIMARY KEY,
    canonical_locator TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    policy_digest TEXT NOT NULL
);
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id),
    state TEXT NOT NULL,
    control_revision INTEGER NOT NULL DEFAULT 0 CHECK (control_revision >= 0),
    policy_epoch INTEGER NOT NULL DEFAULT 0 CHECK (policy_epoch >= 0),
    spec_digest TEXT,
    plan_digest TEXT,
    policy_digest TEXT NOT NULL,
    release_digest TEXT NOT NULL,
    runtime_lock_digest TEXT NOT NULL,
    scope_json TEXT NOT NULL CHECK (json_valid(scope_json)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (workspace_id, session_id)
);
CREATE TABLE artifacts (
    artifact_id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES sessions(session_id),
    workspace_id TEXT REFERENCES workspaces(workspace_id),
    digest TEXT NOT NULL,
    byte_count INTEGER NOT NULL CHECK (byte_count >= 0),
    media_type TEXT NOT NULL,
    storage_locator TEXT NOT NULL UNIQUE,
    sensitivity TEXT NOT NULL CHECK (sensitivity IN ('public','internal','restricted')),
    status TEXT NOT NULL CHECK (status IN ('active','tombstoned','purged')),
    created_at TEXT NOT NULL
);
CREATE INDEX artifacts_by_digest ON artifacts(digest);
CREATE TABLE events (
    event_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    session_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    producer TEXT NOT NULL,
    producer_seq INTEGER NOT NULL CHECK (producer_seq > 0),
    occurred_at TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    control_revision INTEGER NOT NULL CHECK (control_revision >= 0),
    policy_digest TEXT NOT NULL,
    release_digest TEXT NOT NULL,
    payload_digest TEXT NOT NULL,
    redacted_payload_json TEXT NOT NULL CHECK (json_valid(redacted_payload_json)),
    source_kind TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    span_id TEXT NOT NULL,
    FOREIGN KEY (workspace_id, session_id) REFERENCES sessions(workspace_id, session_id),
    UNIQUE (producer, producer_seq)
);
CREATE INDEX events_by_session ON events(session_id, event_seq);
CREATE TRIGGER events_no_update BEFORE UPDATE ON events BEGIN
    SELECT RAISE(ABORT, 'events_are_append_only');
END;
CREATE TRIGGER events_no_delete BEFORE DELETE ON events BEGIN
    SELECT RAISE(ABORT, 'events_are_append_only');
END;
CREATE TABLE entity_versions (
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    entity_id TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version > 0),
    entity_type TEXT NOT NULL,
    status TEXT NOT NULL,
    digest TEXT NOT NULL,
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
    source_event_id TEXT NOT NULL REFERENCES events(event_id),
    PRIMARY KEY (session_id, entity_id, version)
);
CREATE TABLE dependency_edges (
    session_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_version INTEGER NOT NULL,
    target_id TEXT NOT NULL,
    target_version INTEGER NOT NULL,
    relation TEXT NOT NULL CHECK (relation IN ('depends_on','verified_by','approved_by','derived_from')),
    FOREIGN KEY (session_id,source_id,source_version) REFERENCES entity_versions(session_id,entity_id,version),
    FOREIGN KEY (session_id,target_id,target_version) REFERENCES entity_versions(session_id,entity_id,version),
    PRIMARY KEY (session_id,source_id,source_version,target_id,target_version,relation)
);
CREATE INDEX reverse_dependencies ON dependency_edges(session_id,target_id,target_version);
CREATE TABLE idempotency (
    principal_id TEXT NOT NULL REFERENCES principals(principal_id),
    operation TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_digest TEXT NOT NULL,
    response_json TEXT NOT NULL CHECK (json_valid(response_json)),
    created_at TEXT NOT NULL,
    PRIMARY KEY (principal_id,operation,idempotency_key)
);
CREATE TABLE trusted_user_events (
    user_event_id TEXT PRIMARY KEY,
    principal_id TEXT NOT NULL REFERENCES principals(principal_id),
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    host_id TEXT NOT NULL,
    display_event_id TEXT,
    display_digest TEXT,
    raw_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
    received_at TEXT NOT NULL,
    provenance_json TEXT NOT NULL CHECK (json_valid(provenance_json))
);
CREATE TABLE reviews (
    review_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    assignment_id TEXT NOT NULL UNIQUE,
    reviewer_id TEXT NOT NULL REFERENCES principals(principal_id),
    input_bundle_digest TEXT NOT NULL,
    role TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('completed','blocked','failed','cancelled','stale')),
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json))
);
CREATE TABLE approvals (
    receipt_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    user_event_id TEXT NOT NULL REFERENCES trusted_user_events(user_event_id),
    action TEXT NOT NULL,
    receipt_digest TEXT NOT NULL UNIQUE,
    receipt_json TEXT NOT NULL CHECK (json_valid(receipt_json)),
    issuer TEXT NOT NULL,
    key_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active','expired','revoked','superseded')),
    expires_at TEXT NOT NULL
);
CREATE TABLE permits (
    permit_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    task_id TEXT NOT NULL,
    policy_epoch INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active','exhausted','expired','revoked')),
    expires_at TEXT NOT NULL,
    permit_json TEXT NOT NULL CHECK (json_valid(permit_json))
);
CREATE TABLE permit_approvals (
    permit_id TEXT NOT NULL REFERENCES permits(permit_id),
    receipt_id TEXT NOT NULL REFERENCES approvals(receipt_id),
    PRIMARY KEY (permit_id,receipt_id)
);
CREATE TABLE work_units (
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    task_id TEXT NOT NULL,
    plan_digest TEXT NOT NULL,
    status TEXT NOT NULL,
    expected_preimage_digest TEXT NOT NULL,
    observed_postimage_digest TEXT,
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
    PRIMARY KEY (session_id,task_id)
);
CREATE TABLE operations (
    operation_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    permit_id TEXT REFERENCES permits(permit_id),
    status TEXT NOT NULL CHECK (status IN ('intent_committed','permit_reserved','started','result_observed','reconciled','denied','failed','unknown_outcome')),
    request_digest TEXT NOT NULL,
    intent_event_id TEXT NOT NULL REFERENCES events(event_id),
    result_artifact_id TEXT REFERENCES artifacts(artifact_id),
    started_at TEXT,
    finished_at TEXT,
    FOREIGN KEY (session_id,task_id) REFERENCES work_units(session_id,task_id)
);
CREATE TABLE leases (
    lease_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    worker_id TEXT NOT NULL REFERENCES principals(principal_id),
    expires_at TEXT NOT NULL,
    heartbeat_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active','released','expired','revoked')),
    FOREIGN KEY (session_id,task_id) REFERENCES work_units(session_id,task_id)
);
CREATE TABLE write_locks (
    workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id),
    canonical_path TEXT NOT NULL,
    lease_id TEXT NOT NULL REFERENCES leases(lease_id),
    PRIMARY KEY (workspace_id,canonical_path)
);
CREATE TABLE budget_reservations (
    reservation_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    attempt_id TEXT NOT NULL UNIQUE,
    reserved_units INTEGER NOT NULL CHECK (reserved_units >= 0),
    settled_units INTEGER CHECK (settled_units >= 0),
    unit TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('reserved','settled','released','unknown'))
);
CREATE TABLE memory_records (
    memory_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    scope_type TEXT NOT NULL CHECK (scope_type IN ('global','workspace','session','task')),
    workspace_id TEXT REFERENCES workspaces(workspace_id),
    session_id TEXT REFERENCES sessions(session_id),
    task_id TEXT,
    status TEXT NOT NULL CHECK (status IN ('candidate','reviewed','approved','active','stale','superseded','revoked','archived','rejected','tombstoned')),
    content_digest TEXT NOT NULL,
    release_digest TEXT,
    expires_at TEXT,
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
    CHECK ((scope_type <> 'workspace') OR workspace_id IS NOT NULL),
    CHECK ((scope_type <> 'session') OR session_id IS NOT NULL),
    CHECK ((scope_type <> 'task') OR (task_id IS NOT NULL AND session_id IS NOT NULL))
);
CREATE VIRTUAL TABLE memory_search USING fts5(memory_id UNINDEXED, title, body, tags);
-- MemoryService inserts sanitized, active, scoped records only; query joins
-- memory_records and applies scope/status/freshness BEFORE returning results.
CREATE TABLE learning_candidates (
    candidate_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    parent_release_digest TEXT NOT NULL,
    target TEXT NOT NULL,
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json))
);
CREATE TABLE evaluations (
    evaluation_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL REFERENCES learning_candidates(candidate_id),
    split_manifest_digest TEXT NOT NULL,
    criteria_digest TEXT NOT NULL,
    runtime_lock_digest TEXT NOT NULL,
    status TEXT NOT NULL,
    verdict TEXT CHECK (verdict IN ('improved','regressed','inconclusive','invalid')),
    report_json TEXT CHECK (report_json IS NULL OR json_valid(report_json))
);
CREATE TABLE releases (
    release_digest TEXT PRIMARY KEY,
    parent_digest TEXT REFERENCES releases(release_digest),
    manifest_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
    approval_receipt_id TEXT REFERENCES approvals(receipt_id),
    created_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('staged','active','retired','revoked'))
);
CREATE TABLE release_pointers (
    channel TEXT PRIMARY KEY,
    release_digest TEXT NOT NULL REFERENCES releases(release_digest),
    version INTEGER NOT NULL CHECK (version > 0)
);
CREATE TABLE outbox (
    job_id TEXT PRIMARY KEY,
    logical_key TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    session_id TEXT REFERENCES sessions(session_id),
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
    status TEXT NOT NULL CHECK (status IN ('pending','leased','done','failed','cancelled')),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    available_at TEXT NOT NULL,
    lease_until TEXT,
    last_error TEXT
);
CREATE INDEX outbox_ready ON outbox(status,available_at);
