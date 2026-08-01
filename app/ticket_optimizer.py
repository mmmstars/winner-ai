import math
import random


STRATEGY_VARIATION = {"בטוח": 0.05, "מאוזן": 0.16, "נועז": 0.30}
MINIMUM_DISTANCE = {"בטוח": 1, "מאוזן": 2, "נועז": 3}


def optimize(probability_rows: list[dict[str, float]], count: int, strategy: str, seed: int) -> list[tuple[str, ...]]:
    rng = random.Random(seed)
    variation = STRATEGY_VARIATION[strategy]
    minimum_distance = MINIMUM_DISTANCE[strategy]
    candidates = []
    attempts = max(500, count * 150)
    for _ in range(attempts):
        signature = tuple(select(row, variation, rng) for row in probability_rows)
        score = ticket_probability(signature, probability_rows)
        candidates.append((score, signature))
    base = tuple(max(row, key=row.get) for row in probability_rows)
    candidates.append((ticket_probability(base, probability_rows), base))
    candidates.sort(key=lambda item: item[0], reverse=True)
    selected = []
    for _, signature in candidates:
        if signature in selected:
            continue
        if selected and any(distance(signature, existing) < minimum_distance for existing in selected):
            continue
        selected.append(signature)
        if len(selected) == count:
            return selected
    for _, signature in candidates:
        if signature not in selected:
            selected.append(signature)
        if len(selected) == count:
            break
    return selected


def select(chances: dict[str, float], variation: float, rng: random.Random) -> str:
    ordered = sorted(chances, key=chances.get, reverse=True)
    lead = chances[ordered[0]] - chances[ordered[1]]
    if lead >= 0.20 or rng.random() > variation:
        return ordered[0]
    alternatives = ordered[1:]
    return rng.choices(alternatives, weights=[chances[key] for key in alternatives])[0]


def distance(first: tuple[str, ...], second: tuple[str, ...]) -> int:
    return sum(left != right for left, right in zip(first, second))


def ticket_probability(signature: tuple[str, ...], rows: list[dict[str, float]]) -> float:
    return sum(math.log(max(rows[index][selection], 1e-12)) for index, selection in enumerate(signature))
