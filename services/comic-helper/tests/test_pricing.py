from datetime import date

import pytest

from comic_helper import pricing
from comic_helper.config import load_pricing


@pytest.fixture(scope="module")
def cfg():
    return load_pricing()


def test_condition_factors_match_plan(cfg):
    assert {z: v["faktor"] for z, v in cfg["zustaende"].items()} == {0: 1.5, 1: 1.0, 2: 0.4, 3: 0.2, 4: 0.1}


@pytest.mark.parametrize(
    "value,expected",
    [
        (14.20, 13.99),
        (14.30, 14.50),
        (14.74, 14.50),
        (14.75, 14.99),
        (15.30, 15.50),
        (0.40, 2.50),   # minimum price 2.00 -> nearest ending above it
        (2.00, 2.50),
    ],
)
def test_round_nearest(cfg, value, expected):
    assert pricing.round_shop_price(value, cfg) == expected


def test_round_up_mode(cfg):
    up = {**cfg, "rundung": {**cfg["rundung"], "modus": "aufrunden"}}
    assert pricing.round_shop_price(14.20, up) == 14.50
    assert pricing.round_shop_price(14.51, up) == 14.99
    assert pricing.round_shop_price(14.995, up) == 15.50


def test_calculate_example(cfg):
    # Comicguide Z1 = 10 EUR, condition 2 (40 %), markup 1.5 -> 6.00 -> 5.99
    r = pricing.calculate(10.0, 2, "comicguide", cfg)
    assert (r.roh, r.final, r.faktor, r.aufschlag) == (6.0, 5.99, 0.4, 1.5)


def test_condition_zero_is_premium(cfg):
    assert pricing.calculate(20.0, 0, "katalog", cfg).roh == 45.0


def test_cover_price_rule(cfg):
    assert pricing.base_from_cover_price(6.99, cfg) == 4.66
    today = date(2026, 10, 27)
    assert pricing.cover_rule_applies("EUR", 2025, cfg, today)
    assert not pricing.cover_rule_applies("EUR", 2019, cfg, today)
    assert not pricing.cover_rule_applies("DEM", 2025, cfg, today)
    assert not pricing.cover_rule_applies(None, 2025, cfg, today)
    assert not pricing.cover_rule_applies("EUR", None, cfg, today)


@pytest.mark.parametrize("bad", [dict(basis_z1=0, zustand=1, quelle="comicguide"),
                                 dict(basis_z1=5, zustand=5, quelle="comicguide"),
                                 dict(basis_z1=5, zustand=1, quelle="ebay")])
def test_invalid_input(cfg, bad):
    with pytest.raises(ValueError):
        pricing.calculate(cfg=cfg, **bad)


def test_condition_label(cfg):
    assert pricing.condition_label(1, cfg) == "1 – sehr gut"


def test_booklooker_offer_has_no_markup(cfg):
    # PoC (ADR-0017): Booklooker offer is already a retail price
    assert cfg["standard_preisquelle"] == "booklooker"
    r = pricing.calculate(4.50, 1, "booklooker", cfg)
    assert (r.aufschlag, r.final) == (1.0, 4.50)
    assert pricing.calculate(4.50, 1, "comicguide", cfg).aufschlag == 1.5
