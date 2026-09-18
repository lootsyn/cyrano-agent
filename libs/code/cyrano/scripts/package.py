"""Create and verify a source-only ZIP; no secrets or caches."""

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT.parent
ARCHIVE_ROOT = "Cyrano_Agent_Code_Additions"
EXCLUDED = {
    ".git",
    ".venv",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".state",
    ".cache",
    "node_modules",
}


def digest(data: bytes) -> str:
    """Return a raw SHA256 for integrity, not execution authority."""
    return hashlib.sha256(data).hexdigest()


def inventory() -> list[Path]:
    """Reject links and secrets rather than shipping their contents."""
    files = []
    owners = [
        CODE / "deepagents_code/cyrano",
        ROOT,
        CODE / "tests/unit_tests/cyrano",
        CODE / "tests/cyrano_product",
        CODE / ".agents/skills/cyrano-development",
        CODE / "CYRANO_START_HERE.ko.md",
    ]
    for owner in owners:
        paths = [owner] if owner.is_file() else sorted(owner.rglob("*"))
        for path in paths:
            relative = path.relative_to(CODE)
            if any(
                part in EXCLUDED or part.endswith(".egg-info")
                for part in relative.parts
            ):
                continue
            if relative.as_posix().startswith("cyrano/evidence/runs/"):
                continue
            if path.is_symlink():
                raise ValueError(f"REFUSE_SYMLINK: {relative}")
            if not path.is_file() or path.suffix == ".pyc":
                continue
            if path.name == ".env" or path.suffix in {
                ".pem",
                ".key",
                ".sqlite",
                ".sqlite3",
                ".db",
            }:
                raise ValueError(f"REFUSE_SECRET_OR_RUNTIME_FILE: {relative}")
            if path.name != "MANIFEST.sha256":
                files.append(path)
    if not files or not any(
        str(p.relative_to(CODE)).startswith("deepagents_code/cyrano/")
        for p in files
    ):
        raise ValueError("PRODUCT_SOURCE_MISSING")
    return sorted(set(files))


def verify_zip(path: Path) -> dict[str, object]:
    """Check CRC, canonical paths, inventory and payload hashes."""
    with zipfile.ZipFile(path) as archive:
        bad_crc = archive.testzip()
        if bad_crc is not None:
            raise ValueError(f"CRC_MISMATCH: {bad_crc}")
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("DUPLICATE_ARCHIVE_PATH")
        for member in archive.infolist():
            name = PurePosixPath(member.filename)
            if (
                name.is_absolute()
                or ".." in name.parts
                or name.parts[0] != ARCHIVE_ROOT
            ):
                raise ValueError(f"UNSAFE_ARCHIVE_PATH: {name}")
            if stat.S_ISLNK(member.external_attr >> 16):
                raise ValueError(f"SYMLINK_IN_ARCHIVE: {name}")
        manifest_name = ARCHIVE_ROOT + "/MANIFEST.sha256"
        lines = archive.read(manifest_name).decode("utf-8").splitlines()
        expected = {}
        for line in lines:
            checksum, relative = line.split("  ", 1)
            if relative in expected:
                raise ValueError("DUPLICATE_MANIFEST_ENTRY")
            expected[relative] = checksum
        actual = {
            name[len(ARCHIVE_ROOT) + 1 :]
            for name in names
            if name != manifest_name
        }
        if actual != set(expected):
            raise ValueError("MANIFEST_INVENTORY_MISMATCH")
        for relative, checksum in expected.items():
            if digest(archive.read(ARCHIVE_ROOT + "/" + relative)) != checksum:
                raise ValueError(f"HASH_MISMATCH: {relative}")
        return {
            "kind": "executed_zip_integrity_check",
            "file_count": len(names),
            "hashed_payload_files": len(expected),
            "crc_verified": True,
            "path_safety_verified": True,
            "manifest_verified": True,
            "archive_sha256": digest(path.read_bytes()),
            "archive_bytes": path.stat().st_size,
            "not_claimed": [
                "signed_release",
                "production_runtime",
                "live_effectiveness",
            ],
            "native_dcode_base_included": False,
            "native_edits_included": False,
            "scope": "Cyrano-owned source additions; not full fork export",
        }


def main() -> int:
    """Package to an external path or verify an archive explicitly."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if (args.output is None) == (args.verify is None):
        parser.error("supply exactly one of --output or --verify")
    if args.verify is not None:
        report = verify_zip(args.verify.resolve())
    else:
        target = args.output.resolve()
        if target == CODE or CODE in target.parents:
            parser.error("write the archive outside the project")
        paths = inventory()
        manifest = "".join(
            f"{digest(path.read_bytes())}  "
            f"{path.relative_to(CODE).as_posix()}\n"
            for path in paths
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(
            target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            for path in paths:
                info = zipfile.ZipInfo(
                    ARCHIVE_ROOT + "/" + path.relative_to(CODE).as_posix()
                )
                info.date_time = (2026, 9, 16, 0, 0, 0)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                archive.writestr(info, path.read_bytes(), compresslevel=9)
            archive.writestr(ARCHIVE_ROOT + "/MANIFEST.sha256", manifest)
        report = verify_zip(target)
        target.with_suffix(".validation.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
