"""Digest projection tables loaded from the contract files.

`subjects.binding_digest` covers the v1 signable types. This module
loads the declared projection contracts for both v1 and v2 so the
code and the contract files cannot drift apart silently.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from deepagents_code.cyrano.contracts.canonical import digest
from deepagents_code.cyrano.contracts.ingress import (
    JSON,
    parse_document,
)
from deepagents_code.cyrano.contracts.types import CyranoError

PROJECTION_FILES = (
    "v1/digest-projections.json",
    "v2/digest-projections.json",
)


@dataclass(frozen=True, slots=True)
class ProjectionRule:
    """Exact subject/envelope field partition for one type."""

    type_name: str
    schema_version: str
    subject_fields: frozenset[str]
    envelope_fields: frozenset[str]


class ProjectionTable:
    """Versioned projection rules keyed by contract type name."""

    def __init__(self, rules: Mapping[str, ProjectionRule]):
        """Store the loaded projection rules keyed by type name."""
        self._rules = dict(rules)

    @classmethod
    def from_files(cls, files: Mapping[str, bytes]) -> "ProjectionTable":
        """Load v1 and v2 projection contracts from raw bytes."""
        rules: dict[str, ProjectionRule] = {}
        for name, raw in files.items():
            data = parse_document(raw)
            types = data.get("types")
            if not isinstance(types, dict):
                continue
            version = str(
                data.get("version") or data.get("schema_version") or ""
            )
            for type_name, node in types.items():
                if not isinstance(node, dict):
                    continue
                subject = node.get("subject_fields", [])
                envelope = node.get("envelope_fields", [])
                if not isinstance(subject, list):
                    subject = []
                if not isinstance(envelope, list):
                    envelope = []
                rules[str(type_name)] = ProjectionRule(
                    type_name=str(type_name),
                    schema_version=version,
                    subject_fields=frozenset(map(str, subject)),
                    envelope_fields=frozenset(map(str, envelope)),
                )
        return cls(rules)

    @classmethod
    def from_root(cls, contract_root: Path) -> "ProjectionTable":
        """Load projection contracts from a checkout directory."""
        files = {
            name: (contract_root / name).read_bytes()
            for name in PROJECTION_FILES
        }
        return cls.from_files(files)

    def rule(self, schema_type: str) -> ProjectionRule:
        """Return the projection rule or reject the type."""
        rule = self._rules.get(schema_type)
        if rule is None:
            raise CyranoError("UNKNOWN_SUBJECT_TYPE", schema_type)
        return rule

    def binding_digest(
        self, schema_type: str, document: Mapping[str, JSON]
    ) -> str:
        """Hash the subject fields; envelope fields never bind."""
        rule = self.rule(schema_type)
        allowed = rule.subject_fields | rule.envelope_fields
        if set(document) != allowed:
            raise CyranoError(
                "INVALID_SUBJECT_FIELDS",
                "validate the complete typed envelope",
            )
        subject = {key: document[key] for key in rule.subject_fields}
        return digest(
            {
                "projection_version": "1",
                "schema_type": schema_type,
                "subject": subject,
            }
        )
