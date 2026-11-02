"""Price calculation following Sepp's practice (docs/PREISFINDUNG.md).

    base (condition 1) = Comicguide price Z1, Booklooker offer (PoC, ADR-0017),
                         or cover price x 2/3 for titles still in print
    price              = base x condition factor x markup (per source), rounded to shop price endings

The review UI repeats this formula in JavaScript for the live preview; this module is
authoritative and recalculates on submit. Keep both in sync (tests/test_pricing.py).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class PriceResult:
    basis_z1: float
    quelle: str
    zustand: int
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


def calculate(basis_z1: float, zustand: int, quelle: str, cfg: dict) -> PriceResult:
    if quelle not in cfg["preisquellen"]:
        raise ValueError(f"unknown price source {quelle!r}")
    if zustand not in cfg["zustaende"]:
        raise ValueError(f"unknown condition {zustand!r}")
    if basis_z1 <= 0:
        raise ValueError("base price must be positive")
    faktor = float(cfg["zustaende"][zustand]["faktor"])
    aufschlag = markup_for(quelle, cfg)
    roh = basis_z1 * faktor * aufschlag
    return PriceResult(
        basis_z1=_money(basis_z1),
        quelle=quelle,
        zustand=zustand,
        faktor=faktor,
        aufschlag=aufschlag,
        roh=_money(roh),
        final=round_shop_price(roh, cfg),
    )


def condition_label(zustand: int, cfg: dict) -> str:
    """Shop option value, e.g. '1 – sehr gut'."""
    return f"{zustand} – {cfg['zustaende'][zustand]['bezeichnung']}"
