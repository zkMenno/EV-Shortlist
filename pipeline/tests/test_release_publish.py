"""T-064 / Decision 035: releases out of git — split, manifest, publish, fetch, rollback."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from ev_pipeline.commands.releases import ReleaseOpError, rollback
from ev_pipeline.release.build import release_cmd
from ev_pipeline.release.publish import (
    MANIFEST,
    DirPublisher,
    GithubPublisher,
    PublishError,
    asset_name,
    ensure_local,
    fetch,
    http_downloader,
    join_split,
    load_config,
    package,
    read_manifest,
    split_catalogue,
    verify,
)

FIX = Path(__file__).parent / "fixtures" / "release"
NOW = datetime(2026, 11, 15, 1, 0, tzinfo=UTC)


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "data"
    (d / "seed").mkdir(parents=True)
    shutil.copytree(FIX / "staging", d / "staging")
    shutil.copytree(FIX / "taxonomy", d / "taxonomy")
    for n in ("models", "variants", "platforms", "battery_packs", "variant_links"):
        shutil.copy(FIX / f"{n}.yaml", d / "seed" / f"{n}.yaml")
    for n in ("sources", "field_sources"):
        shutil.copy(FIX / f"{n}.yaml", d / f"{n}.yaml")
    monkeypatch.setenv("EV_DATA_DIR", str(d))
    monkeypatch.delenv("EV_RUNS_DIR", raising=False)
    return d


@pytest.fixture
def built(data_dir: Path) -> Path:
    assert release_cmd(False, data_dir=data_dir, now=NOW) == 0
    return data_dir / "releases" / "1"


def _cat() -> dict[str, Any]:
    return {
        "release": 7,
        "generated_at": "2026-11-15T01:00:00+00:00",
        "sources": [{"id": "rdw"}],
        "generations": [{"id": "g1"}, {"id": "g2"}, {"id": "g-empty"}],
        "rows": [
            {"variant_id": "v1", "generation_id": "g1", "x": 1, "provenance": {"x": "rdw"}},
            {"variant_id": "v2", "generation_id": "g2", "x": 2, "provenance": {"x": "rdw"}},
            {"variant_id": "v3", "generation_id": "g1", "x": 3, "provenance": {}},
        ],
        "taxonomy": {"a": 1},
        "known_issues": {"country": "NL", "by_generation": {"g1": {"codes": ["X"]}}},
    }


# --- config + split ----------------------------------------------------------------------


def test_repo_config_loads_and_scratch_dir_falls_back(tmp_path: Path) -> None:
    cfg = load_config(tmp_path)  # no publish.yaml here -> repo config
    assert cfg.target == "github" and cfg.tag(3) == "data-v3"
    assert "github.com" in cfg.download_hosts
    assert cfg.asset_url(3, "a.json").endswith("/releases/download/data-v3/a.json")
    assert "qa.json" in cfg.in_git and "catalogue.json" not in cfg.in_git


def test_repo_config_names_the_renamed_repo(tmp_path: Path) -> None:
    """The repo was renamed EV-Finder -> EV-Shortlist (2026-11-17): new manifests' storage
    URLs must name the new repo (PR #91 review), not lean on GitHub's rename redirect."""
    cfg = load_config(tmp_path)
    assert cfg.repo == "zkMenno/EV-Shortlist"
    assert cfg.asset_url(2, "a.json").startswith("https://github.com/zkMenno/EV-Shortlist/")


def test_split_round_trips_and_index_has_no_provenance(tmp_path: Path) -> None:
    cfg = load_config(tmp_path)
    cat = _cat()
    files = split_catalogue(cat, cfg)
    assert join_split(files, cfg) == cat
    index = json.loads(files[cfg.index_path])
    assert all("provenance" not in r for r in index["rows"])
    assert "by_generation" not in index["known_issues"]
    assert set(index["generation_files"]) == {"g1", "g2", "g-empty"}
    g1 = json.loads(files[index["generation_files"]["g1"]])
    assert [r["variant_id"] for r in g1["rows"]] == ["v1", "v3"]
    assert g1["known_issues"] == {"codes": ["X"]} and g1["rows"][0]["provenance"] == {"x": "rdw"}
    empty = json.loads(files[index["generation_files"]["g-empty"]])
    assert empty["rows"] == [] and empty["generation"] == {"id": "g-empty"}


def test_split_is_deterministic(tmp_path: Path) -> None:
    cfg = load_config(tmp_path)
    assert split_catalogue(_cat(), cfg) == split_catalogue(_cat(), cfg)


@pytest.mark.parametrize("bad", ["../x", "a/b", ".hidden", ""])
def test_split_refuses_unsafe_generation_ids(tmp_path: Path, bad: str) -> None:
    cat = _cat()
    cat["generations"].append({"id": bad})
    with pytest.raises(PublishError, match="file name"):
        split_catalogue(cat, load_config(tmp_path))


def test_row_with_unlisted_generation_still_gets_a_file(tmp_path: Path) -> None:
    cfg = load_config(tmp_path)
    cat = _cat()
    cat["rows"].append({"variant_id": "v9", "generation_id": "g9", "provenance": {}})
    files = split_catalogue(cat, cfg)
    assert join_split(files, cfg) == cat


def test_asset_names_are_flat() -> None:
    assert asset_name("catalogue/generations/g1.json") == "catalogue.generations.g1.json"


# --- package / manifest / verify ---------------------------------------------------------


def test_release_writes_manifest_covering_every_file(built: Path) -> None:
    m = read_manifest(built)
    assert m is not None and m["release"] == 1 and m["storage"]["tag"] == "data-v1"
    paths = {e["path"] for e in m["files"]}
    assert {"catalogue.json", "catalogue/index.json", "qa.json"} <= paths
    assert MANIFEST not in paths
    on_disk = {p.relative_to(built).as_posix() for p in built.rglob("*") if p.is_file()} - {
        MANIFEST
    }
    assert paths == on_disk
    assert m["qa"]["status"] in {"pass", "review"}
    assert m["counts"]["files"] == len(m["files"])
    assert verify(built, m) == []
    flags = {e["path"]: e["in_git"] for e in m["files"]}
    assert flags["qa.json"] and not flags["catalogue.json"]


def test_package_is_idempotent(built: Path, data_dir: Path) -> None:
    before = (built / MANIFEST).read_bytes()
    package(built, load_config(data_dir), now=datetime(2030, 1, 1, tzinfo=UTC))
    assert (built / MANIFEST).read_bytes() == before


def test_split_of_real_release_round_trips(built: Path, data_dir: Path) -> None:
    cfg = load_config(data_dir)
    cat = json.loads((built / "catalogue.json").read_text())
    files = {
        p.relative_to(built).as_posix(): p.read_bytes()
        for p in (built / "catalogue").rglob("*.json")
    }
    assert join_split(files, cfg) == cat


def test_verify_detects_tampering_and_missing_files(built: Path) -> None:
    m = read_manifest(built)
    assert m is not None
    (built / "catalogue.json").write_bytes(b"{}")
    (built / "facts.parquet").unlink()
    problems = verify(built, m)
    assert any("catalogue.json" in p for p in problems)
    assert any("facts.parquet: missing" in p for p in problems)
    assert not any("facts.parquet" in p for p in verify(built, m, only_present=True))


def test_package_refuses_folder_number_mismatch(built: Path, data_dir: Path) -> None:
    wrong = built.parent / "5"
    shutil.copytree(built, wrong)
    with pytest.raises(PublishError, match="must match"):
        package(wrong, load_config(data_dir))


@pytest.mark.parametrize("bad", ["../etc/passwd", "/abs", "a\\b"])
def test_manifest_with_unsafe_path_is_refused(built: Path, bad: str) -> None:
    m = json.loads((built / MANIFEST).read_text())
    m["files"][0]["path"] = bad
    (built / MANIFEST).write_text(json.dumps(m))
    with pytest.raises(PublishError, match="unsafe"):
        read_manifest(built)


def test_manifest_with_unknown_schema_is_refused(built: Path) -> None:
    m = json.loads((built / MANIFEST).read_text())
    m["schema"] = "something/9"
    (built / MANIFEST).write_text(json.dumps(m))
    with pytest.raises(PublishError, match="schema"):
        read_manifest(built)


# --- publishers --------------------------------------------------------------------------


def test_dir_publisher_publishes_then_unchanged_then_refuses(built: Path, tmp_path: Path) -> None:
    m = read_manifest(built)
    assert m is not None
    pub = DirPublisher(tmp_path / "store")
    assert pub.publish(built, m, replace=False) == "published"
    assert (tmp_path / "store" / "data-v1" / "catalogue.generations").exists() is False
    assert any(
        p.name.startswith("catalogue.generations.")
        for p in (tmp_path / "store" / "data-v1").iterdir()
    )
    assert pub.publish(built, m, replace=False) == "unchanged"
    (tmp_path / "store" / "data-v1" / "catalogue.json").write_bytes(b"x")
    with pytest.raises(PublishError, match="refusing"):
        pub.publish(built, m, replace=False)
    assert pub.publish(built, m, replace=True) == "published"


class FakeGh:
    """Records gh calls; holds one fake release store."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.assets: dict[str, list[dict[str, Any]]] = {}

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        verb, tag = args[2], args[3]
        if verb == "view":
            if tag not in self.assets:
                return subprocess.CompletedProcess(args, 1, "", "release not found")
            return subprocess.CompletedProcess(
                args, 0, json.dumps({"assets": self.assets[tag]}), ""
            )
        if verb == "delete":
            self.assets.pop(tag, None)
            return subprocess.CompletedProcess(args, 0, "", "")
        if verb == "create":
            files = [Path(a) for a in args if a.startswith("/") and not a.endswith(".notes.md")]
            import hashlib

            self.assets[tag] = [
                {"name": f.name, "size": f.stat().st_size,
                 "digest": "sha256:" + hashlib.sha256(f.read_bytes()).hexdigest()}
                for f in files
            ]  # fmt: skip
            return subprocess.CompletedProcess(args, 0, "", "")
        raise AssertionError(args)


def test_github_publisher_create_unchanged_refuse_replace(built: Path) -> None:
    m = read_manifest(built)
    assert m is not None
    gh = FakeGh()
    pub = GithubPublisher("zkMenno/EV-Finder", run=gh)
    assert pub.publish(built, m, replace=False) == "published"
    create = next(c for c in gh.calls if c[2] == "create")
    assert "--latest=false" in create and "zkMenno/EV-Finder" in create
    assert {a["name"] for a in gh.assets["data-v1"]} == {e["asset"] for e in m["files"]}
    assert pub.publish(built, m, replace=False) == "unchanged"
    gh.assets["data-v1"][0]["size"] += 1
    with pytest.raises(PublishError, match="never changes"):
        pub.publish(built, m, replace=False)
    assert pub.publish(built, m, replace=True) == "published"
    assert any(c[2] == "delete" for c in gh.calls)


def test_github_publisher_other_view_error_is_raised(built: Path) -> None:
    m = read_manifest(built)
    assert m is not None

    def run(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 1, "", "HTTP 401 bad credentials")

    with pytest.raises(PublishError, match="401"):
        GithubPublisher("o/r", run=run).publish(built, m, replace=False)


# --- fetch / ensure_local / rollback -----------------------------------------------------


def _store_downloader(store: Path, log: list[str]):
    def dl(url: str, dest: Path, max_bytes: int) -> None:
        log.append(url)
        dest.write_bytes((store / url.rsplit("/", 1)[1]).read_bytes())

    return dl


def _publish_and_strip(built: Path, store: Path) -> dict[str, Any]:
    m = read_manifest(built)
    assert m is not None
    DirPublisher(store).publish(built, m, replace=False)
    for e in m["files"]:
        if not e["in_git"]:
            (built / e["path"]).unlink()  # what git would hold after T-064
    return m


def test_fetch_restores_files_from_assets(built: Path, data_dir: Path, tmp_path: Path) -> None:
    m = _publish_and_strip(built, tmp_path / "store")
    log: list[str] = []
    stats = fetch(
        built,
        load_config(data_dir),
        download=_store_downloader(tmp_path / "store" / "data-v1", log),
    )
    assert stats["downloaded"] == sum(1 for e in m["files"] if not e["in_git"])
    assert verify(built, m) == []
    assert all("/releases/download/data-v1/" in u for u in log)
    log.clear()
    again = fetch(
        built,
        load_config(data_dir),
        download=_store_downloader(tmp_path / "store" / "data-v1", log),
    )
    assert again["downloaded"] == 0 and log == []


def test_fetch_rejects_a_wrong_download_and_leaves_nothing(
    built: Path, data_dir: Path, tmp_path: Path
) -> None:
    _publish_and_strip(built, tmp_path / "store")

    def evil(url: str, dest: Path, max_bytes: int) -> None:
        dest.write_bytes(b"not the file")

    with pytest.raises(PublishError, match="checksum"):
        fetch(built, load_config(data_dir), download=evil)
    assert not (built / "catalogue.json").exists()
    assert not any(p.name.startswith(".") and ".part-" in p.name for p in built.rglob("*"))


def test_http_downloader_uses_guarded_client(built: Path, data_dir: Path, tmp_path: Path) -> None:
    store = tmp_path / "store"
    m = _publish_and_strip(built, store)
    seen: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req.url.host)
        name = req.url.path.rsplit("/", 1)[1]
        return httpx.Response(200, content=(store / "data-v1" / name).read_bytes())

    cfg = load_config(data_dir)
    fetch(built, cfg, download=http_downloader(cfg, transport=httpx.MockTransport(handler)))
    assert set(seen) == {"github.com"} and verify(built, m) == []


def test_http_downloader_refuses_hosts_outside_allowlist(tmp_path: Path) -> None:
    from ev_pipeline.net import FetchBlocked

    cfg = load_config(tmp_path)
    dl = http_downloader(cfg, transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    with pytest.raises(FetchBlocked):
        dl("https://evil.example.com/x.json", tmp_path / "x", 100)


def test_ensure_local_fetches_missing_and_refuses_tampered(
    built: Path, data_dir: Path, tmp_path: Path
) -> None:
    _publish_and_strip(built, tmp_path / "store")
    log: list[str] = []
    ensure_local(data_dir, 1, download=_store_downloader(tmp_path / "store" / "data-v1", log))
    assert (built / "catalogue.json").exists() and log
    (built / "catalogue.json").write_bytes(b"{}")
    with pytest.raises(PublishError, match="catalogue.json"):
        ensure_local(data_dir, 1, download=_store_downloader(tmp_path / "store" / "data-v1", log))


def test_ensure_local_accepts_pre_t064_release(data_dir: Path) -> None:
    d = data_dir / "releases" / "3"
    d.mkdir(parents=True)
    (d / "catalogue.json").write_text("{}")
    assert ensure_local(data_dir, 3) == d


def test_rollback_fetches_release_outside_git(
    data_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert release_cmd(False, data_dir=data_dir, now=NOW) == 0
    (data_dir / "staging" / "eea.records.jsonl").unlink()
    assert release_cmd(False, data_dir=data_dir, now=NOW) == 0
    store = tmp_path / "store"
    _publish_and_strip(data_dir / "releases" / "1", store)
    log: list[str] = []
    import ev_pipeline.release.publish as pub

    monkeypatch.setattr(
        pub,
        "http_downloader",
        lambda cfg, transport=None: _store_downloader(store / "data-v1", log),
    )
    entry = rollback(data_dir, 1)
    assert entry["to"] == 1 and log


def test_rollback_without_files_or_store_is_refused(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert release_cmd(False, data_dir=data_dir, now=NOW) == 0
    (data_dir / "staging" / "eea.records.jsonl").unlink()
    assert release_cmd(False, data_dir=data_dir, now=NOW) == 0
    r1 = data_dir / "releases" / "1"
    m = read_manifest(r1)
    assert m is not None
    for e in m["files"]:
        if not e["in_git"]:
            (r1 / e["path"]).unlink()
    import ev_pipeline.release.publish as pub

    def offline(cfg: Any, transport: Any = None):
        def dl(url: str, dest: Path, max_bytes: int) -> None:
            raise PublishError("offline")

        return dl

    monkeypatch.setattr(pub, "http_downloader", offline)
    with pytest.raises(ReleaseOpError, match="unavailable"):
        rollback(data_dir, 1)


def test_next_release_diffs_against_fetched_previous(
    data_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert release_cmd(False, data_dir=data_dir, now=NOW) == 0
    store = tmp_path / "store"
    _publish_and_strip(data_dir / "releases" / "1", store)
    log: list[str] = []
    import ev_pipeline.release.publish as pub

    monkeypatch.setattr(
        pub,
        "http_downloader",
        lambda cfg, transport=None: _store_downloader(store / "data-v1", log),
    )
    assert release_cmd(False, data_dir=data_dir, now=NOW) == 0
    diff = json.loads((data_dir / "releases" / "2" / "diff.json").read_text())
    assert diff["counts"]["added"] == 0 and log  # compared with release 1, not with nothing


def test_next_release_fails_when_previous_unavailable(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert release_cmd(False, data_dir=data_dir, now=NOW) == 0
    r1 = data_dir / "releases" / "1"
    (r1 / "catalogue.json").unlink()
    import ev_pipeline.release.publish as pub

    def offline(cfg: Any, transport: Any = None):
        def dl(url: str, dest: Path, max_bytes: int) -> None:
            raise PublishError("offline")

        return dl

    monkeypatch.setattr(pub, "http_downloader", offline)
    assert release_cmd(False, data_dir=data_dir, now=NOW) == 1
    assert not (data_dir / "releases" / "2").exists()


def test_gitignore_keeps_exactly_the_in_git_files(tmp_path: Path) -> None:
    """.gitignore and publish.yaml `in_git` must list the same files (plus manifest.json)."""
    root = Path(__file__).resolve().parents[2]
    lines = (root / ".gitignore").read_text(encoding="utf-8").splitlines()
    kept = {
        ln.removeprefix("!data/releases/[0-9]*/")
        for ln in lines
        if ln.startswith("!data/releases/[0-9]*/")
    }
    assert "data/releases/[0-9]*/*" in lines
    assert kept == set(load_config(tmp_path).in_git) | {MANIFEST}


# --- the workflow's shell publisher (pipeline/scripts/gh-publish-release.sh) -------------

FAKE_GH = """#!/usr/bin/env bash
# Fake gh for the publisher: one folder per tag; `.draft` marks an unpublished release.
s="$FAKE_GH_STORE"; verb=$2; tag=$3; shift 3
case $verb in
 view) if [ -n "${FAKE_GH_VIEW_ERROR:-}" ]; then echo "HTTP 403: rate limit" >&2; exit 1; fi
       [ -d "$s/$tag" ] || { echo "release not found" >&2; exit 1; }
       case "$*" in
         *isDraft*) if [ -f "$s/$tag.draft" ]; then echo true; else echo false; fi;;
         *) for f in "$s/$tag"/*; do
              [ -e "$f" ] || continue
              d="sha256:$(sha256sum "$f" | cut -d' ' -f1)"; [ -n "${FAKE_GH_NO_DIGEST:-}" ] && d=-
              z=$(wc -c < "$f" | tr -d ' ')
              printf '%s\\t%s\\t%s\\tuploaded\\n' "$(basename "$f")" "$d" "$z"
            done;;
       esac;;
 delete) rm -rf "$s/$tag" "$s/$tag.draft";;
 create) mkdir -p "$s/$tag"; case "$*" in *--draft*) touch "$s/$tag.draft";; esac
         for a in "$@"; do [ -f "$a" ] && [ "${a##*/}" != .notes.md ] && cp "$a" "$s/$tag/"; done
         true;;
 upload) n=$(cat "$s/.fails" 2>/dev/null || echo 0)
         if [ "$n" -gt 0 ]; then
           echo $((n - 1)) > "$s/.fails"; echo "HTTP 403: secondary rate limit" >&2; exit 1
         fi
         echo x >> "$s/.uploads"
         for a in "$@"; do [ -f "$a" ] && cp "$a" "$s/$tag/"; done; true;;
 delete-asset) rm -f "$s/$tag/$1";;
 edit) case "$*" in *--draft=false*) rm -f "$s/$tag.draft";; esac;;
