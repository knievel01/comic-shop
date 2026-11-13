"""Price calculation following Sepp's practice (docs/PREISFINDUNG.md).

    base (condition 1) = Comicguide price Z1, Booklooker offer (PoC, ADR-0011),
                         or cover price x 2/3 for titles still in print
    price              = base x condition factor x markup (per source), rounded to shop price endings

Lots (ADR-0012): several identical copies sold as one variant with a condition range, e.g. 1-3. The
factor is combined from the factors of all conditions in the range (config sammelposten.preisregel).

The review UI repeats this formula in JavaScript for the live preview; this module is
authoritative and recalculates on submit. Keep both in sync (tests/test_pricing.py).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class PriceResult:
    basis_z1: float
    quelle: str
    zustand: int | list[int]   # list for a lot with a condition range (ADR-0012)
    faktor: float
    aufschlag: float
    roh: float
    final: float

    def as_dict(self) -> dict:
        return asdict(self)


def _money(x: float) -> float:
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def round_shop_price(value: float, cfg: dict) -> float:
    """Round to the nearest (or next higher) price with an allowed ending, e.g. x.50 / x.99."""
    r = cfg["rundung"]
    endings = sorted(float(e) for e in r["endungen"])
    minimum = float(r.get("mindestpreis", 0))
    value = max(value, minimum)
    whole = math.floor(value)
    candidates = [whole - 1 + e for e in endings] + [whole + e for e in endings] + [whole + 1 + e for e in endings]
    candidates = [c for c in candidates if c >= minimum - 1e-9]
    if r.get("modus", "naechste") == "aufrunden":
        best = min(c for c in candidates if c >= value - 1e-9)
    else:
        # nearest; ties go up (in Sepp's favour)
        best = min(candidates, key=lambda c: (abs(c - value), -c))
    return _money(best)


def base_from_cover_price(cover_price: float, cfg: dict) -> float:
    return _money(cover_price * float(cfg["coverpreis"]["faktor"]))


def cover_rule_applies(currency: str | None, year: int | None, cfg: dict, today: date | None = None) -> bool:
    """Cover-price rule only for current Euro titles (old DM prices must never be used)."""
    rule = cfg["coverpreis"]
    if not currency or currency.upper() != rule["waehrung"].upper() or not year:
        return False
    today = today or date.today()
    return today.year - int(year) <= int(rule["max_alter_jahre"])


def markup_for(quelle: str, cfg: dict) -> float:
    return float((cfg.get("aufschlag_je_quelle") or {}).get(quelle, cfg["aufschlag"]))


def condition_range(zustaende: Sequence[int], cfg: dict) -> list[int]:
    """Sorted, gap-free range: a lot with conditions 1 and 3 also contains 2 (ADR-0012)."""
    if not zustaende:
        raise ValueError("no condition selected")
    for z in zustaende:
        if z not in cfg["zustaende"]:
            raise ValueError(f"unknown condition {z!r}")
    return list(range(min(zustaende), max(zustaende) + 1))


def combined_factor(zustaende: Sequence[int], cfg: dict) -> float:
    factors = [float(cfg["zustaende"][z]["faktor"]) for z in zustaende]
    rule = (cfg.get("sammelposten") or {}).get("preisregel", "mittelwert")
    if rule == "mittelwert":
        return round(sum(factors) / len(factors), 4)
    if rule == "schlechtester":
        return min(factors)
    if rule == "bester":
        return max(factors)
    raise ValueError(f"unknown sammelposten.preisregel {rule!r}")


def calculate(basis_z1: float, zustand: int | Sequence[int], quelle: str, cfg: dict) -> PriceResult:
    if quelle not in cfg["preisquellen"]:
        raise ValueError(f"unknown price source {quelle!r}")
    zustaende = condition_range([zustand] if isinstance(zustand, int) else zustand, cfg)
    if basis_z1 <= 0:
        raise ValueError("base price must be positive")
    faktor = combined_factor(zustaende, cfg)
    aufschlag = markup_for(quelle, cfg)
    roh = basis_z1 * faktor * aufschlag
    return PriceResult(
        basis_z1=_money(basis_z1),
        quelle=quelle,
        zustand=zustaende[0] if len(zustaende) == 1 else zustaende,
        faktor=faktor,
        aufschlag=aufschlag,
        roh=_money(roh),
        final=round_shop_price(roh, cfg),
    )


def condition_label(zustand: int, cfg: dict) -> str:
    """Shop option value, e.g. '1 – sehr gut'."""
    return f"{zustand} – {cfg['zustaende'][zustand]['bezeichnung']}"


def condition_text(zustaende: Sequence[int]) -> str:
    """'2' or '1–3' for UI and shop texts."""
    lo, hi = min(zustaende), max(zustaende)
    return str(lo) if lo == hi else f"{lo}–{hi}"


def condition_key(zustaende: Sequence[int]) -> str:
    """ASCII form for SKUs and S3 metadata: '2' or '1-3'."""
    return condition_text(zustaende).replace("–", "-")


def lot_label(zustaende: Sequence[int]) -> str:
    """Shop option value of a lot (ADR-0012), e.g. 'Sammelposten · Zustand 1–3'."""
    return f"Sammelposten · Zustand {condition_text(zustaende)}"


def lot_range_words(zustaende: Sequence[int], cfg: dict) -> str:
    """'Zustand 1 bis 3 (sehr gut bis noch sammelwürdig)' or 'Zustand 2 (gut)' for the shop description."""
    lo, hi = min(zustaende), max(zustaende)
    name = lambda z: cfg["zustaende"][z]["bezeichnung"]  # noqa: E731
    if lo == hi:
        return f"Zustand {lo} ({name(lo)})"
    return f"Zustand {lo} bis {hi} ({name(lo)} bis {name(hi)})"
