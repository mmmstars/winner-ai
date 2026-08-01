"""Deterministic field-level conflict resolution with an audit trail."""

from __future__ import annotations

from datetime import datetime, timezone

from app.source_registry import source_policy


def resolve_records(records: list[dict], now: datetime | None = None) -> tuple[dict, list[dict]]:
    if not records:
        return {}, []
    now = now or datetime.now(timezone.utc)
    fields = set().union(*(record.keys() for record in records)) - {"source", "observed_at"}
    chosen, audit = {}, []
    for field in sorted(fields):
        candidates = []
        for record in records:
            value = record.get(field)
            if value is None or value == "":
                continue
            policy = source_policy(record.get("source", ""))
            observed = record.get("observed_at")
            if isinstance(observed, str):
                try:
                    observed = datetime.fromisoformat(observed.replace("Z", "+00:00"))
                except ValueError:
                    observed = None
            freshness = 1.0
            if observed:
                if observed.tzinfo is None:
                    observed = observed.replace(tzinfo=timezone.utc)
                freshness = max(.7, 1 - max(0, (now - observed).total_seconds()) / 864000)
            candidates.append((policy.reliability * freshness, policy.reliability, record.get("source", ""), value))
        if not candidates:
            continue
        candidates.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        score, _, source, value = candidates[0]
        chosen[field] = value
        audit.append({"field": field, "source": source, "score": round(score, 4), "conflict": len({str(item[3]) for item in candidates}) > 1})
    return chosen, audit

