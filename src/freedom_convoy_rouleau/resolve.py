"""Entity resolution and table building.

Turns per-page extraction files into the semantic-model tables:
movement, actor, location, protest_event, movement_phase, state_response,
plus relationship tables actor_event, event_location, event_timeline.

Resolution is deterministic: honorific-stripped name normalization + the
curated alias table. Every resolved entity keeps one row per supporting
citation in the *_citations companion tables, so merges stay auditable.
Events dedupe on (normalized title, date, first location).
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
import typer
import yaml

from .settings import ALIASES_PATH, EXTRACTIONS_DIR, QA_DIR, REPO_ROOT, TABLES_DIR

app = typer.Typer(help="Resolve entities and build semantic-model tables.")

GEO_PATH = REPO_ROOT / "config" / "rouleau_geo.yaml"

HONORIFICS = (
    "mr", "mrs", "ms", "dr", "chief", "interim chief", "deputy chief", "supt",
    "superintendent", "inspector", "insp", "sgt", "sergeant", "commissioner",
    "deputy commissioner", "mayor", "premier", "minister", "deputy prime minister",
    "prime minister", "president", "councillor", "justice", "the honourable",
)

PROVINCE_TO_ADM1 = {
    "AB": "CA01", "BC": "CA02", "MB": "CA03", "NB": "CA04", "NL": "CA05",
    "NS": "CA07", "ON": "CA08", "PE": "CA09", "QC": "CA10", "SK": "CA11",
    "YT": "CA12", "NT": "CA13", "NU": "CA14",
}

ACTOR_TYPE_TO_CAMEO = {
    "police": "COP", "government": "GOV", "protester": "OPP", "organizer": "OPP",
    "supporter": "CVL", "counter_protester": "CVL", "donor": "CVL",
    "platform": "BUS", "other": None,
}

# Phase boundaries are canonical report facts (convoy departure Jan 22,
# arrival in Ottawa Jan 28-29, Emergencies Act invocation Feb 14, revocation
# Feb 23). Citations are anchored to extracted events on the start date, so
# traceability is genuine rather than derived from noisy min/max member dates
# (Ch 5 background reaches back to 2018; post-hoc references reach into fall
# 2022).
PHASES = [
    {"phase_id": "buildup", "name": "Build-up", "phase_order": 1,
     "start_date": "2022-01-22", "end_date": "2022-01-28",
     "description": "Convoy organization and travel to protest sites, before sustained occupation"},
    {"phase_id": "occupation", "name": "Occupation", "phase_order": 2,
     "start_date": "2022-01-29", "end_date": "2022-02-13",
     "description": "Sustained occupation of Ottawa and border blockades, before the Emergencies Act"},
    {"phase_id": "state_response", "name": "State response", "phase_order": 3,
     "start_date": "2022-02-14", "end_date": "2022-02-23",
     "description": "From the Feb 14, 2022 Emergencies Act invocation through the Feb 23 revocation"},
    {"phase_id": "aftermath", "name": "Aftermath", "phase_order": 4,
     "start_date": "2022-02-23", "end_date": None,
     "description": "After the Feb 23, 2022 revocation of the declaration of emergency"},
]

MOVEMENT_START, MOVEMENT_END = "2022-01-22", "2022-02-23"


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug or "unknown"


def normalize_name(name: str) -> str:
    n = re.sub(r"\s+", " ", name).strip().lower().rstrip(".")
    n = re.sub(r"[’']s$", "", n)
    for h in sorted(HONORIFICS, key=len, reverse=True):
        if n.startswith(h + " "):
            n = n[len(h) + 1:]
    return n.strip()


def build_alias_map(section: dict) -> dict[str, str]:
    amap: dict[str, str] = {}
    for canonical, variants in (section or {}).items():
        amap[normalize_name(canonical)] = canonical
        for v in variants or []:
            amap[normalize_name(v)] = canonical
    return amap


def citation_of(rec: dict, row: dict) -> dict:
    return {
        "citation_volume": rec["citation_volume"],
        "citation_chapter": rec["citation_chapter"],
        "citation_printed_page": rec["citation_printed_page"],
        "citation_pdf_page": rec["citation_pdf_page"],
        "extraction_model": rec["extraction_model"],
        "extraction_run_id": rec["extraction_run_id"],
        "source_quote": row["source_quote"],
    }


def most_common(values: list) -> str | None:
    values = [v for v in values if v]
    return Counter(values).most_common(1)[0][0] if values else None


def best_date(row: dict) -> str | None:
    return row.get("event_date") or row.get("event_start_date")


@app.command()
def run() -> None:
    aliases = yaml.safe_load(ALIASES_PATH.read_text()) if ALIASES_PATH.exists() else {}
    actor_aliases = build_alias_map(aliases.get("actors"))
    location_aliases = build_alias_map(aliases.get("locations"))
    geo = (yaml.safe_load(GEO_PATH.read_text()) or {}).get("anchors", {})
    geo_by_norm = {normalize_name(k): dict(v, name=k) for k, v in geo.items()}

    # Drop records that failed citation verification — the tables must contain
    # only quote-verified facts. Requires `verify run` to have been run first.
    quarantine_path = QA_DIR / "quarantine.json"
    if not quarantine_path.exists():
        typer.echo("No quarantine.json — run `verify run` before resolving.", err=True)
        raise typer.Exit(code=1)
    quarantined = {
        (q["file"], q["table"], q["index"]) for q in json.loads(quarantine_path.read_text())
    }

    records = []
    dropped = 0
    for path in sorted(EXTRACTIONS_DIR.glob("*.json")):
        rec = json.loads(path.read_text())
        for table in rec["extraction"]:
            kept = [
                row
                for i, row in enumerate(rec["extraction"][table])
                if (path.name, table, i) not in quarantined
            ]
            dropped += len(rec["extraction"][table]) - len(kept)
            rec["extraction"][table] = kept
        records.append(rec)
    typer.echo(f"Excluded {dropped} quarantined records")
    if not records:
        typer.echo("No extraction files found.", err=True)
        raise typer.Exit(code=1)

    def canonical_actor(name: str) -> str:
        return actor_aliases.get(normalize_name(name), name.strip())

    def canonical_location(name: str) -> str:
        return location_aliases.get(normalize_name(name), name.strip())

    # ---- actors ----
    actor_mentions: dict[str, list[tuple[dict, dict]]] = defaultdict(list)
    for rec in records:
        for row in rec["extraction"]["actors"]:
            actor_mentions[canonical_actor(row["name"])].append((rec, row))

    actors, actor_citations = [], []
    for name, mentions in actor_mentions.items():
        actor_id = slugify(name)
        rows = [r for _, r in mentions]
        actor_type = most_common([r["actor_type"] for r in rows]) or "other"
        actors.append({
            "actor_id": actor_id,
            "name": name,
            "actor_type": actor_type,
            "actor_role": most_common([r.get("actor_role") for r in rows]),
            "affiliation": most_common([r.get("affiliation") for r in rows]),
            "jurisdiction": most_common([r.get("jurisdiction") for r in rows]),
            "gdelt_cameo_type": ACTOR_TYPE_TO_CAMEO.get(actor_type),
            "n_mentions": len(mentions),
            **citation_of(*mentions[0]),
        })
        actor_citations += [{"actor_id": actor_id, **citation_of(rec, row)} for rec, row in mentions]

    # ---- locations ----
    loc_mentions: dict[str, list[tuple[dict, dict]]] = defaultdict(list)
    for rec in records:
        for row in rec["extraction"]["locations"]:
            loc_mentions[canonical_location(row["name"])].append((rec, row))

    locations, location_citations = [], []
    for name, mentions in loc_mentions.items():
        location_id = slugify(name)
        rows = [r for _, r in mentions]
        anchor = geo_by_norm.get(normalize_name(name), {})
        province = anchor.get("province") or most_common([r.get("province") for r in rows])
        locations.append({
            "location_id": location_id,
            "name": name,
            "location_type": most_common([r.get("location_type") for r in rows]),
            "city": anchor.get("city") or most_common([r.get("city") for r in rows]),
            "province": province,
            "country": "Canada",
            "latitude": anchor.get("latitude"),
            "longitude": anchor.get("longitude"),
            "fips_country_code": "CA",
            "adm1_code": PROVINCE_TO_ADM1.get(province or ""),
            "n_mentions": len(mentions),
            **citation_of(*mentions[0]),
        })
        location_citations += [
            {"location_id": location_id, **citation_of(rec, row)} for rec, row in mentions
        ]

    # ---- events (dedupe on normalized title + date + first location) ----
    event_groups: dict[tuple, list[tuple[dict, dict]]] = defaultdict(list)
    for rec in records:
        for row in rec["extraction"]["events"]:
            first_loc = canonical_location(row["location_names"][0]) if row["location_names"] else ""
            key = (normalize_name(row["title"]), best_date(row), normalize_name(first_loc))
            event_groups[key].append((rec, row))

    events, event_citations, actor_event, event_location, event_timeline = [], [], [], [], []
    seen_event_ids: set[str] = set()
    for (_, date, _), mentions in event_groups.items():
        rec, row = mentions[0]
        base_id = slugify(f"{row['title']}_{date or 'undated'}")
        event_id, i = base_id, 1
        while event_id in seen_event_ids:
            i += 1
            event_id = f"{base_id}_{i}"
        seen_event_ids.add(event_id)

        loc_ids = []
        for _, r in mentions:
            for loc_name in r["location_names"]:
                lid = slugify(canonical_location(loc_name))
                if any(l["location_id"] == lid for l in locations) and lid not in loc_ids:
                    loc_ids.append(lid)
        events.append({
            "event_id": event_id,
            "title": row["title"],
            "description": row["description"],
            "event_type": most_common([r["event_type"] for _, r in mentions]),
            "event_date": most_common([r.get("event_date") for _, r in mentions]),
            "event_start_date": most_common([r.get("event_start_date") for _, r in mentions]),
            "event_end_date": most_common([r.get("event_end_date") for _, r in mentions]),
            "movement_phase_id": most_common([r["movement_phase"] for _, r in mentions]),
            "primary_location_id": loc_ids[0] if loc_ids else None,
            "is_state_response": any(r["is_state_response"] for _, r in mentions),
            **citation_of(rec, row),
        })
        event_citations += [{"event_id": event_id, **citation_of(m_rec, m_row)} for m_rec, m_row in mentions]

        for lid in loc_ids:
            event_location.append({"event_id": event_id, "location_id": lid, **citation_of(rec, row)})
        seen_ae = set()
        for m_rec, m_row in mentions:
            for inv in m_row["actor_involvements"]:
                aid = slugify(canonical_actor(inv["actor_name"]))
                ae_key = (aid, inv["involvement_role"])
                if any(a["actor_id"] == aid for a in actors) and ae_key not in seen_ae:
                    seen_ae.add(ae_key)
                    actor_event.append({
                        "actor_id": aid,
                        "event_id": event_id,
                        "involvement_role": inv["involvement_role"],
                        **citation_of(m_rec, m_row),
                    })
        if date:
            event_timeline.append({
                "event_id": event_id,
                "phase_id": most_common([r["movement_phase"] for _, r in mentions]),
                "sequence_date": date,
                **citation_of(rec, row),
            })

    # ---- state responses (dedupe on title + date) ----
    sr_groups: dict[tuple, list[tuple[dict, dict]]] = defaultdict(list)
    for rec in records:
        for row in rec["extraction"]["state_responses"]:
            sr_groups[(normalize_name(row["title"]), row.get("response_date"))].append((rec, row))

    state_responses, sr_citations = [], []
    seen_sr: set[str] = set()
    for (_, date), mentions in sr_groups.items():
        rec, row = mentions[0]
        base_id = slugify(f"{row['title']}_{date or 'undated'}")
        response_id, i = base_id, 1
        while response_id in seen_sr:
            i += 1
            response_id = f"{base_id}_{i}"
        seen_sr.add(response_id)
        responding = row.get("responding_actor_name")
        responding_id = slugify(canonical_actor(responding)) if responding else None
        if responding_id and not any(a["actor_id"] == responding_id for a in actors):
            responding_id = None
        state_responses.append({
            "response_id": response_id,
            "title": row["title"],
            "response_type": row["response_type"],
            "responding_actor_id": responding_id,
            "response_date": date,
            "legal_instrument": row.get("legal_instrument"),
            "description": row["description"],
            **citation_of(rec, row),
        })
        sr_citations += [{"response_id": response_id, **citation_of(m_rec, m_row)} for m_rec, m_row in mentions]

    # ---- movement + phases (canonical boundary dates; citations anchored to
    # an extracted event on the boundary date, so traceability is genuine) ----
    dated = [e for e in events if e["event_date"] or e["event_start_date"]]
    def edate(e): return e["event_date"] or e["event_start_date"]

    def citation_fields(event: dict) -> dict:
        return {k: event[k] for k in event
                if k.startswith(("citation_", "extraction_", "source_"))}

    def anchor_for(date: str, phase_id: str | None = None) -> dict | None:
        """Earliest-cited event on `date`, preferring the matching phase."""
        candidates = [e for e in dated if edate(e) == date]
        if not candidates:
            return None
        in_phase = [e for e in candidates if e["movement_phase_id"] == phase_id]
        pool = in_phase or candidates
        return min(pool, key=lambda e: (e["citation_volume"], e["citation_printed_page"]))

    movement_anchor = anchor_for(MOVEMENT_START) or min(
        dated, key=lambda e: (e["citation_volume"], e["citation_printed_page"])
    )
    movement = [{
        "movement_id": "freedom_convoy_2022",
        "name": "Freedom Convoy 2022",
        "description": "Protest movement against COVID-19 mandates: convoy to and occupation of "
                       "Ottawa, and border blockades, January-February 2022",
        "start_date": MOVEMENT_START,
        "end_date": MOVEMENT_END,
        "country": "Canada",
        **citation_fields(movement_anchor),
    }]

    movement_phases = []
    for phase in PHASES:
        anchor = anchor_for(phase["start_date"], phase["phase_id"])
        if anchor is None:  # fall back to the phase's earliest dated member
            members = [e for e in dated if e["movement_phase_id"] == phase["phase_id"]]
            anchor = min(members, key=edate, default=None)
        if anchor is None:
            continue
        movement_phases.append({**phase, **citation_fields(anchor)})

    # ---- write parquet ----
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    tables = {
        "movement": movement, "movement_phase": movement_phases, "actor": actors,
        "location": locations, "protest_event": events, "state_response": state_responses,
        "actor_event": actor_event, "event_location": event_location,
        "event_timeline": event_timeline, "actor_citations": actor_citations,
        "location_citations": location_citations, "event_citations": event_citations,
        "state_response_citations": sr_citations,
    }
    for name, rows in tables.items():
        df = pd.DataFrame(rows)
        for col in ("event_date", "event_start_date", "event_end_date", "response_date",
                    "sequence_date", "start_date", "end_date"):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
        df.to_parquet(TABLES_DIR / f"{name}.parquet", index=False)
        typer.echo(f"{name}: {len(df)} rows")


if __name__ == "__main__":
    app()