esac
"""


def _publisher(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "gh").write_text(FAKE_GH)
    (bindir / "gh").chmod(0o755)
    store = tmp_path / "store"
    store.mkdir()
    env = {
        **os.environ,
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "GITHUB_REPOSITORY": "o/r",
        "FAKE_GH_STORE": str(store),
        "UPLOAD_BATCH": "3",
        "UPLOAD_PAUSE_S": "0",
        "UPLOAD_BACKOFF_S": "0",
    }
    return store, env


def _run_publisher(
    built: Path, env: dict[str, str], *extra: str
) -> subprocess.CompletedProcess[str]:
    script = Path(__file__).resolve().parents[1] / "scripts" / "gh-publish-release.sh"
    return subprocess.run(
        ["bash", str(script), str(built), *extra], env=env, capture_output=True, text=True
    )


@pytest.mark.skipif(shutil.which("jq") is None, reason="jq not installed")
def test_shell_publisher_publishes_unchanged_and_refuses(built: Path, tmp_path: Path) -> None:
    store, env = _publisher(tmp_path)

    def run(*extra: str) -> subprocess.CompletedProcess[str]:
        return _run_publisher(built, env, *extra)

    first = run()
    assert first.returncode == 0 and "published" in first.stdout, first.stderr + first.stdout
    m = read_manifest(built)
    assert m is not None
    assert {p.name for p in (store / "data-v1").iterdir()} == {e["asset"] for e in m["files"]}
    assert not (store / "data-v1.draft").exists()  # published only once complete
    assert "unchanged" in run().stdout
    (store / "data-v1" / "qa.md").write_text("changed")
    refused = run()
    assert refused.returncode == 1 and "never changes" in refused.stdout
    shutil.rmtree(store / "data-v1")
    (built / "catalogue.json").write_bytes(b"{}")
    bad = run()
    assert bad.returncode == 1 and "differs from manifest" in bad.stdout


@pytest.mark.skipif(shutil.which("jq") is None, reason="jq not installed")
def test_shell_publisher_resumes_a_stopped_draft(built: Path, tmp_path: Path) -> None:
    """Release 3 (2026-11-18): ~650 assets uploaded at once hit GitHub's secondary rate limit
    and left a draft with 504. A re-run must resume that draft (fix wrong assets, upload the
    rest in paced batches, retry on 403) and publish it only once it matches the manifest."""
    store, env = _publisher(tmp_path)
    m = read_manifest(built)
    assert m is not None
    assets = sorted(e["asset"] for e in m["files"])
    assert len(assets) >= 4
    draft = store / "data-v1"
    draft.mkdir()
    (store / "data-v1.draft").touch()
    src = {e["asset"]: built / e["path"] for e in m["files"]}
    shutil.copy(src[assets[0]], draft / assets[0])  # already up, correct
    (draft / assets[1]).write_bytes(b"truncated")  # wrong size: replaced
    same = bytearray(src[assets[2]].read_bytes())
    same[0] ^= 1
    (draft / assets[2]).write_bytes(bytes(same))  # same size, other bytes: replaced (#162 review)
    (draft / "stale.json").write_text("{}")  # not in the manifest: removed
    (store / ".fails").write_text("2")  # the first two uploads hit the rate limit

    out = _run_publisher(built, env)  # no --replace-unmerged: a draft was never published
    assert out.returncode == 0 and "published" in out.stdout, out.stderr + out.stdout
    assert sorted(p.name for p in draft.iterdir()) == assets
    for a in assets:
        assert (draft / a).read_bytes() == src[a].read_bytes()
    assert not (store / "data-v1.draft").exists()
    assert f"uploading {len(assets) - 1} of {len(assets)}" in out.stdout
    batches = -(-(len(assets) - 1) // 3)  # every asset but the one already correct
    assert len((store / ".uploads").read_text().split()) == batches  # paced, 3 per batch


@pytest.mark.skipif(shutil.which("jq") is None, reason="jq not installed")
def test_shell_publisher_never_treats_a_failed_lookup_as_a_new_release(
    built: Path, tmp_path: Path
) -> None:
    """#162 review: a 403 on the first lookup must not create a second draft for the tag."""
    store, env = _publisher(tmp_path)
    out = _run_publisher(built, {**env, "FAKE_GH_VIEW_ERROR": "1"})
    assert out.returncode == 1 and "cannot read release" in out.stdout
    assert not (store / "data-v1").exists()


