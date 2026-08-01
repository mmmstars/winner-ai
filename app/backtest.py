import math
from typing import Literal

from pydantic import BaseModel, Field


Selection = Literal["1", "X", "2"]


class BacktestItem(BaseModel):
    probabilities: dict[Selection, float]
    result: Selection


class BacktestRequest(BaseModel):
    items: list[BacktestItem] = Field(min_length=1, max_length=10000)


def evaluate(items: list[BacktestItem]) -> dict:
    correct = 0
    brier_total = 0.0
    log_total = 0.0
    buckets = {index: {"count": 0, "correct": 0} for index in range(5, 11)}
    for item in items:
        values = normalized(item.probabilities)
        prediction = max(values, key=values.get)
        correct += int(prediction == item.result)
        for selection in ("1", "X", "2"):
            target = 1.0 if selection == item.result else 0.0
            brier_total += (values[selection] - target) ** 2
        log_total -= math.log(max(values[item.result], 1e-12))
        confidence = values[prediction]
        bucket = min(10, max(5, int(confidence * 10)))
        buckets[bucket]["count"] += 1
        buckets[bucket]["correct"] += int(prediction == item.result)
    count = len(items)
    calibration = []
    for bucket, data in buckets.items():
        if data["count"]:
            calibration.append({
                "range": f"{bucket * 10}-{min(100, bucket * 10 + 9)}%",
                "count": data["count"],
                "accuracy": round(data["correct"] / data["count"], 4),
            })
    return {
        "matches": count,
        "accuracy": round(correct / count, 4),
        "brier_score": round(brier_total / count, 4),
        "log_loss": round(log_total / count, 4),
        "calibration": calibration,
    }


def normalized(probabilities: dict[str, float]) -> dict[str, float]:
    values = {key: max(0.0, float(probabilities.get(key, 0.0))) for key in ("1", "X", "2")}
    total = sum(values.values())
    if total <= 0:
        return {"1": 1 / 3, "X": 1 / 3, "2": 1 / 3}
    return {key: value / total for key, value in values.items()}
