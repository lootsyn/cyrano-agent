"""WP23 EVAL-WIRE-01 — model-dispatch observation, digest-only.

``dispatch_confirmed`` is emitted only when the observation happens at
the boundary that hands the final assembled request to the model
handler — inside the extension middleware's model-call wrap. The
provider client may still transform the request into transport bytes;
those bytes are NOT observed, so ``wire_confirmed`` is pinned False.
An adapter-side projection is honest evidence of internal delivery,
never of the wire. No content, credential, or transport structure may
persist.
"""

from deepagents_code.cyrano.contracts.canonical import digest
from deepagents_code.cyrano.dcode.memory_adapter import injection_receipt
from deepagents_code.cyrano.dcode.wire import (
    WireCapture,
    _message_projection,
    _tool_projection,
    wire_receipt,
)


class _FakeModel:
    _llm_type = "fake-provider"
    model = "fake-model-1"


class _FakeRequest:
    """Stand-in for the assembled `ModelRequest` at the boundary."""

    def __init__(self) -> None:
        self.messages = [
            _Msg("human", "write the sidecar"),
            _Msg("ai", "", tool_calls=[{"name": "write_file"}]),
        ]
        self.system_message = _Msg("system", "be terse")
        self.tools = [_FakeTool()]
        self.model = _FakeModel()
        self.model_settings = {"temperature": 0}
        self.tool_choice = "auto"
        self.response_format = None
        self.state = {"messages": []}


class _Msg:
    def __init__(self, type_, content, **kw) -> None:
        self.type = type_
        self.content = content
        for key, value in kw.items():
            setattr(self, key, value)

    def model_dump(self, mode: str = "json"):  # noqa: ARG002
        out: dict[str, object] = {
            "type": self.type,
            "content": self.content,
        }
        tool_calls = getattr(self, "tool_calls", None)
        if tool_calls is not None:
            out["tool_calls"] = tool_calls
        return out


class _FakeTool:
    name = "write_file"

    def get_input_schema(self):
        class _Schema:
            def model_json_schema(self):
                return {"type": "object", "properties": {"file_path": {}}}

        return _Schema()


def test_record_produces_digest_only_evidence():
    capture = WireCapture(run_id="run-1", context_digest="ctx:d")
    evidence = capture.record(_FakeRequest())
    assert evidence.dispatch_confirmed is True
    assert evidence.wire_confirmed is False
    assert evidence.message_digest.startswith("sha256:")
    assert evidence.tools_digest.startswith("sha256:")
    assert evidence.model_params_digest.startswith("sha256:")
    assert evidence.routing_digest.startswith("sha256:")
    assert evidence.provider == "fake-provider"
    assert evidence.model == "fake-model-1"
    assert evidence.message_roles == ("system", "human", "ai")
    # Nothing content-bearing survives on the record.
    assert not hasattr(evidence, "messages")
    assert not hasattr(evidence, "content")
    assert not hasattr(evidence, "headers")


def test_record_never_serializes_secret_shapes():
    """Authorization/cookie material is reduced to digests."""
    from dataclasses import asdict

    request = _FakeRequest()
    request.messages.append(_Msg("human", "token sk-secret-value"))
    capture = WireCapture(run_id="run-1")
    evidence = capture.record(request)
    dumped = str(asdict(evidence))
    assert "sk-secret-value" not in dumped
    assert "write the sidecar" not in dumped


def test_sequence_and_run_linkage():
    capture = WireCapture(run_id="run-7")
    first = capture.record(_FakeRequest())
    second = capture.record(_FakeRequest())
    assert first.sequence == 0
    assert second.sequence == 1
    assert first.run_id == second.run_id == "run-7"
    assert first.evidence_digest != second.evidence_digest


def test_obligation_digest_links_projection():
    capture = WireCapture(
        run_id="r",
        obligation_digest=digest({"obligations": ["o1"]}),
    )
    evidence = capture.record(_FakeRequest())
    assert evidence.obligation_digest == digest({"obligations": ["o1"]})


def test_wire_receipt_adapter_only_not_confirmed():
    receipt = wire_receipt(None, context_projected=True)
    assert receipt["dispatch_confirmed"] is False
    assert receipt["wire_confirmed"] is False
    assert receipt["context_projected"] is True
    assert receipt["evidence_refs"] == ()


def test_dispatch_receipt_confirmed_wire_stays_false():
    """Dispatch observation never upgrades to wire confirmation."""
    capture = WireCapture(run_id="r")
    capture.record(_FakeRequest())
    receipt = wire_receipt(capture, context_projected=True)
    assert receipt["dispatch_confirmed"] is True
    assert receipt["wire_confirmed"] is False
    refs = receipt["evidence_refs"]
    assert isinstance(refs, tuple) and len(refs) == 1


def test_injection_receipt_wire_honesty():
    """Dispatch-confirmed delivery is not wire confirmation."""
    receipt = injection_receipt(
        "m1", 2, "obligation", dispatch_confirmed=False
    )
    assert receipt.adapter_confirmed is True
    assert receipt.dispatch_confirmed is False
    assert receipt.wire_confirmed is False
    confirmed = injection_receipt(
        "m1",
        2,
        "obligation",
        dispatch_confirmed=True,
        evidence_refs=("sha256:abc",),
    )
    assert confirmed.dispatch_confirmed is True
    # Transport bytes are never observed — wire stays pinned False.
    assert confirmed.wire_confirmed is False
    assert confirmed.evidence_refs == ("sha256:abc",)


def test_message_projection_digests_content():
    proj = _message_projection(_Msg("human", "hello secret"))
    assert str(proj["content_digest"]).startswith("sha256:")
    assert "hello secret" not in str(proj)


def test_tool_projection_binds_schema():
    proj = _tool_projection(_FakeTool())
    assert proj["name"] == "write_file"
    assert str(proj["schema_digest"]).startswith("sha256:")
