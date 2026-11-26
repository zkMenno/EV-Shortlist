"""T-134: car photos per generation (Decision 081). No network: MockTransport + generated images."""

from __future__ import annotations

import hashlib
import io
import json
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml
from PIL import Image

from ev_pipeline import net
from ev_pipeline.images.photos import parse_photos
from ev_pipeline.images.qa import check_images
from ev_pipeline.images.store import (
    build_release_images,
    cache_key,
    fetch_originals,
    render_sizes,
)
from ev_pipeline.opendata import bundle as ob
from ev_pipeline.release import build as rb
from ev_pipeline.release.gate import load_registry

TODAY = date(2026, 11, 18)
GENS = {"vw-id3-gen1", "kia-ev6-gen1"}
QA = Path(__file__).parent / "fixtures" / "qa"


def commons(**kw: Any) -> dict[str, Any]:
    e = {
        "generation_id": "vw-id3-gen1",
        "source": "commons",
        "page_url": "https://commons.wikimedia.org/wiki/File:ID3.jpg",
        "file_url": "https://upload.wikimedia.org/wikipedia/commons/a/ab/ID3.jpg",
        "licence": "CC-BY-SA-4.0",
        "author": "Jane Doe",
        "credit": "Photo: Jane Doe, CC BY-SA 4.0, via Wikimedia Commons",
        "retrieved_at": "2026-11-18",
    }
    e.update(kw)
    # T-149: every Commons photo carries its file-page template (here as if read by WS3)
    if e["source"] == "commons" and "licence_template" not in kw:
        e["licence_template"] = f"self|{str(e['licence']).lower()}"
        e.setdefault("licence_checked_at", "2026-11-18")
    return e


