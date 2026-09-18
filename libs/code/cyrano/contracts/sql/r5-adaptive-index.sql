-- Target DDL after r4-memory-observability.sql; not installed migration.
PRAGMA foreign_keys = ON;
CREATE TABLE playbook_entry_details (
 memory_id TEXT NOT NULL, version INTEGER NOT NULL,
 conditions_digest TEXT NOT NULL REFERENCES artifacts(raw_digest),
 validation_state TEXT NOT NULL CHECK(validation_state IN ('candidate','validated','stale','rejected')),
 PRIMARY KEY(memory_id,version),
 FOREIGN KEY(memory_id,version) REFERENCES memories(memory_id,version)
);
CREATE TABLE playbook_links (
 source_id TEXT NOT NULL, source_version INTEGER NOT NULL,
 target_id TEXT NOT NULL, target_version INTEGER NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('supports','contradicts','supersedes','example_of')),
 evidence_digest TEXT NOT NULL REFERENCES artifacts(raw_digest),
 PRIMARY KEY(source_id,source_version,target_id,target_version,kind),
 FOREIGN KEY(source_id,source_version) REFERENCES memories(memory_id,version),
 FOREIGN KEY(target_id,target_version) REFERENCES memories(memory_id,version)
);
CREATE TABLE memory_utility_observations (
 observation_id TEXT PRIMARY KEY,
 application_id TEXT NOT NULL REFERENCES memory_applications(application_id),
 condition_digest TEXT NOT NULL REFERENCES artifacts(raw_digest),
 causality TEXT NOT NULL CHECK(causality IN ('correlational','controlled_comparison')),
 result_digest TEXT NOT NULL REFERENCES artifacts(raw_digest)
);
CREATE TABLE managed_index_generations (
 index_id TEXT NOT NULL, generation TEXT NOT NULL,
 scope_id TEXT NOT NULL REFERENCES scopes(scope_id),
 source_digest TEXT NOT NULL, environment_digest TEXT NOT NULL,
 acl_digest TEXT NOT NULL, provider_digest TEXT NOT NULL,
 manifest_digest TEXT NOT NULL REFERENCES artifacts(raw_digest),
 status TEXT NOT NULL CHECK(status IN ('building','ready','stale','revoked','failed')),
 PRIMARY KEY(index_id,generation)
);
CREATE INDEX index_by_scope ON managed_index_generations(scope_id,status);
-- Enforce identical source/target scopes in service before playbook link insert.
-- Existing canonical memories/releases/outbox/approvals/events remain sole owners.
