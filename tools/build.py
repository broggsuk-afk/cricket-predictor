#!/usr/bin/env python3
"""Build and check the Predictor data.

Reads the source files in data/ and writes data/index.json, the single file
the website loads (plus data.json at the root for older copies of the site).

    python3 tools/build.py          check everything and build
    python3 tools/build.py --lock   first lock picks for matches that have started, then build

Exits with status 1 and a list of problems if anything is wrong, so nothing
broken gets published.
"""
import glob
import json
import math
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

# Allowed labels. Add to these lists as the site grows (e.g. a new sport).
SPORTS = {"cricket"}
CATEGORIES = {"men", "women", "youth"}
LEVELS = {"international", "franchise", "domestic", "club", "school"}
TIERS = {"full", "associate", None}
MODELS = {"full", "lite", "ratings"}
STATUSES = {"upcoming", "live", "completed", "abandoned"}
TEAM_TYPES = {"national", "franchise", "domestic", "club", "school"}

K = 0.1              # factor model steepness
ELO_SCALE = 400      # ratings model
DEFAULT_HOME = 50    # ratings points for playing at home


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as fh:
        return json.load(fh)


def save(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def parse_date(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def predict(fx, ratings):
    """Return (pa, pb, pd) as whole percentages."""
    d = (fx.get("drawPct") or 0) / 100
    if fx["model"] == "ratings":
        ra = fx.get("ratings", {}).get("A", ratings.get(fx["teamA"]))
        rb = fx.get("ratings", {}).get("B", ratings.get(fx["teamB"]))
        home = 0 if fx.get("neutral") else fx.get("homeAdvantage", DEFAULT_HOME)
        p = 1 / (1 + 10 ** (-(ra + home - rb) / ELO_SCALE))
    else:
        score = sum(f["w"] * f["v"] for f in fx["factors"])
        p = 1 / (1 + math.exp(-K * score))
    pa = round(p * (1 - d) * 100)
    pd = round(d * 100)
    return pa, 100 - pa - pd, pd


def main():
    lock = "--lock" in sys.argv
    errors, warnings = [], []

    comps = {c["id"]: c for c in load("competitions.json")["competitions"]}
    teams = {t["id"]: t for t in load("teams.json")["teams"]}
    people = {p["id"]: p for p in load("people.json")["people"]}
    venues = {v["id"]: v for v in load("venues.json")["venues"]}
    ratings = load("ratings.json").get("ratings", {})
    meta = load("meta.json")

    for c in comps.values():
        where = f"competition {c['id']}"
        if c.get("sport") not in SPORTS: errors.append(f"{where}: unknown sport {c.get('sport')!r}")
        if c.get("category") not in CATEGORIES: errors.append(f"{where}: unknown category {c.get('category')!r}")
        if c.get("level") not in LEVELS: errors.append(f"{where}: unknown level {c.get('level')!r}")
        if c.get("tier") not in TIERS: errors.append(f"{where}: unknown tier {c.get('tier')!r}")
        if c.get("model") not in MODELS: errors.append(f"{where}: unknown model {c.get('model')!r}")
    for t in teams.values():
        if t.get("type") not in TEAM_TYPES: errors.append(f"team {t['id']}: unknown type {t.get('type')!r}")
        if t.get("category") not in CATEGORIES: errors.append(f"team {t['id']}: unknown category {t.get('category')!r}")

    now = datetime.now(timezone.utc)
    out_fixtures, seen = [], set()
    for path in sorted(glob.glob(os.path.join(DATA, "fixtures", "*.json"))):
        doc = json.load(open(path, encoding="utf-8"))
        cid = doc.get("competition")
        fname = os.path.basename(path)
        if cid not in comps:
            errors.append(f"{fname}: competition {cid!r} is not in competitions.json")
            continue
        comp = comps[cid]
        changed = False
        for fx in doc.get("fixtures", []):
            where = f"{fname} / {fx.get('id')}"
            if fx.get("id") in seen: errors.append(f"{where}: duplicate fixture id")
            seen.add(fx.get("id"))
            if fx.get("competition", cid) != cid: errors.append(f"{where}: competition does not match file")
            fx.setdefault("model", comp["model"])
            if fx["model"] not in MODELS: errors.append(f"{where}: unknown model {fx['model']!r}")
            if fx.get("status") not in STATUSES: errors.append(f"{where}: unknown status {fx.get('status')!r}")
            for side in ("teamA", "teamB"):
                if fx.get(side) not in teams: errors.append(f"{where}: {side} {fx.get(side)!r} is not in teams.json")
            if fx.get("venue") and fx["venue"] not in venues: errors.append(f"{where}: venue {fx['venue']!r} is not in venues.json")
            try:
                start = parse_date(fx["date"])
                if start.tzinfo is None: errors.append(f"{where}: date needs a time zone, e.g. 2026-10-01T09:00:00Z")
            except Exception:
                errors.append(f"{where}: bad date {fx.get('date')!r}"); start = None
            if fx["model"] in ("full", "lite"):
                fl = fx.get("factors") or []
                if not fl: errors.append(f"{where}: {fx['model']} model needs factors")
                for f in fl:
                    v, w = f.get("v"), f.get("w")
                    if not isinstance(v, (int, float)) or v < -5 or v > 5 or (v * 2) % 1:
                        errors.append(f"{where}: factor {f.get('id')} value {v!r} must be -5..5 in steps of 0.5")
                    if not isinstance(w, (int, float)) or w <= 0:
                        errors.append(f"{where}: factor {f.get('id')} weight {w!r} must be positive")
            else:
                for side, key in (("A", "teamA"), ("B", "teamB")):
                    if fx.get("ratings", {}).get(side) is None and fx.get(key) not in ratings:
                        errors.append(f"{where}: ratings model needs a rating for {fx.get(key)}")
            for group in ("players", "leaders"):
                for p in fx.get(group, []):
                    if p.get("person") not in people: errors.append(f"{where}: {group} person {p.get('person')!r} is not in people.json")
                    if p.get("team") not in ("A", "B"): errors.append(f"{where}: {group} {p.get('person')} team must be 'A' or 'B'")
            names = {teams.get(fx.get("teamA"), {}).get("name"), teams.get(fx.get("teamB"), {}).get("name"), "Draw", "No result", "Tie"}
            if fx.get("result") and fx["result"].get("winner") not in names:
                errors.append(f"{where}: result winner {fx['result'].get('winner')!r} must be a team name, Draw, Tie or No result")
            if errors:
                continue
            pa, pb, pd = predict(fx, ratings)
            if lock and start and start <= now and "predictedWinner" not in fx:
                fx["predictedWinner"] = teams[fx["teamA"]]["name"] if pa >= pb else teams[fx["teamB"]]["name"]
                fx["predictedPct"] = max(pa, pb)
                changed = True
                print(f"locked {fx['id']}: {fx['predictedWinner']} {fx['predictedPct']}%")
            if start and start <= now and fx.get("status") == "upcoming" and "predictedWinner" not in fx:
                warnings.append(f"{where}: has started but its pick is not locked (run with --lock)")
            # flattened copy for the website
            flat = {k: v for k, v in fx.items() if k not in ("players", "leaders")}
            ta, tb, ve = teams[fx["teamA"]], teams[fx["teamB"]], venues.get(fx.get("venue"), {})
            flat.update({
                "competition": cid, "series": comp["name"], "sport": comp["sport"], "category": comp["category"],
                "level": comp["level"], "tier": comp.get("tier"),
                "teamAId": ta["id"], "teamBId": tb["id"], "teamA": ta["name"], "teamB": tb["name"],
                "teamAShort": ta.get("short", ""), "teamBShort": tb.get("short", ""),
                "venue": ", ".join(x for x in (ve.get("name"), ve.get("city")) if x),
                "prediction": {"A": pa, "B": pb, "draw": pd},
            })
            if fx["model"] == "ratings":
                flat["ratingA"] = fx.get("ratings", {}).get("A", ratings.get(fx["teamA"]))
                flat["ratingB"] = fx.get("ratings", {}).get("B", ratings.get(fx["teamB"]))
            for group in ("players", "leaders"):
                flat[group] = []
                for p in fx.get(group, []):
                    person = people[p["person"]]
                    item = {k: v for k, v in p.items() if k != "displayName"}
                    item["name"] = p.get("displayName") or person["name"]
                    if person.get("wiki"): item["wiki"] = person["wiki"]
                    if person.get("minor"): item["minor"] = True
                    flat[group].append(item)
            out_fixtures.append(flat)
        if changed:
            save(path, doc)

    if errors:
        print("PROBLEMS FOUND - nothing was built:")
        for e in errors: print("  -", e)
        sys.exit(1)

    out_fixtures.sort(key=lambda f: f["date"])
    sections = {}
    for f in out_fixtures:
        key = (f["sport"], f["category"], f["level"], f.get("tier"))
        s = sections.setdefault(key, {"sport": key[0], "category": key[1], "level": key[2], "tier": key[3], "upcoming": 0, "completed": 0})
        s["completed" if f["status"] == "completed" else "upcoming"] += 1
    index = {
        "meta": meta,
        "builtAt": now.isoformat(timespec="seconds"),
        "sections": list(sections.values()),
        "competitions": [c for c in comps.values() if c.get("active", True)],
        "fixtures": out_fixtures,
    }
    save(os.path.join(DATA, "index.json"), index)
    save(os.path.join(ROOT, "data.json"), index)  # for copies of the site that still read data.json
    for w in warnings: print("warning:", w)
    print(f"built data/index.json: {len(out_fixtures)} fixtures in {len(sections)} section(s), {len(comps)} competitions, {len(teams)} teams, {len(people)} people")


if __name__ == "__main__":
    main()
