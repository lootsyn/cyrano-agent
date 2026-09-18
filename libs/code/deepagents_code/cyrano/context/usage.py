"""Provider usage normalization: absent metrics stay absent.

Missing cache counters normalize to ``None``, never to a fabricated
zero hit. A latency improvement is not a cache hit, and an inclusive-
semantics flag left unconfirmed keeps the ratio unresolved.
"""

from dataclasses import dataclass
from typing import Mapping

from deepagents_code.cyrano.context.compiler import cache_read_ratio
from deepagents_code.cyrano.contracts.types import CyranoError


@dataclass(frozen=True, slots=True)
class UsageReport:
    """Normalized provider usage; ``None`` means not reported."""

    total_input: int | None
    cache_read: int | None
    cache_write: int | None
    inclusive_semantics: bool | None
    wire_observed: bool


def normalize_usage(raw: Mapping[str, object] | None) -> UsageReport:
    """Map a provider response to a report; missing stays missing."""
    if raw is None:
        return UsageReport(None, None, None, None, False)

    def number(key: str) -> int | None:
        value = raw.get(key)
        if value is None:
            return None
        if type(value) is not int or value < 0:
            raise CyranoError("INVALID_USAGE", f"{key}={value!r}")
        return value

    semantics = raw.get("cache_read_inclusive")
    if semantics is not None and type(semantics) is not bool:
        raise CyranoError("INVALID_USAGE", "inclusive flag not bool")
    return UsageReport(
        total_input=number("input_tokens"),
        cache_read=number("cache_read_tokens"),
        cache_write=number("cache_write_tokens"),
        inclusive_semantics=semantics,
        wire_observed=True,
    )


def measured_cache_ratio(report: UsageReport) -> float | None:
    """Ratio only from measured counters with known semantics."""
    return cache_read_ratio(
        report.total_input,
        report.cache_read,
        inclusive_semantics=report.inclusive_semantics,
    )
