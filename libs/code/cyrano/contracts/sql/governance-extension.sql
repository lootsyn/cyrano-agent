-- TARGET SHAPE ONLY: reviewed versioned migrations must apply this in WP02.
-- Never execute against a user's current database from the package installer.
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS governance_bindings (
    binding_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    contract_kind TEXT NOT NULL,
    contract_version TEXT NOT NULL,
    subject_digest TEXT NOT NULL,
    artifact_ref TEXT NOT NULL,
    control_revision INTEGER NOT NULL CHECK(control_revision >= 0),
    UNIQUE(tenant_id, user_id, workspace_id, binding_id)
);
CREATE TABLE IF NOT EXISTS governance_operation_journal (
    operation_id TEXT PRIMARY KEY,
    binding_id TEXT NOT NULL REFERENCES governance_bindings(binding_id),
    fencing_token INTEGER NOT NULL CHECK(fencing_token >= 0),
    phase TEXT NOT NULL CHECK(phase IN ('prepared','started','partial','applied','verified','failed','unknown','reconciled')),
    expected_preimage TEXT NOT NULL,
    observed_postimage TEXT,
    manifest_ref TEXT,
    revision INTEGER NOT NULL CHECK(revision >= 0)
);
CREATE TABLE IF NOT EXISTS governance_effect_entries (
    operation_id TEXT NOT NULL REFERENCES governance_operation_journal(operation_id),
    path_id TEXT NOT NULL,
    effect_kind TEXT NOT NULL CHECK(effect_kind IN ('create','modify','delete','only_write')),
    before_digest TEXT,
    after_digest TEXT,
    outcome TEXT NOT NULL CHECK(outcome IN ('not_started','applied','failed','unknown','reconciled')),
    PRIMARY KEY(operation_id, path_id)
);
CREATE TABLE IF NOT EXISTS governance_budget_liabilities (
    reservation_id TEXT PRIMARY KEY,
    operation_id TEXT NOT NULL REFERENCES governance_operation_journal(operation_id),
    currency TEXT NOT NULL,
    reserved_decimal TEXT NOT NULL,
    actual_decimal TEXT,
    status TEXT NOT NULL CHECK(status IN ('reserved','settled','unknown')),
    settlement_evidence_ref TEXT
);
CREATE TABLE IF NOT EXISTS governance_deletion_tombstones (
    deletion_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    entity_ref TEXT NOT NULL,
    requested_event_ref TEXT NOT NULL,
    closure_manifest_ref TEXT NOT NULL,
    created_at TEXT NOT NULL
);
