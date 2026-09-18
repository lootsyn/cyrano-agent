"""Trusted obligation checkers: declarative specs, digest-bound.

A ``checker_id`` resolves only through this registry. Specs are
data — JSON field expectations, sibling-file requirements, exact
postimage digests — evaluated by the deterministic functions in
this module. A spec can never execute code, and the model can never
register or mutate one: ``from_trusted_files`` loads bytes once
from a caller-supplied trusted root and every ``resolve`` re-verifies
the captured bytes against the digest the obligation bound. A
workspace-side rewrite of the source file changes nothing; a
registry built from a tampered spec resolves a different digest and
fails closed.
"""

from __future__ import annotations

import fnmatch
import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath

from deepagents_code.cyrano.contracts.types import CyranoError

CHECKER_KINDS = frozenset(
    {"paired_files", "json_fields", "expected_postimage"}
)

_FIELD_OPS = frozenset({"equals", "one_of", "required", "matches_stem"})
_PAIRED_KEYS = frozenset({"trigger", "derive", "required", "json_fields"})
_JSON_KEYS = frozenset({"files", "fields", "missing_is_violation"})
_POSTIMAGE_KEYS = frozenset({"files"})


@dataclass(frozen=True, slots=True)
class CheckerSpec:
    """A declarative checker bound to the digest of its spec bytes."""

    checker_id: str
    kind: str
    params: Mapping[str, object]
    digest: str


@dataclass(frozen=True, slots=True)
class CheckerVerdict:
    """A deterministic outcome.

    Errors are ``unverifiable``, never pass.
    """

    state: str  # satisfied | violated | unverifiable
    detail: str
    evidence_refs: tuple[str, ...] = ()


def _file_digest(content: bytes) -> str:
    return "sha256:" + sha256(content).hexdigest()


def _str_map(value: object, *, field: str) -> dict[str, object]:
    """Narrow to a string-keyed mapping; non-string keys are invalid."""
    if not isinstance(value, Mapping):
        raise CyranoError("INPUT_INVALID", f"{field} must map")
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise CyranoError("INPUT_INVALID", f"{field} key must str")
        result[key] = item
    return result


def _spec_params(kind: str, params: object) -> Mapping[str, object]:
    """Validate a spec body against its kind's closed key set."""
    params = _str_map(params, field="checker params")
    if kind == "paired_files":
        unknown = set(params) - _PAIRED_KEYS
        if unknown:
            raise CyranoError(
                "INPUT_INVALID", f"paired_files keys {sorted(unknown)}"
            )
        for key in ("trigger", "derive"):
            if not isinstance(params.get(key), str) or not params.get(key):
                raise CyranoError("INPUT_INVALID", f"paired_files needs {key}")
        _field_ops(
            _str_map(params.get("json_fields", {}), field="json_fields")
        )
        return params
    if kind == "json_fields":
        unknown = set(params) - _JSON_KEYS
        if unknown:
            raise CyranoError(
                "INPUT_INVALID", f"json_fields keys {sorted(unknown)}"
            )
        if not isinstance(params.get("files"), str):
            raise CyranoError("INPUT_INVALID", "json_fields needs files")
        _field_ops(_str_map(params.get("fields"), field="fields"))
        return params
    if kind == "expected_postimage":
        unknown = set(params) - _POSTIMAGE_KEYS
        if unknown:
            raise CyranoError(
                "INPUT_INVALID",
                f"expected_postimage keys {sorted(unknown)}",
            )
        files = _str_map(params.get("files"), field="files")
        if not files:
            raise CyranoError(
                "INPUT_INVALID", "expected_postimage needs files"
            )
        for expected in files.values():
            if not isinstance(expected, str):
                raise CyranoError(
                    "INPUT_INVALID", "postimage map holds strings"
                )
        return params
    raise CyranoError("INPUT_INVALID", f"checker kind {kind!r}")


def _field_ops(fields: Mapping[str, object]) -> None:
    """Every field rule uses a closed operator set — never code."""
    for name, rule in fields.items():
        rule_map = _str_map(rule, field=f"field {name} rule")
        unknown = set(rule_map) - _FIELD_OPS
        if unknown:
            raise CyranoError(
                "INPUT_INVALID",
                f"field {name} ops {sorted(unknown)}",
            )
        if "one_of" in rule_map and not isinstance(
            rule_map["one_of"], (list, tuple)
        ):
            raise CyranoError("INPUT_INVALID", "one_of must be a list")


