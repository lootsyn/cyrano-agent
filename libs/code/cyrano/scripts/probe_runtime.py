"""Read runtime metadata only; never launch or install anything."""

import importlib.metadata
import json
import platform
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    """Report facts; unexecuted compatibility probes stay unverified."""
    packages = {}
    for name in ("deepagents-code", "deepagents", "langchain", "pydantic"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    report = {
        "kind": "installed_metadata_only",
        "python": platform.python_version(),
        "packages": packages,
        "dcode_executable_found": shutil.which("dcode") is not None,
        "runtime_compatibility": "not_tested",
        "governed_ready": False,
        "network_or_model_executed": False,
    }
    (ROOT / "evidence/runtime-metadata.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