def press(verdict: str = "allowed", **kw: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    e = commons(
        generation_id="kia-ev6-gen1",
        source="press",
        licence="press-terms",
        make_id="kia",
        page_url="https://press.kia.example/ev6",
        file_url="https://media.kia.example/ev6.jpg",
        credit="Photo: Kia",
    )
    e.update(kw)
    terms = {
        "makers": [{"make_id": "kia", "verdict": verdict, "photo_hosts": ["media.kia.example"]}]
    }
    return e, terms


def jpeg(w: int, h: int, exif: bool = False) -> bytes:
    im = Image.new("RGB", (w, h), (30, 120, 60))
    buf = io.BytesIO()
    if exif:
        ex = Image.Exif()
        ex[0x010F] = "SecretCam"  # Make
        im.save(buf, format="JPEG", exif=ex)
    else:
        im.save(buf, format="JPEG")
    return buf.getvalue()


# --- photos.yaml rules ---------------------------------------------------------------------


def test_valid_commons_and_allowed_press_photos_pass() -> None:
    p, terms = press()
    photos, problems = parse_photos({"photos": [commons(), p]}, terms, GENS, TODAY)
    assert problems == []
    assert {x.generation_id for x in photos} == GENS
    assert photos[0].field()["licence"] == "CC-BY-SA-4.0"


@pytest.mark.parametrize(
    ("entry", "reason"),
    [
        (commons(licence="CC-BY-NC-4.0"), "licence"),
        (commons(licence="CC-BY-ND-4.0"), "licence"),
        (commons(licence="press-terms"), "licence"),
        (commons(credit="  "), "credit"),
        (commons(generation_id="nope"), "unknown generation_id"),
        (commons(file_url="http://upload.wikimedia.org/x.jpg"), "https"),
        (commons(retrieved_at="2027-01-01"), "future"),
        (commons(retrieved_at="soon"), "not a date"),
        (commons(source="flickr"), "source must be"),
    ],
)
def test_photo_rule_breaks_go_to_problems(entry: dict[str, Any], reason: str) -> None:
    photos, problems = parse_photos({"photos": [entry]}, None, GENS, TODAY)
    assert photos == []
    assert len(problems) == 1 and reason in problems[0].reason


@pytest.mark.parametrize("verdict", ["unclear", "not_allowed"])
def test_press_photo_needs_allowed_terms(verdict: str) -> None:
    p, terms = press(verdict)
    photos, problems = parse_photos({"photos": [p]}, terms, GENS, TODAY)
    assert photos == [] and "not 'allowed'" in problems[0].reason


@pytest.mark.parametrize("lic", ["CC-BY-4.0", "CC-BY-SA-3.0-DE", "CC-BY-2.0-AT", "CC-BY-SA-2.5"])
def test_commons_country_ports_are_allowed(lic: str) -> None:
    photos, problems = parse_photos({"photos": [commons(licence=lic)]}, None, GENS, TODAY)
    assert problems == [] and photos[0].licence == lic


@pytest.mark.parametrize(
    "lic", ["CC-BY-SA-4.0-DE", "CC-BY-NC-SA-3.0-DE", "CC-BY-SA-3.0-de", "CC-BY-SA"]
)
def test_commons_licence_lookalikes_are_refused(lic: str) -> None:
    photos, problems = parse_photos({"photos": [commons(licence=lic)]}, None, GENS, TODAY)
    assert photos == [] and "licence" in problems[0].reason


def test_one_photo_per_generation() -> None:
    photos, problems = parse_photos({"photos": [commons(), commons()]}, None, GENS, TODAY)
    assert len(photos) == 1 and "second photo" in problems[0].reason


def test_no_photos_file_means_no_photos() -> None:
    assert parse_photos(None, None, GENS, TODAY) == ([], [])


# --- resize ----------------------------------------------------------------------------------


def test_render_three_webp_widths_and_strips_exif() -> None:
    out = render_sizes(jpeg(2000, 1000, exif=True), "vw-id3-gen1")
    widths = sorted(int(p.rsplit("-", 1)[1][:-5]) for p in out)
    assert widths == [400, 800, 1600]
    for path, data in out.items():
        assert path.startswith("images/vw-id3-gen1-") and path.endswith(".webp")
        with Image.open(io.BytesIO(data)) as im:
            assert im.format == "WEBP"
            assert im.width == int(path.rsplit("-", 1)[1][:-5])
            assert im.height == im.width // 2
            assert "exif" not in im.info
            assert b"SecretCam" not in data


def test_render_never_upscales() -> None:
    assert {p.rsplit("-", 1)[1] for p in render_sizes(jpeg(900, 600), "g")} == {
        "400.webp",
        "800.webp",
    }
    assert {p.rsplit("-", 1)[1] for p in render_sizes(jpeg(300, 200), "g")} == {"300.webp"}


def test_new_photo_gets_a_new_path() -> None:
    a = set(render_sizes(jpeg(500, 300), "g"))
    b = set(render_sizes(jpeg(501, 300), "g"))
    assert a.isdisjoint(b)


# --- fetch once ------------------------------------------------------------------------------


def _client_factory(handler, hosts: dict[str, list[str]]):
    def make(sid: str) -> httpx.Client:
        return net.safe_client(sid, hosts=hosts[sid], transport=httpx.MockTransport(handler))

    return make


HOSTS = {"wikimedia-commons": ["upload.wikimedia.org"], "maker-press-photos": []}


def test_fetch_downloads_once_then_uses_cache(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(net, "system_resolver", lambda host, port: ["93.184.216.34"])
    calls: list[str] = []
    body = jpeg(1000, 500)

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(str(req.url))
        return httpx.Response(200, content=body, headers={"content-type": "image/jpeg"})

    photos, _ = parse_photos({"photos": [commons()]}, None, GENS, TODAY)
    f = _client_factory(handler, HOSTS)
    rep = fetch_originals(photos, tmp_path, f, sleep=lambda s: None)
    assert rep.fetched == ["vw-id3-gen1"] and len(calls) == 1
    key = cache_key(photos[0].file_url)
    assert (tmp_path / f"{key}.bin").read_bytes() == body
    meta = json.loads((tmp_path / f"{key}.json").read_text())
    assert meta["bytes"] == len(body) and meta["content_type"] == "image/jpeg"
    rep2 = fetch_originals(photos, tmp_path, f, sleep=lambda s: None)
    assert rep2.cached == ["vw-id3-gen1"] and len(calls) == 1


def test_fetch_refuses_non_images_and_unlisted_hosts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(net, "system_resolver", lambda host, port: ["93.184.216.34"])

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>", headers={"content-type": "text/html"})

    p, terms = press()
    photos, _ = parse_photos({"photos": [commons(), p]}, terms, GENS, TODAY)
    rep = fetch_originals(photos, tmp_path, _client_factory(handler, HOSTS), sleep=lambda s: None)
    assert rep.fetched == []
    assert "not an image" in rep.failed["vw-id3-gen1"]
    assert "FetchBlocked" in rep.failed["kia-ev6-gen1"]  # press host not in the allowlist
    assert not list(tmp_path.glob("*.bin"))


# --- release field + QA ----------------------------------------------------------------------


def _data_dir(tmp_path: Path, original: bytes | None) -> Path:
    d = tmp_path / "data"
    (d / "images").mkdir(parents=True)
    (d / "images" / "photos.yaml").write_text(yaml.safe_dump({"photos": [commons()]}))
    if original is not None:
        cache = d / "cache" / "images"
        cache.mkdir(parents=True)
        (cache / f"{cache_key(commons()['file_url'])}.bin").write_bytes(original)
    return d


def _catalogue() -> dict[str, Any]:
    return {"generations": [{"id": g} for g in sorted(GENS)], "rows": []}


def test_attach_holds_back_until_schema_has_the_field(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(rb, "_schema", lambda: {"$defs": {"Generation": {"properties": {}}}})
    cat = _catalogue()
    files, log = rb.attach_images(cat, _data_dir(tmp_path, jpeg(1000, 500)), TODAY)
    assert files == {} and "held back" in log["status"]
    assert all("image" not in g for g in cat["generations"])


def test_attach_adds_field_and_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        rb, "_schema", lambda: {"$defs": {"Generation": {"properties": {"image": {}}}}}
    )
    cat = _catalogue()
    files, log = rb.attach_images(cat, _data_dir(tmp_path, jpeg(1000, 500)), TODAY)
    img = next(g for g in cat["generations"] if g["id"] == "vw-id3-gen1")["image"]
    assert [f["width"] for f in img["files"]] == [400, 800]
    assert set(files) == {f["path"] for f in img["files"]}
    assert img["licence"] == "CC-BY-SA-4.0" and img["credit"].startswith("Photo: Jane Doe")
    assert img["page_url"].startswith("https://commons.wikimedia.org/")
    assert img["retrieved_at"] == "2026-11-18"
    assert log["status"] == "attached" and log["by_source"] == {"commons": 1}
    assert check_images(cat).status == "pass"


def test_uncached_photo_is_logged_not_attached(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        rb, "_schema", lambda: {"$defs": {"Generation": {"properties": {"image": {}}}}}
    )
    cat = _catalogue()
    files, log = rb.attach_images(cat, _data_dir(tmp_path, None), TODAY)
    assert files == {} and "not fetched" in log["missing"]["vw-id3-gen1"]


def test_unreadable_original_is_logged(tmp_path: Path) -> None:
    photos, _ = parse_photos({"photos": [commons()]}, None, GENS, TODAY)
    (tmp_path / f"{cache_key(commons()['file_url'])}.bin").write_bytes(b"not an image")
    rel = build_release_images(photos, tmp_path)
    assert rel.fields == {} and "unreadable" in rel.missing["vw-id3-gen1"]


@pytest.mark.parametrize(
    ("patch", "needle"),
    [
        ({"licence": "CC-BY-NC-4.0"}, "licence"),
        ({"credit": ""}, "credit"),
        ({"files": [{"width": 800, "path": "https://upload.wikimedia.org/x.jpg"}]}, "hotlink"),
        ({"files": [{"width": 800, "path": "images/../../etc/passwd"}]}, "hotlink"),
        ({"files": []}, "no image files"),
    ],
)
def test_release_qa_blocks_bad_images(patch: dict[str, Any], needle: str) -> None:
    img = {
        "files": [{"width": 800, "path": "images/g-abc-800.webp", "bytes": 1, "sha256": "x"}],
        **parse_photos({"photos": [commons()]}, None, GENS, TODAY)[0][0].field(),
    }
    img.update(patch)
    c = check_images({"generations": [{"id": "vw-id3-gen1", "image": img}]})
    assert c.blocking and c.status == "fail"
    assert any(needle in p for p in c.details["problems"])


def test_open_data_bundle_carries_no_images() -> None:
    cat = json.loads((QA / "catalogue.json").read_text())
    img = {"files": [{"width": 800, "path": "images/x-800.webp"}], "licence": "CC-BY-SA-4.0"}
    gens = sorted({r["generation_id"] for r in cat["rows"]})
    assert gens and cat["rows"]
    cat["generations"] = [{"id": g, "image": img} for g in gens]
    for r in cat["rows"]:
        r["image"] = img  # even a stray row-level key must not leak into the CC BY bundle
    b = ob.build_bundle(cat, load_registry(QA / "sources.yaml"))
    text = ob.variants_csv(b) + json.dumps(b.rows) + json.dumps(ob.field_docs(b))
    assert "webp" not in text and "CC-BY-SA" not in text and "image" not in text.lower()


def test_fetch_stops_at_the_first_429(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(net, "system_resolver", lambda host, port: ["93.184.216.34"])
    calls: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(str(req.url))
        return httpx.Response(429, headers={"retry-after": "600"})

    entries = [
        commons(),
        commons(generation_id="kia-ev6-gen1", file_url="https://upload.wikimedia.org/b.jpg"),
    ]
    photos, _ = parse_photos({"photos": entries}, None, GENS, TODAY)
    rep = fetch_originals(photos, tmp_path, _client_factory(handler, HOSTS), sleep=lambda s: None)
    assert len(calls) == 1  # never hammers the rest
    assert rep.stopped and "retry-after 600" in rep.stopped
    assert set(rep.failed) == GENS and all("RateLimited" in v for v in rep.failed.values())


def test_default_client_sends_a_contactable_user_agent() -> None:
    from ev_pipeline.images import store

    c = store._default_client("wikimedia-commons")
    try:
        assert "github.com/zkMenno/EV-Shortlist" in c.headers["User-Agent"]
    finally:
        c.close()


def test_refresh_fetch_step_never_raises(tmp_path: Path) -> None:
    from ev_pipeline.refresh.runner import fetch_images

    out = fetch_images(tmp_path)  # no seed, no photos: logged, not raised
    assert out["outcome"] == "failed" and "reason" in out


@pytest.mark.seed
def test_refresh_fetch_step_fetches_listed_photos(tmp_path: Path, monkeypatch) -> None:
    from ev_pipeline.images import store
    from ev_pipeline.refresh import runner

    real = Path(__file__).resolve().parents[2] / "data"
    d = tmp_path / "data"
    (d / "seed").mkdir(parents=True)
    (d / "seed" / "models.yaml").write_text((real / "seed" / "models.yaml").read_text())
    (d / "images").mkdir()
    gid = "tesla-model-3-gen1"  # first generation in the seed
    (d / "images" / "photos.yaml").write_text(
        yaml.safe_dump({"photos": [commons(generation_id=gid)]})
    )
    seen: list[str] = []

    def fake_fetch(photos, cache, *a, **k):
        seen.extend(p.generation_id for p in photos)
        return store.FetchReport([p.generation_id for p in photos], [], {})

    monkeypatch.setattr(store, "fetch_originals", fake_fetch)
    out = runner.fetch_images(d)
    assert out["outcome"] == "ok" and out["fetched"] == 1 and seen == [gid]


@pytest.mark.seed
def test_photos_pending_lets_a_photo_only_night_publish(tmp_path: Path) -> None:
    """#110 should-fix 3: a night with new photos but no data change used to be skipped."""
    from ev_pipeline.refresh.runner import photos_pending

    real = Path(__file__).resolve().parents[2] / "data"
    d = tmp_path / "data"
    (d / "seed").mkdir(parents=True)
    (d / "seed" / "models.yaml").write_text((real / "seed" / "models.yaml").read_text())
    (d / "images").mkdir()
    gid = "tesla-model-3-gen1"
    photo = commons(generation_id=gid)
    (d / "images" / "photos.yaml").write_text(yaml.safe_dump({"photos": [photo]}))
    rel = d / "releases" / "1"
    rel.mkdir(parents=True)
    (d / "releases" / "latest").write_text("1\n")

    def publish(image: dict[str, Any] | None) -> None:
        g: dict[str, Any] = {"id": gid}
        if image:
            g["image"] = image
        (rel / "catalogue.json").write_text(json.dumps({"generations": [g]}))

    publish(None)
    assert photos_pending(d) == []  # listed but not downloaded yet: nothing to ship
    cache = d / "cache" / "images"
    cache.mkdir(parents=True)
    (cache / f"{cache_key(photo['file_url'])}.bin").write_bytes(b"x")
    assert photos_pending(d) == [gid]  # downloaded, not published: publish tonight
    from ev_pipeline.images.photos import parse_photos as _pp

    field = _pp({"photos": [photo]}, None, {gid}, date.today())[0][0].field()
    publish({**field, "files": [{"path": "images/x.webp"}]})
    assert photos_pending(d) == []  # already in the release (files don't count)
    publish({**field, "credit": "old credit line"})
    assert photos_pending(d) == [gid]  # same file, corrected credit: publish (#150 review)
    publish({**field, "files": [{"path": "images/x.webp"}]})
    publish({"file_url": "https://upload.wikimedia.org/old.jpg"})
    assert photos_pending(d) == [gid]  # photo swapped
    (d / "images" / "photos.yaml").write_text(yaml.safe_dump({"photos": []}))
    assert photos_pending(d) == [gid]  # photo removed from photos.yaml
    (d / "releases" / "latest").unlink()
    assert photos_pending(d) == []  # no release yet: the first one is built anyway


def test_refresh_release_gate_builds_on_pending_photos(tmp_path: Path, monkeypatch) -> None:
    import time as _time
    from datetime import UTC, datetime

    from ev_pipeline.refresh import runner
    from ev_pipeline.release import build
    from ev_pipeline.release.validate import ReleaseError

    monkeypatch.setattr(runner, "fetch_images", lambda d: {"outcome": "ok", "fetched": 1})
    monkeypatch.setattr(
        build, "build_release", lambda d: (_ for _ in ()).throw(ReleaseError("built"))
    )
    now, t0 = datetime.now(UTC), _time.monotonic()

    monkeypatch.setattr(runner, "photos_pending", lambda d: [])
    out = runner._release(tmp_path, {}, [], [], now, t0)
    assert out["outcome"] == "skipped" and out["reason"] == "no source brought new data"

    monkeypatch.setattr(runner, "photos_pending", lambda d: ["tesla-model-3-gen1"])
    out = runner._release(tmp_path, {}, [], [], now, t0)
    assert out == {"outcome": "failed", "reason": "built"}  # got past the gate to the build


def test_check_release_verifies_stored_image_files(tmp_path: Path, monkeypatch) -> None:
    """#110 review nit: each image file must be stored with the field's sha256 + bytes."""
    monkeypatch.setattr(
        rb, "_schema", lambda: {"$defs": {"Generation": {"properties": {"image": {}}}}}
    )
    cat = _catalogue()
    files, _ = rb.attach_images(cat, _data_dir(tmp_path, jpeg(1000, 500)), TODAY)
    rel = tmp_path / "rel"
    for path, data in files.items():
        (rel / path).parent.mkdir(parents=True, exist_ok=True)
        (rel / path).write_bytes(data)
    assert check_images(cat, rel).status == "pass"  # before packaging: local files

    first = sorted(files)[0]
    (rel / first).write_bytes(b"tampered")
    c = check_images(cat, rel)
    assert c.status == "fail" and any("sha256/bytes differ" in p for p in c.details["problems"])
    (rel / first).unlink()
    c = check_images(cat, rel)
    assert any("missing from the release folder" in p for p in c.details["problems"])

    # Packaged release: the manifest is the record (files may live outside git).
    entries = [
        {"path": p, "bytes": len(d), "sha256": hashlib.sha256(d).hexdigest()}
        for p, d in files.items()
    ]
    (rel / "manifest.json").write_text(json.dumps({"files": entries}))
    assert check_images(cat, rel).status == "pass"
    (rel / "manifest.json").write_text(json.dumps({"files": entries[1:]}))
    c = check_images(cat, rel)
    assert any("not in manifest.json" in p for p in c.details["problems"])


def test_a_dropped_cached_photo_does_not_force_a_release_every_night(
    tmp_path: Path, monkeypatch
) -> None:
    """#134 should-fix: a cached photo that `attach_images` drops (unreadable original, or a
    generation not in the built catalogue) kept `photos_pending` non-empty forever, so the
    refresh published a catalogue-identical release every night. Decide on the built catalogue."""
    import time as _time
    from datetime import UTC, datetime
    from types import SimpleNamespace

    from ev_pipeline.refresh import runner
    from ev_pipeline.release import build

    gid = "tesla-model-3-gen1"
    rel = tmp_path / "releases" / "1"
    rel.mkdir(parents=True)
    (tmp_path / "releases" / "latest").write_text("1\n")
    (rel / "catalogue.json").write_text(json.dumps({"generations": [{"id": gid}]}))

    built: dict[str, Any] = {"generations": [{"id": gid}]}  # build dropped the photo
    res = SimpleNamespace(
        catalogue=built,
        charging_stats=None,
        release=2,
        diff={"previous_release": 1, "counts": {"added": 0, "removed": 0, "changed": 0}},
    )
    monkeypatch.setattr(runner, "fetch_images", lambda d: {"outcome": "ok"})
    monkeypatch.setattr(runner, "photos_pending", lambda d: [gid])  # cached, so "pending"
    monkeypatch.setattr(build, "build_release", lambda d: res)
    now, t0 = datetime.now(UTC), _time.monotonic()

    out = runner._release(tmp_path, {}, [], [], now, t0)
    assert out["outcome"] == "skipped"
    assert out["reason"].startswith("catalogue identical to the previous release")
    assert "1 photo change(s) expected before the build, none built" in out["reason"]

    # the same night with the photo attached by the build does publish
    built["generations"][0]["image"] = {"file_url": "https://upload.wikimedia.org/new.jpg"}
    assert runner.built_photo_changes(tmp_path, built) == [gid]
    monkeypatch.setattr(
        build, "write_release", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("wrote"))
    )
    monkeypatch.setattr(runner, "release_sources_doc", lambda *a: {})
    monkeypatch.setattr(runner, "registry_entries", lambda d: [])
    with pytest.raises(RuntimeError, match="wrote"):
        runner._release(tmp_path, {}, [], [], now, t0)


def test_built_photo_changes_compares_with_the_latest_release(tmp_path: Path) -> None:
    from ev_pipeline.refresh.runner import built_photo_changes

    img = {"file_url": "https://x/a.jpg", "credit": "c", "files": [{"path": "images/a.webp"}]}
    cat = {"generations": [{"id": "a", "image": img}, {"id": "b"}]}
    assert built_photo_changes(tmp_path, cat) == []  # no release yet
    rel = tmp_path / "releases" / "1"
    rel.mkdir(parents=True)
    (tmp_path / "releases" / "latest").write_text("1\n")
    (rel / "catalogue.json").write_text(json.dumps(cat))
    assert built_photo_changes(tmp_path, cat) == []
    swapped = {"generations": [{"id": "a", "image": {"file_url": "https://x/a2.jpg"}}]}
    assert built_photo_changes(tmp_path, swapped) == ["a"]
    assert built_photo_changes(tmp_path, {"generations": [{"id": "a"}]}) == ["a"]  # removed
    recredited = {"generations": [{"id": "a", "image": {**img, "credit": "fixed"}}, {"id": "b"}]}
    assert built_photo_changes(tmp_path, recredited) == ["a"]  # same file, new credit
    refiled = {"generations": [{"id": "a", "image": {**img, "files": []}}, {"id": "b"}]}
    assert built_photo_changes(tmp_path, refiled) == []  # files alone don't count
