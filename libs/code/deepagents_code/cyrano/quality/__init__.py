"""Quality pack: policy resolution, native checks, docstring review.

Tool exit codes are never treated as pass/fail truth; every run is
parsed into a typed report and compared against baselines explicitly.
"""

from deepagents_code.cyrano.quality.policy import (
    QualityPolicy,
    check_path_in_scope,
    require_run_permit,
    resolve_quality_policy,
)
from deepagents_code.cyrano.quality.runner import (
    BaselineDecision,
    QualityReportStore,
    RawCheckReport,
    SnapshotManifest,
    attempt_outcome,
    compare_diagnostic_multisets,
    run_native_checks,
    snapshot_python_files,
)

__all__ = [
    "BaselineDecision",
    "QualityPolicy",
    "QualityReportStore",
    "RawCheckReport",
    "SnapshotManifest",
    "attempt_outcome",
    "check_path_in_scope",
    "compare_diagnostic_multisets",
    "require_run_permit",
    "resolve_quality_policy",
    "run_native_checks",
    "snapshot_python_files",
]
