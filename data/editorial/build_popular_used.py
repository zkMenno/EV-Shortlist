"""Build data/editorial/popular_used.yaml (T-131): the landing's "Popular used EVs".

Generation level. Candidates come from Menno's own list of EV generations (the `eras` tab
in menno-picks.yaml, Decision 038), limited to eras already on the used market. Each row is
scored with two plain signals whose weights live in `METHOD` below and are written into the
output file, so the order is explainable:

  registrations: the model's rank in data/seed/top40.yaml (NL: RDW cars by year of first
                 admission 2018-2024; UK: DfT whole licensed BEV fleet, no year split).
                 Rank 1 = 40 points, rank 40 = 1 point.
  owner:         Menno's verdict for that generation (shortlist / consider / unrated /
                 ruled_out) plus a bonus for his favourites.

A generation is kept when it has registration points or a positive owner verdict; unrated
generations of models outside the top 40 are dropped (neither popular nor picked).

Usage (from the repo root):
  python3 -I data/editorial/build_popular_used.py           # write popular_used.yaml
  python3 -I data/editorial/build_popular_used.py --check   # exit 1 if stale or ids unknown
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
PICKS = ROOT / "data/editorial/menno-picks.yaml"
TOP40 = ROOT / "data/seed/top40.yaml"
MODELS = ROOT / "data/seed/models.yaml"
OUT = ROOT / "data/editorial/popular_used.yaml"

METHOD: dict[str, Any] = {
    "used_eras": ["2019-2021", "2021-2022", "2022-2024", "2024-2026"],
    "registration_top": 40,
    "registration_points": "41 - top40 rank (rank 1 = 40 points); 0 outside the top 40",
    "owner_points": {"shortlist": 20, "consider": 10, "unrated": 0, "ruled_out": -10},
    "favourite_bonus": 5,
    "keep_if": "registration points > 0, or owner verdict shortlist / consider",
    "tie_break": "more registration points, then newer generation start year, then generation id",
    "landing_count": 12,
}

# T-169: "the owner" read as the car's previous owner, so the lines say "the site owner".
VERDICT_TEXT = {
    "shortlist": "on the site owner's shortlist",
    "consider": "the site owner would consider it",
    "unrated": None,
    "ruled_out": "the site owner ruled it out",
}


def _generations() -> dict[str, dict[str, Any]]:
    seed = yaml.safe_load(MODELS.read_text())
    out: dict[str, dict[str, Any]] = {}
    for make in seed["makes"]:
        for model in make["models"]:
            for gen in model.get("generations", []):
                out[gen["id"]] = {
                    "model_id": model["id"],
                    "model_name": model["name"],
                    "make": make["name"],
                    "model": model["name"],
                    "generation": gen["name"],
                    "years": gen.get("years"),
                }
    return out


def display_name(make: str, model: str, generation: str) -> str:
    """'Polestar 2', 'Nissan Leaf ZE1', 'Kia e-Niro (Gen 1, DE)': never the make or model twice."""
    base = model if model.lower().startswith(make.lower()) else f"{make} {model}"
    if generation.lower().startswith(model.lower()):
        rest = generation[len(model) :].strip()
        return f"{base} {rest}".strip()
    first, *rest = generation.split()
    for w in model.split():
        if w.lower() in first.lower() and first.lower() != w.lower():
            return f"{make} {generation}"  # 'e-Niro (Gen 1, DE)' names the model better
        if first.lower() in w.lower():
            return f"{base} {' '.join(rest)}".strip()  # 'Corsa-e' + 'Corsa F' -> 'Corsa-e F'
    return f"{base} {generation}"


def build() -> dict[str, Any]:
    picks = yaml.safe_load(PICKS.read_text())
    top40 = yaml.safe_load(TOP40.read_text())
    gens = _generations()
    rank = {m["model_id"]: m["rank"] for m in top40["models"]}

    rows: dict[str, dict[str, Any]] = {}
    for e in picks["eras"]:
        gid = e.get("seed_generation_id")
        if e["era"] not in METHOD["used_eras"] or not gid:
            continue
        if gid not in gens:
            raise SystemExit(f"unknown generation id in menno-picks eras: {gid}")
        g = gens[gid]
        verdict = e.get("verdict") or "unrated"
        prev = rows.get(gid)
        # The eras tab can list one generation twice (Enyaq, Enyaq Coupe): keep the better one.
        pts_of = METHOD["owner_points"]
        if prev and pts_of[prev["owner"]["verdict"]] >= pts_of[verdict]:
            prev["owner"]["sheet_names"].append(f"{e['make']} {e['model']}")
            prev["owner"]["favourite"] = prev["owner"]["favourite"] or bool(e.get("favourite"))
            continue
        r = rank.get(g["model_id"])
        carried = prev["owner"]["sheet_names"] if prev else []
        rows[gid] = {
            "generation_id": gid,
            "model_id": g["model_id"],
            "name": display_name(g["make"], g["model_name"], g["generation"]),
            "registrations": {"top40_rank": r, "points": (METHOD["registration_top"] + 1 - r) if r else 0},
            "owner": {
                "verdict": verdict,
                "favourite": bool(e.get("favourite")) or bool(prev and prev["owner"]["favourite"]),
                "era": e["era"],
                "sheet_names": carried + [f"{e['make']} {e['model']}"],
                "remark": e.get("remark") or None,
            },
            "_start": (g["years"] or [0])[0],
        }

    kept = []
    for row in rows.values():
        o = row["owner"]
        pts = row["registrations"]["points"] + METHOD["owner_points"][o["verdict"]]
        pts += METHOD["favourite_bonus"] if o["favourite"] else 0
        if row["registrations"]["points"] == 0 and o["verdict"] not in ("shortlist", "consider"):
            continue
        row["points"] = pts
        kept.append(row)
    kept.sort(
        key=lambda x: (
            -x["points"],
            -x["registrations"]["points"],
            -x["_start"],
            x["generation_id"],
        )
    )

    out_rows = []
    for i, row in enumerate(kept, 1):
        why = []
        r = row["registrations"]["top40_rank"]
        if r:
            why.append(f"#{r} most registered EV model (NL + UK fleets)")
        vt = VERDICT_TEXT[row["owner"]["verdict"]]
        if vt:
            why.append(vt + (" (a favourite)" if row["owner"]["favourite"] else ""))
        elif row["owner"]["favourite"]:
            why.append("one of the site owner's favourites")
        if row["owner"]["verdict"] == "ruled_out" and row["owner"]["remark"]:
            rem = row["owner"]["remark"]
            why[-1] += f": {rem[0].lower()}{rem[1:]}"
        text = "; ".join(why)
        row["why"] = text[0].upper() + text[1:] + "."
        del row["_start"]
        out_rows.append({"order": i, **row})

    return {
        "schema": "editorial-popular-used/v1",
        "generated_by": "data/editorial/build_popular_used.py (T-131)",
        "inputs": {
            "picks": f"data/editorial/menno-picks.yaml (eras, {picks['source']['imported']})",
            "registrations": f"data/seed/top40.yaml (generated {top40['generated_on']})",
            "upstream_licences": {
                "rdw": "CC0-1.0 (RDW open data, NL)",
                "dft-veh": "OGL-UK-3.0 (DfT VEH0120, UK; whole licensed fleet, not only used cars)",
            },
        },
        # Credit lines to show wherever this list is shown (#128 follow-up). RDW: Decision 037
        # (no RDW logo or house style until RDW answers Q-037). DfT: the OGL v3 statement that
        # data/sources.yaml (dft-veh `terms`) requires.
        "attribution": [
            {
                "source": "rdw",
                "text": "Dutch open vehicle register (opendata.rdw.nl), CC0",
                "url": "https://opendata.rdw.nl",
                "basis": "Decision 037",
            },
            {
                "source": "dft-veh",
                "text": (
                    "Contains public sector information licensed under the Open Government "
                    "Licence v3.0."
                ),
                "url": (
                    "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"
                ),
                "basis": "OGL-UK-3.0 (data/sources.yaml dft-veh terms)",
            },
        ],
        "licence": (
            "CC-BY-4.0 (order and 'why' are ours; owner verdicts are Menno's opinion: label them)"
        ),
        "notes": [
            (
                "Registration ranks are per MODEL (top40.yaml has no generation split), so two "
                "generations of one model share the same rank; the owner verdict separates them."
            ),
            "Edit the weights in METHOD (build_popular_used.py) and re-run; never edit rows.",
        ],
        "method": METHOD,
        "generations": out_rows,
    }


def main() -> int:
    data = build()
    header = "# GENERATED by data/editorial/build_popular_used.py. Do not edit by hand.\n"
    text = header + yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=110)
    if "--check" in sys.argv:
        if not OUT.exists() or OUT.read_text() != text:
            print("popular_used.yaml is stale: run python3 -I data/editorial/build_popular_used.py")
            return 1
        print(f"popular_used.yaml up to date ({len(data['generations'])} generations)")
        return 0
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(data['generations'])} generations")
    for g in data["generations"]:
        print(f"{g['order']:>3} {g['points']:>3} {g['generation_id']:<34} {g['why']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