@pytest.mark.skipif(shutil.which("jq") is None, reason="jq not installed")
def test_shell_publisher_falls_back_to_size_without_a_digest(built: Path, tmp_path: Path) -> None:
    """Assets uploaded before GitHub returned digests: same size counts as unchanged."""
    store, env = _publisher(tmp_path)
    assert _run_publisher(built, env).returncode == 0
    assert "unchanged" in _run_publisher(built, {**env, "FAKE_GH_NO_DIGEST": "1"}).stdout


@pytest.mark.skipif(shutil.which("jq") is None, reason="jq not installed")
def test_shell_publisher_gives_up_after_retries_and_keeps_the_draft(
    built: Path, tmp_path: Path
) -> None:
    store, env = _publisher(tmp_path)
    (store / ".fails").write_text("99")
    out = _run_publisher(built, {**env, "UPLOAD_RETRIES": "3"})
    assert out.returncode == 1 and "re-run the job to resume" in out.stdout
    assert (store / "data-v1.draft").exists()  # never published half-done
    (store / ".fails").write_text("0")
    again = _run_publisher(built, env)
    assert again.returncode == 0 and "published" in again.stdout
    assert not (store / "data-v1.draft").exists()


def test_fetch_only_selected_files(built: Path, data_dir: Path, tmp_path: Path) -> None:
    _publish_and_strip(built, tmp_path / "store")
    log: list[str] = []
    dl = _store_downloader(tmp_path / "store" / "data-v1", log)
    stats = fetch(built, load_config(data_dir), download=dl, only=frozenset({"catalogue.json"}))
    assert stats["downloaded"] == 1 and (built / "catalogue.json").exists()
    assert not (built / "facts.parquet").exists()
    fetch(built, load_config(data_dir), download=dl, only=frozenset({"catalogue/"}))
    assert (built / "catalogue" / "index.json").exists()
    with pytest.raises(PublishError, match="not in the manifest"):
        fetch(built, load_config(data_dir), download=dl, only=frozenset({"nope.json"}))


