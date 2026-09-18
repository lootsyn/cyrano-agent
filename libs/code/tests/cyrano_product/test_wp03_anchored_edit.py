"""WP03 anchored-edit contract cases CON-EDT-01..12."""

import errno
from pathlib import Path

import pytest

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.intelligence.contracts import (
    AnalysisError,
    GraphRelation,
    IndexBinding,
)
from deepagents_code.cyrano.kernel.anchored_edit import (
    AnchoredEditService,
    EditHunk,
    PatchAnchor,
    anchor_for,
)

SVC = AnchoredEditService()


def _anchor(content: bytes, needle: bytes, path: str = "f.txt") -> PatchAnchor:
    start = content.find(needle)
    return PatchAnchor(
        path=path,
        start=start,
        end=start + len(needle),
        expected_digest=_digest(needle),
    )


def _digest(data: bytes) -> str:
    from hashlib import sha256

    return "sha256:" + sha256(data).hexdigest()


def _hunk(
    content: bytes, needle: bytes, repl: bytes, path="f.txt"
) -> EditHunk:
    return EditHunk(_anchor(content, needle, path), repl)


class TestValidation:
    def test_con_edt_01_exact_bytes_changed(self):
        content = b"alpha beta gamma"
        SVC.validate_patch(
            [_hunk(content, b"beta", b"BETA")],
            {"f.txt": content},
        )

    def test_con_edt_02_stale_anchor_rejected(self):
        content = b"alpha beta gamma"
        stale = _anchor(content, b"beta")
        drifted = b"alpha DELTA gamma"
        with pytest.raises(CyranoError) as exc:
            SVC.validate_patch(
                [EditHunk(stale, b"X")],
                {"f.txt": drifted},
            )
        assert exc.value.code == "PATCH_STALE"

    def test_con_edt_03_short_tag_never_identifies(self):
        content = b"foo foo-suffix"
        start = content.find(b"foo")
        # anchor claims the later occurrence's digest but the
        # earlier occurrence's range — identity mismatch
        anchor = PatchAnchor(
            path="f.txt",
            start=start,
            end=start + 3,
            expected_digest=_digest(b"foo-suffix"),
        )
        with pytest.raises(CyranoError) as exc:
            SVC.validate_patch([EditHunk(anchor, b"X")], {"f.txt": content})
        assert exc.value.code == "PATCH_STALE"

    def test_con_edt_04_ambiguous_text_rejected(self):
        content = b"x x x"
        with pytest.raises(CyranoError) as exc:
            anchor_for(content, b"x")
        assert exc.value.code == "INPUT_INVALID"

    def test_con_edt_06_nfd_bytes_rejected(self):
        import unicodedata

        nfc = unicodedata.normalize("NFC", "한").encode()
        nfd = unicodedata.normalize("NFD", "한").encode()
        content = b"p " + nfc + b" s"
        anchor = PatchAnchor(
            path="f.txt",
            start=2,
            end=2 + len(nfc),
            expected_digest=_digest(nfd),
        )
        with pytest.raises(CyranoError) as exc:
            SVC.validate_patch([EditHunk(anchor, b"Y")], {"f.txt": content})
        assert exc.value.code == "PATCH_STALE"

    def test_con_edt_07_path_escape_denied(self):
        anchor = PatchAnchor(
            path="../secret",
            start=0,
            end=1,
            expected_digest=_digest(b"x"),
        )
        with pytest.raises(CyranoError) as exc:
            SVC.validate_patch([EditHunk(anchor, b"Y")], {"../secret": b"x"})
        assert exc.value.code == "ACL_DENIED"

    def test_con_edt_09_one_stale_hunk_fails_whole_patch(self):
        content = b"aaa bbb ccc"
        good = _hunk(content, b"aaa", b"A")
        stale = EditHunk(PatchAnchor("f.txt", 4, 7, _digest(b"ZZZ")), b"B")
        good2 = _hunk(content, b"ccc", b"C")
        with pytest.raises(CyranoError) as exc:
            SVC.validate_patch([good, stale, good2], {"f.txt": content})
        assert exc.value.code == "PATCH_STALE"


