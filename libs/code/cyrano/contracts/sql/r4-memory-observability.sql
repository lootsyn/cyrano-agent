-- Design DDL: apply after target-schema.sql and governance-extension.sql.
-- Not an installed migration. Never create a second competing event store.
PRAGMA foreign_keys = ON;
CREATE TABLE memory_revision_details (
 memory_id TEXT NOT NULL, version INTEGER NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('episodic','semantic','procedural','preference','working')),
 content_digest TEXT NOT NULL REFERENCES artifacts(raw_digest),
 approval_id TEXT REFERENCES approvals(approval_id),
 dependency_manifest TEXT NOT NULL REFERENCES artifacts(raw_digest),
 tombstoned_at TEXT, PRIMARY KEY(memory_id,version),
 FOREIGN KEY(memory_id,version) REFERENCES memories(memory_id,version)
);
CREATE TABLE memory_release_items (
 release_digest TEXT NOT NULL REFERENCES releases(release_digest),
 memory_id TEXT NOT NULL, version INTEGER NOT NULL,
 PRIMARY KEY(release_digest,memory_id),
 FOREIGN KEY(memory_id,version) REFERENCES memories(memory_id,version)
);
CREATE TABLE memory_views (
 view_digest TEXT PRIMARY KEY REFERENCES artifacts(raw_digest),
 run_id TEXT NOT NULL REFERENCES runs(run_id),
 release_digest TEXT NOT NULL REFERENCES releases(release_digest),
 phase TEXT NOT NULL, query_digest TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE memory_view_items (
 view_digest TEXT NOT NULL REFERENCES memory_views(view_digest),
 memory_id TEXT NOT NULL, version INTEGER NOT NULL,
 selected_rank INTEGER NOT NULL CHECK(selected_rank >= 0),
 PRIMARY KEY(view_digest,memory_id,version),
 FOREIGN KEY(memory_id,version) REFERENCES memories(memory_id,version)
);
CREATE TABLE memory_applications (
 application_id TEXT PRIMARY KEY,
 view_digest TEXT NOT NULL REFERENCES memory_views(view_digest),
 memory_id TEXT NOT NULL, version INTEGER NOT NULL,
 run_id TEXT NOT NULL REFERENCES runs(run_id),
 status TEXT NOT NULL CHECK(status IN ('referenced','unverified','applied','rejected')),
 checker_id TEXT, evidence_digest TEXT REFERENCES artifacts(raw_digest),
 FOREIGN KEY(memory_id,version) REFERENCES memories(memory_id,version),
 CHECK(status != 'applied' OR (checker_id IS NOT NULL AND evidence_digest IS NOT NULL))
);
CREATE VIRTUAL TABLE memory_fts_r4 USING fts5(
 memory_id UNINDEXED, version UNINDEXED, scope_id UNINDEXED, title, content
);
CREATE TABLE request_run_links (
 request_id TEXT NOT NULL, scope_id TEXT NOT NULL REFERENCES scopes(scope_id),
 run_id TEXT NOT NULL REFERENCES runs(run_id), parent_run_id TEXT REFERENCES runs(run_id),
 PRIMARY KEY(request_id,run_id)
);
CREATE TABLE observer_epochs (
 observer_key TEXT PRIMARY KEY, producer_id TEXT NOT NULL, epoch TEXT NOT NULL,
 UNIQUE(producer_id,epoch)
);
CREATE TABLE trace_spans (
 span_id TEXT PRIMARY KEY, trace_id TEXT NOT NULL,
 run_id TEXT NOT NULL REFERENCES runs(run_id), parent_span_id TEXT,
 observer_key TEXT NOT NULL REFERENCES observer_epochs(observer_key),
 source_kind TEXT NOT NULL, boot_id TEXT NOT NULL,
 started_ns INTEGER NOT NULL CHECK(started_ns >= 0), ended_ns INTEGER,
 outcome TEXT NOT NULL, event_id TEXT REFERENCES events(event_id),
 CHECK(ended_ns IS NULL OR ended_ns >= started_ns)
);
CREATE TABLE model_invocations (
 logical_request_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(run_id),
 source_kind TEXT NOT NULL, request_manifest TEXT NOT NULL REFERENCES artifacts(raw_digest)
);
CREATE TABLE model_attempt_observations (
 physical_attempt_id TEXT PRIMARY KEY,
 logical_request_id TEXT NOT NULL REFERENCES model_invocations(logical_request_id),
 attempt_no INTEGER NOT NULL CHECK(attempt_no > 0), retry_of TEXT,
 span_id TEXT NOT NULL REFERENCES trace_spans(span_id),
 outcome TEXT NOT NULL, usage_digest TEXT REFERENCES artifacts(raw_digest),
 cost_kind TEXT NOT NULL CHECK(cost_kind IN ('actual','estimated','unknown')),
 cost_microunits INTEGER CHECK(cost_microunits >= 0), currency TEXT,
 UNIQUE(logical_request_id,attempt_no),
 CHECK(cost_kind != 'unknown' OR cost_microunits IS NULL)
);
CREATE TABLE event_projection_checkpoints (
 projection_id TEXT PRIMARY KEY, projection_version INTEGER NOT NULL,
 last_event_seq INTEGER NOT NULL CHECK(last_event_seq >= 0),
 snapshot_digest TEXT REFERENCES artifacts(raw_digest)
);
CREATE INDEX request_runs_scope ON request_run_links(scope_id,request_id);
CREATE INDEX trace_lookup ON trace_spans(trace_id,started_ns);
CREATE INDEX memory_versions_scope ON memories(scope_id,memory_id,version);
-- v1 events UNIQUE(producer,producer_seq) is retained: producer must be the
-- versioned observer_key (producer_id + epoch), not a reused process name.
-- Old memory_fts is no longer queried by the R4 service. Rebuild its new
-- projection from immutable canonical revisions; canonical ACL joins required.
