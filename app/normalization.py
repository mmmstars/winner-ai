"""Conservative team matching: aliases first, fuzzy matching only above a safe threshold."""

import re
import unicodedata
from difflib import SequenceMatcher


STOP_WORDS = {"fc", "cf", "sc", "club", "football", "מועדון", "כדורגל"}


def normalized_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).casefold().replace("׳", "'").replace("״", '"')
    value = "".join(character for character in value if not unicodedata.combining(character))
    words = re.findall(r"[\w'\"]+", value, flags=re.UNICODE)
    return " ".join(word for word in words if word not in STOP_WORDS)


def match_team(name: str, aliases: dict[str, str], threshold: float = .88) -> tuple[str | None, float]:
    query = normalized_name(name)
    exact = {normalized_name(alias): canonical for alias, canonical in aliases.items()}
    if query in exact:
        return exact[query], 1.0
    ranked = sorted(
        ((SequenceMatcher(None, query, candidate).ratio(), canonical) for candidate, canonical in exact.items()),
        reverse=True,
    )
    if not ranked or ranked[0][0] < threshold:
        return None, ranked[0][0] if ranked else 0.0
    if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < .04:
        return None, ranked[0][0]
    return ranked[0][1], ranked[0][0]