class TestApply:
    def test_con_edt_05_crlf_preserved(self, tmp_path):
        content = b"line1\r\nline2\r\n"
        (tmp_path / "f.txt").write_bytes(content)
        hunk = _hunk(content, b"line2", b"LINE2")
        journal = tmp_path / "journal"
        result = SVC.apply_candidate(
            tmp_path,
            [hunk],
            journal,
            preimage_digests={"f.txt": SVC.preimage_digest(content)},
        )
        out = (tmp_path / "f.txt").read_bytes()
        assert out == b"line1\r\nLINE2\r\n"
        assert result.digests["f.txt"] == _digest(out)

    def test_con_edt_08_symlink_swap_blocked(self, tmp_path):
        content = b"original"
        target = tmp_path / "f.txt"
        target.write_bytes(content)
        hunk = _hunk(content, b"original", b"replaced")
        SVC.validate_patch([hunk], {"f.txt": content})
        # swap for a symlink between validate and apply
        real = tmp_path / "elsewhere.txt"
        real.write_bytes(b"secret")
        target.unlink()
        target.symlink_to(real)
        with pytest.raises(CyranoError) as exc:
            SVC.apply_candidate(
                tmp_path,
                [hunk],
                tmp_path / "j",
                preimage_digests={"f.txt": SVC.preimage_digest(content)},
            )
        assert exc.value.code == "PATH_ESCAPE"
        assert real.read_bytes() == b"secret"

    def test_con_edt_10_io_error_needs_reconciliation(self, tmp_path):
        content = b"data"
        (tmp_path / "f.txt").write_bytes(content)
        hunk = _hunk(content, b"data", b"new")
        journal = tmp_path / "j"

        import unittest.mock as mock

        def enospc(*a, **k):
            raise OSError(errno.ENOSPC, "No space left")

        with mock.patch.object(Path, "write_bytes", enospc):
            with pytest.raises(CyranoError) as exc:
                SVC.apply_candidate(
                    tmp_path,
                    [hunk],
                    journal,
                    preimage_digests={"f.txt": SVC.preimage_digest(content)},
                )
        assert exc.value.code == "APPLY_INCOMPLETE"
        entry = next(journal.iterdir())
        assert "needs_reconciliation" in entry.read_text()

    def test_con_edt_11_user_edit_conflict_preserved(self, tmp_path):
        content = b"agent validated this"
        target = tmp_path / "f.txt"
        target.write_bytes(content)
        hunk = _hunk(content, b"validated", b"replaced")
        SVC.validate_patch([hunk], {"f.txt": content})
        target.write_bytes(b"user changed meanwhile")
        with pytest.raises(CyranoError) as exc:
            SVC.apply_candidate(
                tmp_path,
                [hunk],
                tmp_path / "j",
                preimage_digests={"f.txt": SVC.preimage_digest(content)},
            )
        assert exc.value.code == "PATCH_CONFLICT"
        assert target.read_bytes() == b"user changed meanwhile"

    def test_con_edt_12_index_stale_on_env_change(self):
        bound = IndexBinding(
            workspace_id="w",
            source_digest="s",
            environment_digest="env1",
            acl_digest="a",
            provider_digest="p",
            schema_version="1",
        )
        changed = IndexBinding(
            workspace_id="w",
            source_digest="s",
            environment_digest="env2",
            acl_digest="a",
            provider_digest="p",
            schema_version="1",
        )
        with pytest.raises(AnalysisError) as exc:
            bound.require_match(changed)
        assert "INDEX_BINDING_MISMATCH" in str(exc.value)

    def test_inferred_relation_not_authority(self):
        rel = GraphRelation("a", "b", "calls", "inferred")
        with pytest.raises(AnalysisError):
            rel.require_declared()
        GraphRelation("a", "b", "calls", "declared")
