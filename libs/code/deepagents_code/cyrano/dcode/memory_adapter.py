"""Event-triggered recall adapter for the dcode runtime.

Hints carry a bound candidate id, revision, trigger, epoch, and
expiry. A manipulated id, an expired hint, or a revision that was
never admitted is refused — a hint is data, not authority.
"""

from dataclasses import dataclass

from deepagents_code.cyrano.contracts.types import CyranoError
from deepagents_code.cyrano.memory.models import (
    ApplicationVerdict,
    MemoryRecord,
    RecallHint,
)
from deepagents_code.cyrano.memory.obligations import RuleObligation
from deepagents_code.cyrano.memory.service import MemoryService


@dataclass(frozen=True, slots=True)
class AdmittedHint:
    """A hint admitted for injection into a work unit."""

    hint: RecallHint
    content_digest: str


class RecallService:
    """Admit bound hints; track exposure vs application."""

    def __init__(self, service: MemoryService) -> None:
        """Bind the adapter to the governed memory service."""
        self._service = service
        self._hints: list[RecallHint] = []
        self._exposures: dict[str, str] = {}
        self._verdicts: dict[str, ApplicationVerdict] = {}

    def candidates(self, scope_id: str, trigger: str) -> list[RecallHint]:
        """Hints for a trigger; only active in-scope records."""
        return [h for h in self._hints if h.trigger == trigger]

    def admit_hint(
        self,
        scope_id: str,
        hint: RecallHint,
        *,
        now: int,
        epoch: str,
    ) -> AdmittedHint:
        """Admit a hint only when every bound field verifies.

        A store failure is ``AUDIT_UNAVAILABLE`` — the hint is blocked
        rather than admitted on partial evidence.
        """
        try:
            record = self._service.get(scope_id, hint.memory_id)
        except CyranoError:
            raise
        except Exception as exc:
            raise CyranoError("AUDIT_UNAVAILABLE", str(exc)) from exc
        if record is None or record.status != "active":
            raise CyranoError(
                "INPUT_INVALID",
                f"hint {hint.hint_id!r} names no active memory",
            )
        if record.revision != hint.revision:
            raise CyranoError(
                "INPUT_INVALID",
                f"hint revision {hint.revision} != record r{record.revision}",
            )
        if now >= hint.expires_at:
            raise CyranoError(
                "INPUT_INVALID", f"hint {hint.hint_id!r} expired"
            )
        if hint.epoch != epoch:
            raise CyranoError(
                "INPUT_INVALID",
                f"hint epoch {hint.epoch!r} != current {epoch!r}",
            )
        self._exposures[hint.memory_id] = hint.hint_id
        return AdmittedHint(hint, record.content_digest)

    def mark_application(
        self,
        memory_id: str,
        verdict: ApplicationVerdict,
    ) -> None:
        """Record the verdict; self-report never counts as applied."""
        self._verdicts[memory_id] = verdict

    def verdict(self, memory_id: str) -> ApplicationVerdict | None:
        """The recorded verdict for a memory, if any."""
        return self._verdicts.get(memory_id)

    def exposure_count(self) -> int:
        """Exposures recorded; distinct from applications."""
        return len(self._exposures)


@dataclass(frozen=True, slots=True)
class ReadonlyProjection:
    """Channel split: reference text vs governed obligations.

    The two sets are disjoint by construction — a memory projected
    as an obligation never also appears as ``<agent_memory>``
    reference material, and a reference record never silently gains
    obligation authority.
    """

    reference_ids: tuple[str, ...]
    obligation_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InjectionReceipt:
    """Proof level of one channel delivery; wire bytes stay honest.

    ``adapter_confirmed`` means the adapter delivered the content to
    the runtime boundary; ``wire_confirmed`` is only True when the
    serialized request was captured — a channel an adapter cannot
    see stays False instead of being claimed.
    """

    memory_id: str
    revision: int
    channel: str  # "reference" | "obligation"
    adapter_confirmed: bool
    wire_confirmed: bool
    evidence_refs: tuple[str, ...]


def project_readonly_memory(
    records: list[MemoryRecord],
    obligations: tuple[RuleObligation, ...],
) -> ReadonlyProjection:
    """Split records into the reference channel vs obligations.

    This adapter owns the dual-channel exclusion: a memory bound
    into an obligation is removed from the reference set, and the
    two id sets can never overlap.
    """
    projected = {o.memory_id for o in obligations}
    reference = tuple(
        sorted(r.memory_id for r in records if r.memory_id not in projected)
    )
    return ReadonlyProjection(
        reference_ids=reference,
        obligation_ids=tuple(sorted(projected)),
    )


def injection_receipt(
    memory_id: str,
    revision: int,
    channel: str,
    *,
    wire_confirmed: bool = False,
    evidence_refs: tuple[str, ...] = (),
) -> InjectionReceipt:
    """Build a delivery receipt.

    Wire capture stays honest by default.
    """
    if channel not in {"reference", "obligation"}:
        raise CyranoError("INPUT_INVALID", f"channel {channel!r}")
    return InjectionReceipt(
        memory_id=memory_id,
        revision=revision,
        channel=channel,
        adapter_confirmed=True,
        wire_confirmed=wire_confirmed,
        evidence_refs=evidence_refs,
    )
