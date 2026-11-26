"""Licence gate (Decision 009): which sources may reach a public release.

Fails closed (T-006 review):
- No data/sources.yaml -> the release FAILS (`ReleaseError` in build_release); nothing is
  released on the strength of a missing registry.
- A source is releasable only when the registry lists it with `status: active` (or
  `active_pending_confirmation`, Decision 037) AND either a
  named, confirmed licence or `permission: written` (explicit written permission, logged).
- A licence that is empty, "none", "unknown", "n/a" or still marked "(to confirm)" is not a
  named licence. That matches data/sources.yaml: "(to confirm)" licences stay blocked until
  checked. `permission: written` is the only override; no source sets it tonight.
- `use: cited-facts` + a logged owner `decision` (Decision 068): an `active` source of single
  facts cited one by one from maker documents (URL, date, confidence) ships without a named
  licence. Its `cited_hosts` lists the maker hosts a fact may cite (manual/facts.py checks
  every fact); third-party pages go to a blocked source instead. The CC BY open-data bundle
  still needs a named licence (opendata/bundle.py), so these facts never enter it.
- `nyland` is always excluded (matcher.EXCLUDED_SOURCES), whatever the registry says.
- `aliases` (Q-075): a source may list other ids it is known by (e.g. `bnetza` carries
  `bnetza-ladesaeulenregister`, the id the charging taxonomies use). An alias is gated exactly
  like its registry entry; an alias that clashes with another entry or alias is ignored.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse, urlsplit

import yaml

from ev_pipeline.match.matcher import EXCLUDED_SOURCES

_NO_LICENCE = {"", "none", "unknown", "n/a"}
# Statuses that may reach a release. `active_pending_confirmation` (Decision 037): in use
# now, credited, reuse terms being confirmed in writing; a "no" removes it next release.
RELEASABLE_STATUSES = frozenset({"active", "active_pending_confirmation"})
WRITTEN_PERMISSION = "written"
AGGREGATES_ONLY = "aggregates-only"
CITED_FACTS = "cited-facts"
MISSING_REGISTRY = "no data/sources.yaml (licence registry missing; release blocked)"


def url_matches(pattern: str, url: str) -> bool:
    """True when `url` is on `pattern`: a bare host (`www.audi.com`, `*.example.com`) matches
    that host; `host/path/` matches URLs under that path, segment by segment, where a `*`
    segment stands for exactly one path segment (`www.louwman.nl/uploads/*/Peugeot/`)."""
    parts = urlparse(url.strip())
    host = (parts.hostname or "").lower()
    pat_host, _, pat_path = pattern.strip().partition("/")
    if not fnmatch.fnmatchcase(host, pat_host.lower()):  # hosts ignore case; paths don't
        return False
    want = [seg for seg in pat_path.split("/") if seg]
    have = [unquote(seg) for seg in parts.path.split("/") if seg]
    if want and any(h in (".", "..") or "/" in h or "\\" in h for h in have):
        return False  # a dot segment or encoded slash could step out of the allowed prefix
    if len(have) < len(want):
        return False
    return all(
        fnmatch.fnmatchcase(h, w) if w == "*" else h == w for h, w in zip(have, want, strict=False)
    )


@dataclass
class SourceEntry:
    id: str
    name: str
    licence: str
    status: str
    owner: str = ""
    terms: str = ""
    permission: str = ""  # "written" = explicit written permission from the owner
    # T-111 (A-35 S2): `use: aggregates-only` + `decision`: the owner accepted, in a logged
    # decision, that we derive our own aggregates from the site (Decision 060). Its values
    # never ship; only figures we compute from them may, and only through derive/used_price.
    use: str = ""
    decision: str = ""
    # Sites a hand-noted aggregate may cite as its URL (not the fetch allowlist `hosts`).
    site_hosts: tuple[str, ...] = ()
    # Decision 068 (`use: cited-facts`): the maker hosts a cited fact's URL may be on.
    cited_hosts: tuple[str, ...] = ()
    # `access` (api | bulk | manual | ...) and the fetch allowlist `hosts`: manual/facts.py
    # lets a hand-entered fact name a non-manual source only when its URL is on these hosts.
    access: str = ""
    hosts: tuple[str, ...] = ()
    # Host/path prefixes a hand-entered fact naming this source may cite (PR #80 round 2):
    # for sources on a shared host (github.com), the source's own `<owner>/<repo>/` path.
    cite_paths: tuple[str, ...] = ()


def licence_problem(licence: str) -> str | None:
    """None when `licence` names a confirmed licence, else why not."""
    text = licence.strip().lower()
    base = text.split("(")[0].strip()
    if base in _NO_LICENCE or base.startswith(("unknown", "none")) or "no licence" in text:
        return f"no named licence ({licence})"
    if "to confirm" in text or "unconfirmed" in text:
        return f"licence not confirmed ({licence})"
    return None


@dataclass
class Registry:
    sources: dict[str, SourceEntry] = field(default_factory=dict)
    loaded: bool = False
    aliases: dict[str, str] = field(default_factory=dict)  # alias id -> registry id

    def canonical(self, source_id: str) -> str:
        """The registry id for `source_id` (itself unless it is a known alias)."""
        return source_id if source_id in self.sources else self.aliases.get(source_id, source_id)

    def reason_blocked(self, source_id: str) -> str | None:
        """None when releasable, else why not."""
        if source_id in EXCLUDED_SOURCES:
            return "permission pending (hard exclusion)"
        if not self.loaded:
            return MISSING_REGISTRY
        source_id = self.canonical(source_id)
        if source_id in EXCLUDED_SOURCES:
            return "permission pending (hard exclusion)"
        entry = self.sources.get(source_id)
        if entry is None:
            return "not in data/sources.yaml"
        if entry.status not in RELEASABLE_STATUSES:
            return f"status {entry.status}"
        if entry.permission == WRITTEN_PERMISSION:
            return None
        if entry.use == CITED_FACTS and entry.decision:
            return None  # Decision 068: single cited maker facts, no licence needed
        return licence_problem(entry.licence)

    def cited_url_problem(self, source_id: str, url: str | None) -> str | None:
        """Decision 068 / 087: for a `use: cited-facts` source with `cited_hosts`, each
        published fact's URL must match a listed maker host or path prefix; third-party and
        dealer copies stay internal evidence only and never ship."""
        entry = self.sources.get(self.canonical(source_id))
        if entry is None or entry.use != CITED_FACTS or not entry.cited_hosts:
            return None
        if not url or not str(url).strip():
            return f"missing source_url for cited-facts source {entry.id}"
        if any(url_matches(h, str(url)) for h in entry.cited_hosts):
            return None
        host = (urlsplit(str(url).strip()).hostname or "").lower()
        return f"source_url host {host!r} not in {entry.id} cited_hosts (Decision 068)"

    def fact_blocked(self, source_id: str, url: str | None = None) -> str | None:
        """None when a fact from `(source_id, url)` may ship, else why not."""
        return self.reason_blocked(source_id) or self.cited_url_problem(source_id, url)

    def cited_facts(self, source_id: str) -> bool:
        """True when `source_id` ships under Decision 068 (`use: cited-facts` + `decision`):
        its licence text names no licence on purpose, so a licence re-check must skip it."""
        entry = self.sources.get(self.canonical(source_id))
        return bool(entry and entry.use == CITED_FACTS and entry.decision)

    def aggregate_input_problem(self, source_id: str) -> str | None:
        """None when our own aggregates may be derived from `source_id` (T-111, A-35 S2):
        releasable, or active with `use: aggregates-only` and a logged owner `decision`."""
        why = self.reason_blocked(source_id)
        if why is None:
            return None
        entry = self.sources.get(self.canonical(source_id))
        if entry is None or entry.status not in RELEASABLE_STATUSES:
            return why
        if entry.use == AGGREGATES_ONLY and entry.decision:
            return None
        return why

    def source_for_url(self, url: str) -> str | None:
        """The registry id whose `site_hosts` names the URL's host, else None."""
        host = (urlsplit(url).hostname or "").lower()
        hits = [e.id for e in self.sources.values() if host and host in e.site_hosts]
        return hits[0] if len(hits) == 1 else None

    def releasable(self, source_id: str) -> bool:
        return self.reason_blocked(source_id) is None

    def source_object(self, source_id: str) -> dict[str, Any] | None:
        e = self.sources.get(self.canonical(source_id))
        if e is None:
            return None
        return {"id": e.id, "name": e.name, "licence": e.licence.split("(")[0].strip()}