def test_ensure_local_only_ignores_absent_optional_files(built: Path, data_dir: Path) -> None:
    # Only catalogue.json is needed and present: no download even though split files are gone.
    shutil.rmtree(built / "catalogue")

    def no_net(url: str, dest: Path, max_bytes: int) -> None:
        raise AssertionError("should not download")

    only = frozenset({"catalogue.json", "not-in-this-release.json"})
    assert ensure_local(data_dir, 1, download=no_net, only=only) == built


# --- G-66: ev release fetch --via-gh (mocked subprocess, no network) -------------------------


def _fake_gh_download(store: Path, calls: list[list[str]]):
    """Fake `gh release download` runner copying matching assets from `<store>/<tag>/`."""
    import fnmatch

    def run(args: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        assert args[:3] == ["gh", "release", "download"]
        tag = args[3]
        dest = Path(args[args.index("--dir") + 1])
        patterns: list[str] = []
        i = 0
        while i < len(args):
            if args[i] == "--pattern":
                patterns.append(args[i + 1])
                i += 2
            else:
                i += 1
        src_dir = store / tag
        if not src_dir.is_dir():
            return subprocess.CompletedProcess(args, 1, "", f"release {tag} not found")
        for f in sorted(src_dir.iterdir()):
            if not f.is_file():
                continue
            if patterns and not any(fnmatch.fnmatchcase(f.name, pat) for pat in patterns):
                continue
            shutil.copyfile(f, dest / f.name)
        return subprocess.CompletedProcess(args, 0, "", "")

    return run


def test_fetch_via_gh_restores_verifies_and_skips_when_already_ok(
    built: Path, data_dir: Path, tmp_path: Path
) -> None:
    store = tmp_path / "store"
    m = _publish_and_strip(built, store)
    calls: list[list[str]] = []
    cfg = load_config(data_dir)

    stats = fetch(built, cfg, via_gh=True, run=_fake_gh_download(store, calls))
    assert stats["downloaded"] == sum(1 for e in m["files"] if not e["in_git"])
    assert verify(built, m) == []
    assert len(calls) == 1
    assert calls[0][:6] == ["gh", "release", "download", "data-v1", "--repo", cfg.repo]
    assert "--pattern" not in calls[0]  # full fetch downloads all assets in one call

    # Second run: every file matches manifest -> gh is not invoked at all.
    calls.clear()
    again = fetch(built, cfg, via_gh=True, run=_fake_gh_download(store, calls))
    assert again["downloaded"] == 0 and calls == []


def test_fetch_via_gh_only_passes_patterns_and_downloads_subset(
    built: Path, data_dir: Path, tmp_path: Path
) -> None:
    store = tmp_path / "store"
    _publish_and_strip(built, store)
    calls: list[list[str]] = []
    cfg = load_config(data_dir)

    stats = fetch(
        built,
        cfg,
        only=frozenset({"catalogue.json"}),
        via_gh=True,
        run=_fake_gh_download(store, calls),
    )
    assert stats["downloaded"] == 1
    assert (built / "catalogue.json").exists()
    assert not (built / "facts.parquet").exists()
    assert len(calls) == 1
    assert "--pattern" in calls[0] and "catalogue.json" in calls[0]


def test_fetch_via_gh_handles_images_tar_bundle(tmp_path: Path) -> None:
    """G-66 + Decision 086: `--via-gh` downloads, verifies, and unpacks `images.tar`."""
    rel = tmp_path / "data" / "releases" / "7"
    rel.mkdir(parents=True)
    photos = {
        "images/g0-abcd1234-400.webp": b"webp-400" * 20,
        "images/g0-abcd1234-800.webp": b"webp-800" * 30,
    }
    cat = {
        "release": 7,
        "generated_at": "2026-11-26T01:00:00+00:00",
        "sources": [],
        "generations": [{"id": "g0"}],
        "rows": [{"variant_id": "v0", "generation_id": "g0"}],
    }
    (rel / "catalogue.json").write_text(json.dumps(cat), encoding="utf-8")
    (rel / "qa.json").write_text(json.dumps({"status": "pass"}), encoding="utf-8")
    for p, data in photos.items():
        (rel / p).parent.mkdir(parents=True, exist_ok=True)
        (rel / p).write_bytes(data)

    cfg = load_config(tmp_path)
    m = package(rel, cfg, now=NOW)
    assert any(e["path"] == "images.tar" for e in m["files"])

    store = tmp_path / "store"
    DirPublisher(store).publish(rel, m, replace=False)
    for e in m["files"]:
        if not e["in_git"]:
            (rel / e["path"]).unlink()
    shutil.rmtree(rel / "images")

    calls: list[list[str]] = []
    stats = fetch(rel, cfg, via_gh=True, run=_fake_gh_download(store, calls))
    assert stats["unpacked"] == 1
    assert verify(rel, m) == []
    for p, data in photos.items():
        assert (rel / p).read_bytes() == data
    assert len(calls) == 1

    # Missing unpacked photo re-unpacks from local images.tar without invoking gh.
    (rel / next(iter(photos))).unlink()
    calls.clear()
    again = fetch(rel, cfg, via_gh=True, run=_fake_gh_download(store, calls))
    assert again["downloaded"] == 0 and again["unpacked"] == 1 and calls == []
    assert verify(rel, m) == []


def test_fetch_via_gh_rejects_bad_checksum_missing_asset_and_gh_errors(
    built: Path, data_dir: Path, tmp_path: Path
) -> None:
    store = tmp_path / "store"
    _publish_and_strip(built, store)
    cfg = load_config(data_dir)

    # 1. Tampered asset -> refused before placing ANY file into release_dir
    tampered = store / "data-v1" / "catalogue.json"
    orig = tampered.read_bytes()
    tampered.write_bytes(b"corrupt")
    with pytest.raises(PublishError, match="checksum"):
        fetch(built, cfg, via_gh=True, run=_fake_gh_download(store, []))
    assert not (built / "catalogue.json").exists()
    assert not (built / "facts.parquet").exists()
    assert not any(p.name.startswith(".") and ".part-" in p.name for p in built.rglob("*"))
    tampered.write_bytes(orig)

    # 2. Missing asset in gh output -> refused
    def partial_gh(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 0, "", "")

    with pytest.raises(PublishError, match="not downloaded by gh"):
        fetch(built, cfg, via_gh=True, run=partial_gh)

    # 3. Non-zero gh exit -> PublishError with stderr
    def failing_gh(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 1, "", "HTTP 401 unauthorized")

    with pytest.raises(PublishError, match="401 unauthorized"):
        fetch(built, cfg, via_gh=True, run=failing_gh)

    # 4. Missing gh binary -> clear PublishError
    def missing_gh(args: list[str]) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("gh")

    with pytest.raises(PublishError, match="gh CLI not found"):
        fetch(built, cfg, via_gh=True, run=missing_gh)


def test_cli_release_fetch_via_gh_and_blocked_hint(
    built: Path, data_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    import ev_pipeline.release.publish as pub
    from ev_pipeline.cli import main
    from ev_pipeline.net import FetchBlocked

    store = tmp_path / "store"
    m = _publish_and_strip(built, store)

    # Direct HTTPS blocked by proxy -> clean error + --via-gh hint
    def blocked_dl(cfg: Any, transport: Any = None):
        def dl(url: str, dest: Path, max_bytes: int) -> None:
            raise FetchBlocked("release-assets: private address refused")

        return dl

    monkeypatch.setattr(pub, "http_downloader", blocked_dl)
    assert main(["release", "fetch", "latest"]) == 1
    out = capsys.readouterr().out
    assert "private address refused" in out and "--via-gh" in out

    # Retry with --via-gh -> succeeds via mocked subprocess
    calls: list[list[str]] = []
    monkeypatch.setattr(pub, "_run", _fake_gh_download(store, calls))
    assert main(["release", "fetch", "latest", "--via-gh"]) == 0
    out = capsys.readouterr().out
    assert "downloaded" in out and verify(built, m) == [] and len(calls) == 1
