"""Evaluation and guarded, bounded model-weight recalibration."""

from __future__ import annotations

from app.backtest import evaluate


DEFAULT_WEIGHTS = {"market": .45, "elo": .20, "goals": .20, "factors": .15}


def safe_recalibration(current: dict[str, float], candidate: dict[str, float], current_items, candidate_items, minimum_matches: int = 200) -> dict:
    if len(current_items) < minimum_matches or len(candidate_items) != len(current_items):
        return {"accepted": False, "reason": "נדרשים לפחות 200 משחקים זהים לבדיקה", "weights": current}
    before, after = evaluate(current_items), evaluate(candidate_items)
    bounded = all(.05 <= float(candidate.get(key, 0)) <= .70 for key in DEFAULT_WEIGHTS)
    normalized = abs(sum(candidate.values()) - 1) < .001
    improved = after["log_loss"] <= before["log_loss"] and after["brier_score"] <= before["brier_score"]
    if not (bounded and normalized and improved):
        return {"accepted": False, "reason": "המשקלים נדחו בבדיקת הבטיחות", "weights": current, "before": before, "after": after}
    return {"accepted": True, "reason": "אושר לאחר שיפור מחוץ למדגם", "weights": candidate, "before": before, "after": after}