def parse_registry(data: dict[str, Any]) -> Registry:
    out: dict[str, SourceEntry] = {}
    alias_of: dict[str, set[str]] = {}
    for s in data.get("sources") or []:
        for a in s.get("aliases") or []:
            alias_of.setdefault(str(a), set()).add(s["id"])
        out[s["id"]] = SourceEntry(
            id=s["id"],
            name=str(s.get("name", s["id"])),
            licence=str(s.get("licence") or ""),
            status=str(s.get("status") or ""),
            owner=str(s.get("owner") or ""),
            terms=str(s.get("terms") or ""),
            permission=str(s.get("permission") or "").strip().lower(),
            use=str(s.get("use") or "").strip().lower(),
            decision=str(s.get("decision") or "").strip(),
            site_hosts=tuple(str(h).lower() for h in s.get("site_hosts") or []),
            cited_hosts=tuple(str(h) for h in s.get("cited_hosts") or []),
            access=str(s.get("access") or "").strip().lower(),
            hosts=tuple(str(h).lower() for h in s.get("hosts") or []),
            cite_paths=tuple(str(h) for h in s.get("cite_paths") or []),
        )
    aliases = {a: next(iter(ids)) for a, ids in alias_of.items() if len(ids) == 1 and a not in out}
    return Registry(out, loaded=True, aliases=aliases)


def load_registry(path: Path) -> Registry:
    if not path.exists():
        return Registry()
    return parse_registry(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