def parse_checker_spec(checker_id: str, data: bytes) -> CheckerSpec:
    """Parse and validate a spec; the digest binds these exact bytes."""
    try:
        body = json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CyranoError(
            "INPUT_INVALID", f"checker {checker_id} not JSON: {exc}"
        ) from exc
    if not isinstance(body, Mapping):
        raise CyranoError("INPUT_INVALID", "checker spec must map")
    kind = body.get("kind")
    if not isinstance(kind, str) or kind not in CHECKER_KINDS:
        raise CyranoError(
            "INPUT_INVALID", f"checker kind {kind!r} unsupported"
        )
    params = _spec_params(kind, body.get("params", {}))
    return CheckerSpec(
        checker_id=checker_id,
        kind=kind,
        params=params,
        digest=_file_digest(data),
    )


class TrustedCheckerRegistry:
    """The only ``checker_id`` resolution path; fail closed always."""

    def __init__(
        self,
        specs: Mapping[str, CheckerSpec] | None = None,
        blobs: Mapping[str, bytes] | None = None,
    ) -> None:
        """Bind specs to their captured bytes for use-time re-verify."""
        self._specs = dict(specs or {})
        self._blobs = dict(blobs or {})

    @classmethod
    def from_specs(
        cls, specs: Mapping[str, CheckerSpec]
    ) -> TrustedCheckerRegistry:
        """Build a registry from already-validated spec objects."""
        return cls(specs)

    @classmethod
    def from_trusted_files(
        cls, root: Path, files: Mapping[str, str]
    ) -> TrustedCheckerRegistry:
        """Capture spec bytes once from a caller-named trusted root.

        The root is an operator input — this class never resolves
        checker content from the agent-mutable workspace. Bytes are
        frozen at registration, so later rewrites of the source file
        cannot substitute checker behavior.
        """
        specs: dict[str, CheckerSpec] = {}
        blobs: dict[str, bytes] = {}
        for checker_id, rel in sorted(files.items()):
            data = (root / rel).read_bytes()
            specs[checker_id] = parse_checker_spec(checker_id, data)
            blobs[checker_id] = data
        return cls(specs, blobs)

    def register(self, checker_id: str, data: bytes) -> CheckerSpec:
        """Register a spec supplied by trusted caller code."""
        spec = parse_checker_spec(checker_id, data)
        self._specs[checker_id] = spec
        self._blobs[checker_id] = data
        return spec

    def ids(self) -> frozenset[str]:
        """Registered ids — the ``known_recipes`` input for plans."""
        return frozenset(self._specs)

    def digest_of(self, checker_id: str) -> str | None:
        """The bound content digest, or None when unregistered."""
        spec = self._specs.get(checker_id)
        return None if spec is None else spec.digest

    def digests(self) -> dict[str, str]:
        """Id→digest map for obligation projection binding."""
        return {cid: s.digest for cid, s in self._specs.items()}

    def resolve(
        self, checker_id: str, expected_digest: str | None
    ) -> CheckerSpec:
        """Resolve a bound checker; unknown or mismatched fails closed.

        The captured spec bytes are re-hashed at use time and must
        equal both the registered digest and the digest the
        obligation bound — a mutated store or swapped spec never
        resolves.
        """
        spec = self._specs.get(checker_id)
        if spec is None:
            raise CyranoError(
                "CAPABILITY_UNAVAILABLE", f"checker {checker_id!r}"
            )
        blob = self._blobs.get(checker_id)
        if blob is not None and _file_digest(blob) != spec.digest:
            raise CyranoError(
                "CHECKER_DIGEST_MISMATCH",
                f"checker {checker_id} store diverged",
            )
        if expected_digest is not None and spec.digest != expected_digest:
            raise CyranoError(
                "CHECKER_DIGEST_MISMATCH",
                f"checker {checker_id} bound {expected_digest}",
            )
        return spec


def _field_failures(
    fields: Mapping[str, object],
    document: Mapping[str, object],
    *,
    stem: str,
) -> list[str]:
    """Apply each field rule; a missing field fails its operators."""
    failures: list[str] = []
    for name, rule in fields.items():
        rule_map = _str_map(rule, field=f"field {name} rule")
        present = name in document
        actual = document.get(name)
        if "required" in rule_map and not present:
            failures.append(f"{name} missing")
            continue
        if not present:
            failures.append(f"{name} absent")
            continue
        if "equals" in rule_map and actual != rule_map["equals"]:
            failures.append(f"{name}!={rule_map['equals']!r}")
        one_of = rule_map.get("one_of")
        if one_of is not None and (
            not isinstance(one_of, (list, tuple)) or actual not in one_of
        ):
            failures.append(f"{name} not in {one_of}")
        if rule_map.get("matches_stem") and actual != stem:
            failures.append(f"{name}!={stem!r}")
    return failures


def _json_document(path: Path) -> tuple[Mapping[str, object] | None, str]:
    """Read a JSON object; malformed is a violation, not an error."""
    try:
        body = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return None, f"{path.name} unparsable: {exc}"
    if not isinstance(body, dict):
        return None, f"{path.name} is not a JSON object"
    return body, ""


