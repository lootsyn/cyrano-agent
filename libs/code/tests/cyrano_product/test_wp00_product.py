"""WP00 product tests: runtime lock, probes, and doctor verdicts."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.dcode.adapter import require_governed
from deepagents_code.cyrano.dcode.probes import (
    PROBE_NAMES,
    DistributionInfo,
    doctor,
    inspect_installed_distribution,
    run_compatibility_probe,
    verify_runtime_lock,
    write_runtime_lock,
)


def _dist(digest: str = "sha256:" + "a" * 64) -> DistributionInfo:
    return DistributionInfo(
        name="deepagents-code",
        version="0.1.70",
        location="/env/site-packages",
        editable=False,
        record_digest=digest,
        file_count=14,
    )


def _all_verified() -> dict[str, str]:
    return dict.fromkeys(PROBE_NAMES, "verified")


def test_runtime_hash_mismatch_refuses_governed(tmp_path):
    """RUNTIME-HASH: same version, different digest must refuse."""
    lock_path = tmp_path / "runtime-lock.json"
    write_runtime_lock(
        lock_path,
        distribution=_dist(),
        probes=_all_verified(),
        source_observation={"kind": "test"},
    )
    verify_runtime_lock(
        json.loads(lock_path.read_text()),
        distribution=_dist(),
        probes=_all_verified(),
    )
    tampered = _dist("sha256:" + "b" * 64)
    with pytest.raises(CyranoError, match="RUNTIME_HASH_MISMATCH"):
        verify_runtime_lock(
            json.loads(lock_path.read_text()),
            distribution=tampered,
            probes=_all_verified(),
        )
    with pytest.raises(CyranoError, match="DCODE_RUNTIME_NOT_VERIFIED"):
        require_governed(dict.fromkeys(PROBE_NAMES, "not_tested"))


def test_runtime_missing_reported_not_faked():
    """RUNTIME-MISSING: absent distribution reports missing."""
    with pytest.raises(CyranoError, match="DISTRIBUTION_MISSING"):
        inspect_installed_distribution("cyrano-no-such-distribution")
    report = doctor(distribution_name="cyrano-no-such-distribution")
    assert report["verdict"] == "missing"
    assert report["install_required"] is True
    assert report["governed_ready"] is False
    assert set(report["probes"].values()) == {"not_tested"}


def test_runtime_native_unsupported_recorded():
    """RUNTIME-NATIVE: an absent surface is unsupported, not patched."""
    report = run_compatibility_probe("context_manifest")
    assert report.status == "not_tested"

    def missing_impl() -> tuple[str, str, tuple[str, ...]]:
        return ("unsupported", "documented API absent from install", ())

    report = run_compatibility_probe(
        "extension_loading",
        impls={"extension_loading": missing_impl},
    )
    assert report.status == "unsupported"
    assert report.status != "verified"


def test_uh_ops_02_missing_extension_surface_blocks():
    """UH-OPS-02: doctor blocks unsupported runtimes, no fake API."""
    impls = {
        name: (lambda: ("unsupported", "absent", ())) for name in PROBE_NAMES
    }
    report = doctor(distribution_name="deepagents-code", impls=impls)
    assert report["verdict"] == "unsupported_runtime"
    assert report["governed_ready"] is False
    with pytest.raises(CyranoError, match="DCODE_RUNTIME_NOT_VERIFIED"):
        require_governed(report["probes"])


def test_integ_wp_bootstrap_partial_not_verified():
    """INTEG-WP-BOOTSTRAP: bootstrap verdict stays not_verified."""
    report = doctor(distribution_name="deepagents-code")
    assert report["verdict"] in {"bootstrap_only", "verified"}
    if report["verdict"] == "bootstrap_only":
        assert report["governed_ready"] is False
        assert "not_tested" in report["probes"].values()
    with tempfile.TemporaryDirectory() as directory:
        lock_status = write_runtime_lock(
            Path(directory) / "lock.json",
            distribution=_dist(report["distribution"]["record_digest"]),
            probes=report["probes"],
            source_observation={"kind": "test"},
        )["status"]
    if "not_tested" in report["probes"].values():
        assert lock_status == "not_verified"


def test_lock_write_rejects_missing_probe(tmp_path):
    """A lock without every required probe is refused, not written."""
    probes = _all_verified()
    del probes["cancel_recovery"]
    with pytest.raises(CyranoError, match="RUNTIME_LOCK_INCOMPLETE"):
        write_runtime_lock(
            tmp_path / "lock.json",
            distribution=_dist(),
            probes=probes,
            source_observation={},
        )
    assert not (tmp_path / "lock.json").exists()


def test_verify_lock_rejects_python_drift(tmp_path):
    lock = write_runtime_lock(
        tmp_path / "lock.json",
        distribution=_dist(),
        probes=_all_verified(),
        source_observation={},
    )
    lock["python"] = "0.0.0"
    with pytest.raises(
        CyranoError,
        match=r"RUNTIME_HASH_MISMATCH|RUNTIME_PYTHON_CHANGED",
    ):
        verify_runtime_lock(lock, distribution=_dist(), probes=_all_verified())
