#!/usr/bin/env python3
"""Compares the automatic price search (ADR-0022) between models on already recognized comics.

Runs inside the comic-helper pod (needs S3 and the Anthropic key), nothing is written back:
  kubectl -n comics exec -i deploy/comic-helper -- python - [max_comics] [model,model,...] [max_tokens] < scripts/preissuche-vergleich.py
Prices (USD per million tokens, search per call) as of 2026-11-03, see platform.claude.com pricing.
"""
import copy
import statistics
import sys

from comic_helper import app, marktpreis
from comic_helper.storage import AKTIV, EINGANG

PRICES = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.1, 0.5)}  # haiku: prompts up to 100k tokens
MODELS = {m: PRICES[m] for m in (sys.argv[2].split(",") if len(sys.argv) > 2 else ["claude-opus-5-5", "claude-sonnet-5-5"])}
SEARCH_USD = 0.01
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 10
MAX_TOKENS = int(sys.argv[3]) if len(sys.argv) > 3 else 4000

store, cfg, client = app.get_store(), app.get_cfg(), app.get_claude()
comics = []
for prefix in (EINGANG, AKTIV):
    for o in store.list_scans(prefix):
        sk = store.sidecar_key(prefix, o.copy_id)
        if store.exists(sk):
            v = store.read_json(sk).get("vorschlag")
            if v and v.get("titel") and v["titel"] != "-":
                comics.append((o.copy_id, v))
comics = comics[:LIMIT]


def cost(model, u):
    pin, pout = MODELS[model]
    return u["input_tokens"] / 1e6 * pin + u["output_tokens"] / 1e6 * pout + u["searches"] * SEARCH_USD


rows = {m: [] for m in MODELS}
print(f"{len(comics)} Comics")
for cid, v in comics:
    line = f"{v['titel'][:18]:18} #{str(v['ausgabe'])[:6]:6}"
    for model in MODELS:
        c = copy.deepcopy(cfg)
        c["marktpreis"]["modell"] = model
        c["marktpreis"]["max_tokens"] = MAX_TOKENS
        u = {}
        h = marktpreis.suggest(client, v, c, model, usage_out=u)
        u["usd"] = cost(model, u)
        u["median"] = h["basis_z1"] if h else None
        u["n"] = len(h["angebote"]) if h else 0
        rows[model].append(u)
        line += f" | {model.split('-')[1]:6} {('%.2f' % u['median']) if h else '  -  ':>6} n={u['n']} {u['seconds']:5.1f}s ${u['usd']:.3f}"
    print(line, flush=True)

print()
for model, us in rows.items():
    if not us:
        continue
    print(f"{model}: Ø {statistics.mean(u['seconds'] for u in us):.1f}s, Ø ${statistics.mean(u['usd'] for u in us):.3f}, "
          f"Ø {statistics.mean(u['input_tokens'] for u in us):.0f} in / {statistics.mean(u['output_tokens'] for u in us):.0f} out, "
          f"Ø {statistics.mean(u['searches'] for u in us):.1f} Suchen, Treffer bei {sum(1 for u in us if u['median'])}/{len(us)}")
names = list(rows)
for other in names[1:]:
    pairs = [(a["median"], b["median"]) for a, b in zip(rows[names[0]], rows[other]) if a["median"] and b["median"]]
    if pairs:
        dev = [abs(b - a) / a for a, b in pairs]
        print(f"Median-Abweichung {other} vs. {names[0]} bei {len(pairs)} Paaren: Ø {statistics.mean(dev):.0%}, max {max(dev):.0%}")
