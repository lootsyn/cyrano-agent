"""WP05 context tests: epochs, binding revocation, warming policy."""

import pytest

from deepagents_code.cyrano.context.binding import (
    MemoryView,
    bind_context,
    memory_entry_usable,
)
from deepagents_code.cyrano.context.compiler import (
    Block,
    compile_context,
)
from deepagents_code.cyrano.context.epochs import (
    EpochManager,
    epoch_for,
    ttl_status,
)
from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.events.coverage import (
    WarmingPolicy,
    WarmScheduler,
    record_keepalive,
)


def _epoch(**over):
    fields = {
        "tool_inventory_digest": "t1",
        "model_identity": "m1",
        "route": "r1",
        "release_digest": "rel1",
        "profile_digest": "p1",
        "memory_view_digest": "mv1",
    }
    fields.update(over)
    return epoch_for(**fields)


class TestEpochs:
    """CACHE-TOOLS, CON-CTX-02, CON-CAC-01/03/11."""

    def test_cache_tools_new_epoch_no_mixing(self):
        manager = EpochManager(_epoch())
        first = manager.current
        second = manager.update(tool_inventory_digest="t2")
        assert second.epoch_id != first.epoch_id
        assert second.generation == first.generation + 1
        assert second.tool_inventory_digest == "t2"

    def test_con_ctx_02_tool_schema_change_new_epoch(self):
        a = _epoch(tool_inventory_digest="schema-a")
        b = _epoch(tool_inventory_digest="schema-b")
        assert a.epoch_id != b.epoch_id

    def test_con_cac_03_model_switch_separate_identity(self):
        a = _epoch(model_identity="model-a")
        b = _epoch(model_identity="model-b")
        assert a.epoch_id != b.epoch_id

    def test_con_cac_01_ttl_from_request_start(self):
        assert (
            ttl_status(
                request_start=0,
                ttl_seconds=300,
                now=301,
                clock_kind="wall",
            )
            == "expired"
        )
        assert (
            ttl_status(
                request_start=0,
                ttl_seconds=300,
                now=299,
                clock_kind="wall",
            )
            == "valid"
        )

    def test_con_cac_11_restarted_monotonic_is_unknown(self):
        assert (
            ttl_status(
                request_start=0,
                ttl_seconds=300,
                now=10,
                clock_kind="monotonic_restarted",
            )
            == "unknown"
        )

    def test_stale_epoch_binding_refused(self):
        manager = EpochManager(_epoch())
        old = manager.current.epoch_id
        manager.update(tool_inventory_digest="t9")
        with pytest.raises(CyranoError) as exc:
            manager.require_current(old)
        assert exc.value.code == "STALE_EPOCH"


class TestBinding:
    """CON-CTX-05, UH-CACHE-05/06: permits and memory pinning."""

    def test_con_ctx_05_revoked_permit_pauses_bind(self):
        compiled = compile_context([Block("a", 0, "x")], {})
        view = MemoryView("mv1", "rel-mem", frozenset())
        with pytest.raises(CyranoError) as exc:
            bind_context(
                compiled,
                _epoch(),
                permit_id="p1",
                is_revoked=lambda pid: True,
                memory_view=view,
            )
        assert exc.value.code == "PERMIT_REVOKED"

    def test_bind_succeeds_with_live_permit(self):
        compiled = compile_context([Block("a", 0, "x")], {})
        view = MemoryView("mv1", "rel-mem", frozenset())
        receipt = bind_context(
            compiled,
            _epoch(),
            permit_id="p1",
            is_revoked=lambda pid: False,
            memory_view=view,
        )
        assert receipt.memory_view_digest == "mv1"
        assert receipt.stable_digest == compiled.stable_digest

    def test_uh_cache_05_release_change_new_view(self):
        old = _epoch(memory_view_digest="mv1")
        new = _epoch(memory_view_digest="mv2")
        assert old.epoch_id != new.epoch_id

    def test_uh_cache_06_revoked_memory_never_served(self):
        view = MemoryView("mv1", "rel", frozenset({"mem-bad"}))
        assert memory_entry_usable("mem-bad", view) is False
        assert memory_entry_usable("mem-ok", view) is True


class TestWarmingPolicy:
    """CON-CAC-04..08/12, CON-CAC-02: honest warming semantics."""

    def test_con_cac_06_default_off_zero_calls(self):
        scheduler = WarmScheduler(WarmingPolicy())
        assert (
            scheduler.maybe_warm(pending_input=False, route_known=True)
            == "disabled"
        )
        assert scheduler.calls_made == 0

    def test_con_cac_05_pending_input_wins(self):
        scheduler = WarmScheduler(WarmingPolicy(enabled=True, cost_cap=10))
        assert (
            scheduler.maybe_warm(pending_input=True, route_known=True)
            == "deferred_user_input"
        )

    def test_con_cac_04_unobserved_route_refused(self):
        scheduler = WarmScheduler(WarmingPolicy(enabled=True, cost_cap=10))
        with pytest.raises(CyranoError) as exc:
            scheduler.maybe_warm(pending_input=False, route_known=False)
        assert exc.value.code == "CAPABILITY_UNAVAILABLE"

    def test_con_cac_07_budget_contention_single_winner(self):
        scheduler = WarmScheduler(WarmingPolicy(enabled=True, cost_cap=1))
        assert scheduler.reserve_budget(1) is True
        assert scheduler.reserve_budget(1) is False

    def test_con_cac_08_late_result_billed_stale(self):
        scheduler = WarmScheduler(WarmingPolicy(enabled=True, cost_cap=10))
        assert scheduler.complete_warm(generation_current=False) == (
            "billed_stale"
        )
        assert scheduler.calls_made == 1

    def test_con_cac_12_keepalive_is_network_only(self):
        obs = record_keepalive(True)
        assert obs.network_reachable is True
        assert obs.cache_read is None
        assert obs.cache_write is None

    def test_con_cac_02_hit_needs_usage_not_timing(self):
        scheduler = WarmScheduler(WarmingPolicy(enabled=True, cost_cap=10))
        assert (
            scheduler.maybe_warm(pending_input=False, route_known=True)
            == "warm"
        )
        obs = record_keepalive(True)
        assert obs.cache_read is None
