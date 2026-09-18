-- CYRANO target schema v1. Syntax/integrity test only; not an applied migration.
PRAGMA foreign_keys = ON;
CREATE TABLE scopes (
 scope_id TEXT PRIMARY KEY, tenant TEXT NOT NULL, user_id TEXT NOT NULL,
 workspace TEXT NOT NULL, acl_revision INTEGER NOT NULL CHECK (acl_revision >= 0),
 UNIQUE(tenant, user_id, workspace)
);
CREATE TABLE streams (
 stream_id TEXT PRIMARY KEY, scope_id TEXT NOT NULL REFERENCES scopes(scope_id),
 revision INTEGER NOT NULL DEFAULT 0 CHECK(revision >= 0),
 entity_type TEXT NOT NULL, status TEXT NOT NULL
);
CREATE TABLE artifacts (
 raw_digest TEXT PRIMARY KEY, scope_id TEXT NOT NULL REFERENCES scopes(scope_id),
 relative_blob_path TEXT NOT NULL, media_type TEXT NOT NULL,
 byte_length INTEGER NOT NULL CHECK(byte_length >= 0), sensitivity TEXT NOT NULL,
 origin_kind TEXT NOT NULL, sealed INTEGER NOT NULL CHECK(sealed IN(0,1))
);
CREATE TABLE subjects (
 subject_digest TEXT PRIMARY KEY, schema_type TEXT NOT NULL, projection_version INTEGER NOT NULL,
 scope_id TEXT NOT NULL REFERENCES scopes(scope_id), raw_digest TEXT NOT NULL REFERENCES artifacts(raw_digest)
);
CREATE TABLE events (
 event_seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE,
 stream_id TEXT NOT NULL REFERENCES streams(stream_id), stream_revision INTEGER NOT NULL,
 producer TEXT NOT NULL, producer_seq INTEGER NOT NULL,
 kind TEXT NOT NULL, schema_version INTEGER NOT NULL, payload_digest TEXT NOT NULL REFERENCES artifacts(raw_digest),
 observed_at TEXT NOT NULL, ingested_at TEXT NOT NULL, observation_kind TEXT NOT NULL,
 UNIQUE(stream_id, stream_revision), UNIQUE(producer, producer_seq)
);
CREATE TABLE entity_versions (
 stream_id TEXT NOT NULL REFERENCES streams(stream_id), version INTEGER NOT NULL,
 subject_digest TEXT NOT NULL REFERENCES subjects(subject_digest),
 PRIMARY KEY(stream_id,version)
);
CREATE TABLE requests (
 scope_id TEXT NOT NULL REFERENCES scopes(scope_id), actor TEXT NOT NULL, command TEXT NOT NULL,
 idempotency_key TEXT NOT NULL, request_digest TEXT NOT NULL,
 response_digest TEXT NOT NULL REFERENCES artifacts(raw_digest),
 PRIMARY KEY(scope_id,actor,command,idempotency_key)
);
CREATE TABLE outbox (
 job_id TEXT PRIMARY KEY, event_id TEXT NOT NULL REFERENCES events(event_id),
 scope_id TEXT NOT NULL REFERENCES scopes(scope_id), payload_digest TEXT NOT NULL REFERENCES artifacts(raw_digest),
 state TEXT NOT NULL CHECK(state IN('pending','leased','completed','failed','cancelled','unknown')),
 attempts INTEGER NOT NULL DEFAULT 0, fence INTEGER NOT NULL DEFAULT 0,
 lease_owner TEXT, lease_until TEXT, deadline TEXT NOT NULL,
 meta_depth INTEGER NOT NULL CHECK(meta_depth BETWEEN 0 AND 1), UNIQUE(event_id,job_id)
);
CREATE TABLE dependency_edges (
 source_subject TEXT NOT NULL REFERENCES subjects(subject_digest),
 dependent_subject TEXT NOT NULL REFERENCES subjects(subject_digest), relation TEXT NOT NULL,
 PRIMARY KEY(source_subject,dependent_subject,relation)
);
CREATE TABLE approvals (
 approval_id TEXT PRIMARY KEY, subject_digest TEXT NOT NULL REFERENCES subjects(subject_digest),
 scope_id TEXT NOT NULL REFERENCES scopes(scope_id), purpose TEXT NOT NULL,
 issuer TEXT NOT NULL, audience TEXT NOT NULL, nonce TEXT NOT NULL UNIQUE,
 issued_at TEXT NOT NULL, expires_at TEXT NOT NULL, signature_ref TEXT NOT NULL,
 revoked_revision INTEGER, source_user_event_id TEXT REFERENCES events(event_id)
);
CREATE TABLE releases (
 release_digest TEXT PRIMARY KEY REFERENCES subjects(subject_digest),
 parent_digest TEXT REFERENCES releases(release_digest), approval_id TEXT NOT NULL REFERENCES approvals(approval_id),
 status TEXT NOT NULL CHECK(status IN('staged','active','revoked','superseded')),
 minimum_schema_version INTEGER NOT NULL CHECK(minimum_schema_version >= 1)
);
CREATE TABLE active_releases (
 scope_id TEXT PRIMARY KEY REFERENCES scopes(scope_id),
 release_digest TEXT NOT NULL REFERENCES releases(release_digest), revision INTEGER NOT NULL
);
CREATE TABLE runs (
 run_id TEXT PRIMARY KEY, scope_id TEXT NOT NULL REFERENCES scopes(scope_id),
 release_digest TEXT NOT NULL REFERENCES releases(release_digest), snapshot_digest TEXT NOT NULL REFERENCES artifacts(raw_digest),
 runtime_digest TEXT NOT NULL, status TEXT NOT NULL, context_epoch INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE attempts (
 attempt_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(run_id), parent_attempt TEXT REFERENCES attempts(attempt_id),
 input_signature TEXT NOT NULL, input_snapshot TEXT NOT NULL REFERENCES artifacts(raw_digest),
 output_snapshot TEXT REFERENCES artifacts(raw_digest), execution_status TEXT NOT NULL,
 correctness_status TEXT NOT NULL, acceptance_status TEXT NOT NULL, external_request_id TEXT,
 receipt_digest TEXT REFERENCES artifacts(raw_digest)
);
CREATE TABLE experiments (
 experiment_id TEXT PRIMARY KEY, plan_subject TEXT NOT NULL REFERENCES subjects(subject_digest),
 permit_id TEXT NOT NULL REFERENCES approvals(approval_id), planned_pairs INTEGER NOT NULL CHECK(planned_pairs > 0),
 candidate_subject TEXT NOT NULL REFERENCES subjects(subject_digest), state TEXT NOT NULL
);
CREATE TABLE experiment_pairs (
 experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id), pair_id TEXT NOT NULL,
 family_id TEXT NOT NULL, split TEXT NOT NULL CHECK(split IN('development','validation','sealed')),
 baseline_attempt TEXT REFERENCES attempts(attempt_id), candidate_attempt TEXT REFERENCES attempts(attempt_id),
 status TEXT NOT NULL, exclusion_reason TEXT, PRIMARY KEY(experiment_id,pair_id)
);
CREATE TABLE memories (
 memory_id TEXT NOT NULL, version INTEGER NOT NULL, scope_id TEXT NOT NULL REFERENCES scopes(scope_id),
 subject_digest TEXT NOT NULL REFERENCES subjects(subject_digest), status TEXT NOT NULL,
 valid_from TEXT NOT NULL, valid_until TEXT NOT NULL, title TEXT NOT NULL,
 PRIMARY KEY(memory_id,version)
);
CREATE VIRTUAL TABLE memory_fts USING fts5(memory_id UNINDEXED, scope_id UNINDEXED, title, content);
CREATE INDEX events_by_stream ON events(stream_id,event_seq);
CREATE INDEX memory_scope_status ON memories(scope_id,status,valid_until);
CREATE INDEX outbox_state_lease ON outbox(state,lease_until);
CREATE INDEX subjects_scope ON subjects(scope_id,schema_type);
PRAGMA user_version = 1;