def _eval_paired_files(
    params: Mapping[str, object],
    *,
    root: Path,
    touched: frozenset[str],
    covered: frozenset[str],
) -> CheckerVerdict:
    """Every live trigger file needs a conforming derived file.

    Exception-covered pairs are skipped untouched; a missing or
    nonconforming derived file is a violation.
    """
    trigger = str(params["trigger"])
    derive = str(params["derive"])
    required = bool(params.get("required", True))
    fields = _str_map(params.get("json_fields", {}), field="json_fields")
    violations: list[str] = []
    checked = 0
    for path in sorted(root.glob(trigger)):
        rel = path.relative_to(root).as_posix()
        if rel in covered:
            continue
        derived_rel = derive.replace("{stem}", path.stem)
        if derived_rel in covered:
            continue
        checked += 1
        derived = root / derived_rel
        if not derived.exists():
            if required:
                violations.append(f"{rel}: missing {derived_rel}")
            continue
        document, error = _json_document(derived)
        if document is None:
            violations.append(f"{rel}: {error}")
            continue
        violations.extend(
            f"{derived_rel}: {failure}"
            for failure in _field_failures(fields, document, stem=path.stem)
        )
    if violations:
        return CheckerVerdict(
            "violated", "; ".join(violations), tuple(violations)
        )
    if checked == 0:
        return CheckerVerdict("unverifiable", "no trigger paths matched", ())
    return CheckerVerdict("satisfied", f"{checked} pairs conform")


def _eval_json_fields(
    params: Mapping[str, object],
    *,
    root: Path,
    touched: frozenset[str],
    covered: frozenset[str],
) -> CheckerVerdict:
    """Every touched file matching the glob must conform."""
    pattern = str(params["files"])
    fields = _str_map(params["fields"], field="fields")
    missing_is_violation = bool(params.get("missing_is_violation"))
    violations: list[str] = []
    checked = 0
    for rel in sorted(touched):
        if rel in covered or not fnmatch.fnmatchcase(rel, pattern):
            continue
        checked += 1
        path = root / rel
        if not path.exists():
            if missing_is_violation:
                violations.append(f"{rel} deleted")
            continue
        document, error = _json_document(path)
        if document is None:
            violations.append(f"{rel}: {error}")
            continue
        violations.extend(
            f"{rel}: {failure}"
            for failure in _field_failures(fields, document, stem=path.stem)
        )
    if violations:
        return CheckerVerdict(
            "violated", "; ".join(violations), tuple(violations)
        )
    if checked == 0:
        return CheckerVerdict("unverifiable", "no touched paths matched", ())
    return CheckerVerdict("satisfied", f"{checked} files conform")


def _eval_expected_postimage(
    params: Mapping[str, object],
    *,
    root: Path,
    touched: frozenset[str],
    covered: frozenset[str],
) -> CheckerVerdict:
    """Each expected path must exist and digest-match exactly."""
    files = _str_map(params["files"], field="files")
    violations: list[str] = []
    for rel, expected in sorted(files.items()):
        assert isinstance(expected, str)
        path = root / rel
        if not path.exists():
            violations.append(f"{rel} missing")
            continue
        try:
            actual = _file_digest(path.read_bytes())
        except OSError as exc:
            violations.append(f"{rel} unreadable: {exc}")
            continue
        if actual != expected:
            violations.append(f"{rel} digest {actual}")
    if violations:
        return CheckerVerdict(
            "violated", "; ".join(violations), tuple(violations)
        )
    return CheckerVerdict("satisfied", "postimages match")


_EVALUATORS = {
    "paired_files": _eval_paired_files,
    "json_fields": _eval_json_fields,
    "expected_postimage": _eval_expected_postimage,
}


def evaluate(
    spec: CheckerSpec,
    *,
    root: Path,
    touched_paths: tuple[str, ...],
    covered_paths: frozenset[str] = frozenset(),
) -> CheckerVerdict:
    """Run a spec's deterministic evaluator over the post-apply state.

    Only exception-covered paths are skipped. An evaluator failure —
    unreadable tree, bad path, unexpected error — is reported
    ``unverifiable`` and can never be folded into ``satisfied``.
    """
    touched = frozenset(touched_paths)
    for rel in touched:
        pure = PurePosixPath(rel)
        if pure.is_absolute() or ".." in pure.parts:
            return CheckerVerdict(
                "unverifiable", f"unsafe touched path {rel}", ()
            )
    evaluator = _EVALUATORS[spec.kind]
    try:
        return evaluator(
            spec.params,
            root=root,
            touched=touched,
            covered=covered_paths,
        )
    except CyranoError as exc:
        return CheckerVerdict("unverifiable", f"{exc.code} {exc}", ())
    except Exception as exc:  # noqa: BLE001 - errors are never PASS
        return CheckerVerdict("unverifiable", str(exc), ())
