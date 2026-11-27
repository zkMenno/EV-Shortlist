"""G-65 (T-166): static AST audit ensuring every test reading committed `data/seed/*.yaml`
carries `@pytest.mark.seed` (or module/class `pytestmark`), so seed-pinned tests never skip
`data/seed/data_qa.sh`. Fast fixture test, no network."""

from __future__ import annotations

import ast
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SEED_YAML_SUFFIXES = (".yaml", ".yml")
NON_YAML_EXTENSIONS = (".py", ".sh", ".md", ".txt", ".json", ".csv")
# Helper calls that read committed data/seed/*.yaml when passed repo data/ directly
DATA_DIR_SEED_READERS = frozenset({"load_links"})
# Helper calls that read committed data/seed/*.yaml when passed data/seed/ dir directly
SEED_DIR_READERS = frozenset({"load_hand_kept"})
# File/path constructors where a string literal containing "data/seed" is a real path read
PATH_OPEN_CALLS = frozenset({"Path", "open", "load_seed", "load_manual_variants", "load_hand_kept"})


def _is_seed_mark_expr(node: ast.AST) -> bool:
    """True for `pytest.mark.seed` or `pytest.mark.seed(...)` or `mark.seed`."""
    if isinstance(node, ast.Call):
        node = node.func
    if isinstance(node, ast.Attribute) and node.attr == "seed":
        val = node.value
        if isinstance(val, ast.Attribute) and val.attr == "mark":
            return True
        if isinstance(val, ast.Name) and val.id == "mark":
            return True
    return False


def _has_seed_decorator(decorators: list[ast.expr]) -> bool:
    return any(_is_seed_mark_expr(d) for d in decorators)


def _pytestmark_has_seed(stmts: list[ast.stmt]) -> bool:
    """True when `pytestmark = pytest.mark.seed` or `pytestmark = [..., pytest.mark.seed]`."""
    for stmt in stmts:
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(stmt, ast.Assign):
            targets, value = stmt.targets, stmt.value
        elif isinstance(stmt, ast.AnnAssign):
            targets, value = [stmt.target], stmt.value
        if value is None:
            continue
        if not any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in targets):
            continue
        if _is_seed_mark_expr(value):
            return True
        if isinstance(value, (ast.List, ast.Tuple)) and any(
            _is_seed_mark_expr(elt) for elt in value.elts
        ):
            return True
    return False


def _fixture_name(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    """If `fn` is decorated with `@pytest.fixture`, return its registered fixture name."""
    for dec in fn.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        is_fix = (isinstance(target, ast.Attribute) and target.attr == "fixture") or (
            isinstance(target, ast.Name) and target.id == "fixture"
        )
        if not is_fix:
            continue
        if isinstance(dec, ast.Call):
            for kw in dec.keywords:
                if (
                    kw.arg == "name"
                    and isinstance(kw.value, ast.Constant)
                    and isinstance(kw.value.value, str)
                ):
                    return kw.value.value
        return fn.name
    return None


def _usefixtures_names(decorators: list[ast.expr]) -> set[str]:
    names: set[str] = set()
    for dec in decorators:
        if not isinstance(dec, ast.Call):
            continue
        fn = dec.func
        if isinstance(fn, ast.Attribute) and fn.attr == "usefixtures":
            for arg in dec.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    names.add(arg.value)
    return names


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


_FILE_ROOTED_KINDS = frozenset({"file_path", "repo_root", "repo_data", "seed_dir", "seed_yaml"})


def _is_file_rooted(node: ast.AST, env: dict[str, str]) -> bool:
    """True when `node` originates from `__file__` (directly or via tracked path variables)."""
    if isinstance(node, ast.Name):
        return node.id == "REPO_ROOT" or env.get(node.id) in _FILE_ROOTED_KINDS
    if isinstance(node, ast.Attribute) and node.attr in ("parent", "resolve"):
        return _is_file_rooted(node.value, env)
    if isinstance(node, ast.Subscript):
        val = node.value
        if isinstance(val, ast.Attribute) and val.attr == "parents":
            return _is_file_rooted(val.value, env)
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute) and node.func.attr == "resolve":
            return _is_file_rooted(node.func.value, env)
        if any(isinstance(a, ast.Name) and a.id == "__file__" for a in node.args):
            return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _is_file_rooted(node.left, env)
    return False


def _is_file_parents_expr(node: ast.AST, env: dict[str, str], *, saw_parent: bool = False) -> bool:
    """True for `Path(__file__)[.resolve()].parents[...]`, `Path(__file__).parent.parent...`,
    or `<file-rooted>.parents[...].parent`."""
    if isinstance(node, ast.Attribute) and node.attr == "parent":
        return _is_file_parents_expr(node.value, env, saw_parent=True)
    if isinstance(node, ast.Attribute) and node.attr == "resolve":
        return _is_file_parents_expr(node.value, env, saw_parent=saw_parent)
    if isinstance(node, ast.Subscript):
        val = node.value
        if isinstance(val, ast.Attribute) and val.attr == "parents":
            return _is_file_rooted(val.value, env)
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute) and node.func.attr == "resolve":
            return _is_file_parents_expr(node.func.value, env, saw_parent=saw_parent)
        if saw_parent and any(isinstance(a, ast.Name) and a.id == "__file__" for a in node.args):
            return True
    return False


def _flatten_div_chain(node: ast.AST) -> tuple[ast.AST, list[str | None]] | None:
    """Flatten `base / 'a/b' / 'c'` into `(base, ['a', 'b', 'c'])` (None for dynamic segments)."""
    if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)):
        return None
    parts: list[str | None] = []
    cur: ast.AST = node
    while isinstance(cur, ast.BinOp) and isinstance(cur.op, ast.Div):
        right = cur.right
        if isinstance(right, ast.Constant) and isinstance(right.value, str):
            segs = [p for p in right.value.replace("\\", "/").split("/") if p]
            parts.extend(reversed(segs))
        else:
            parts.append(None)
        cur = cur.left
    parts.reverse()
    return cur, parts


def _is_non_yaml_file(segment: str | None) -> bool:
    return segment is not None and segment.lower().endswith(NON_YAML_EXTENSIONS)


def _classify_expr(node: ast.AST, env: dict[str, str]) -> str | None:
    """Classify an expression as `'file_path'`, `'repo_root'`, `'repo_data'`, `'seed_dir'`,
    `'seed_yaml'`, or `None` given variable classifications in `env`."""
    if isinstance(node, ast.Name):
        if node.id == "REPO_ROOT":
            return "repo_root"
        return env.get(node.id)

    if isinstance(node, ast.Call):
        cname = _call_name(node)
        if cname == "default_data_dir":
            return "repo_data"
        if isinstance(node.func, ast.Attribute) and node.func.attr == "resolve":
            return _classify_expr(node.func.value, env)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "joinpath":
            base_kind = _classify_expr(node.func.value, env)
            segs: list[str | None] = []
            for a in node.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    segs.extend(p for p in a.value.replace("\\", "/").split("/") if p)
                else:
                    segs.append(None)
            return _advance_path(base_kind, segs)
        if cname == "join" and len(node.args) >= 2:
            base_kind = _classify_expr(node.args[0], env)
            if base_kind is not None:
                segs = []
                for a in node.args[1:]:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str):
                        segs.extend(p for p in a.value.replace("\\", "/").split("/") if p)
                    else:
                        segs.append(None)
                return _advance_path(base_kind, segs)
        if cname in PATH_OPEN_CALLS:
            for a in node.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    parts = [p for p in a.value.replace("\\", "/").split("/") if p]
                    if "data" in parts:
                        idx = parts.index("data")
                        res = _advance_path("repo_root", parts[idx:])
                        if res in ("seed_yaml", "seed_dir"):
                            return res
                sub = _classify_expr(a, env)
                if sub in ("seed_yaml", "seed_dir"):
                    return "seed_yaml"
        if cname in DATA_DIR_SEED_READERS and any(
            _classify_expr(a, env) == "repo_data" for a in node.args
        ):
            return "seed_yaml"
        if cname in SEED_DIR_READERS and any(
            _classify_expr(a, env) in ("seed_dir", "seed_yaml") for a in node.args
        ):
            return "seed_yaml"
        # Any call taking a seed_yaml argument (e.g. `SEED = load_seed(REAL_SEED)`)
        if any(_classify_expr(a, env) == "seed_yaml" for a in node.args):
            return "seed_yaml"
        if any(_classify_expr(kw.value, env) == "seed_yaml" for kw in node.keywords):
            return "seed_yaml"
        # Method calls on a seed_yaml Path (e.g. `(REPO / "data" / "seed" / "x.yaml").read_text()`)
        if isinstance(node.func, ast.Attribute):
            recv = _classify_expr(node.func.value, env)
            if recv == "seed_yaml":
                return "seed_yaml"
        if any(isinstance(a, ast.Name) and a.id == "__file__" for a in node.args):
            return "file_path"
        return None

    if _is_file_parents_expr(node, env):
        return "repo_root"

    chain = _flatten_div_chain(node)
    if chain is not None:
        base, parts = chain
        base_kind = _classify_expr(base, env)
        res = _advance_path(base_kind, parts)
        if res is None and base_kind in _FILE_ROOTED_KINDS:
            return "file_path"
        return res

    return None


def _advance_path(base_kind: str | None, parts: list[str | None]) -> str | None:
    if base_kind is None or not parts:
        return base_kind
    kind: str | None = base_kind
    for seg in parts:
        if kind == "repo_root":
            if seg == "data":
                kind = "repo_data"
            else:
                return None
        elif kind == "repo_data":
            if seg == "seed":
                kind = "seed_dir"
            else:
                return None
        elif kind == "seed_dir":
            if _is_non_yaml_file(seg):
                return None
            if seg is None or seg.lower().endswith(SEED_YAML_SUFFIXES):
                kind = "seed_yaml"
            else:
                return None
        else:
            return None
    return kind


def _bind_target(tgt: ast.AST, kind: str, env: dict[str, str]) -> None:
    if isinstance(tgt, ast.Name):
        if tgt.id != "_":
            env[tgt.id] = kind
    elif isinstance(tgt, (ast.Tuple, ast.List)):
        for elt in tgt.elts:
            _bind_target(elt, kind, env)


def _record_assignments(stmts: list[ast.stmt], env: dict[str, str]) -> None:
    """Propagate path/seed variable bindings (including tuple unpacking) across statements."""
    for stmt in stmts:
        if isinstance(stmt, ast.Assign):
            k = _classify_expr(stmt.value, env)
            if k is not None:
                for tgt in stmt.targets:
                    _bind_target(tgt, k, env)
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            k = _classify_expr(stmt.value, env)
            if k is not None:
                _bind_target(stmt.target, k, env)


def _body_reads_seed(fn: ast.FunctionDef | ast.AsyncFunctionDef, mod_env: dict[str, str]) -> bool:
    """True when `fn`'s body directly references committed `data/seed/*.yaml` (or passes
    committed `data/seed` / `data/` into a seed reader)."""
    env = dict(mod_env)
    # Walk statements in order so local aliases like `real = Path(...)/"data"` resolve
    for stmt in fn.body:
        _record_assignments([stmt], env)
        for node in ast.walk(stmt):
            kind = _classify_expr(node, env)
            if kind == "seed_yaml":
                return True
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("glob", "rglob", "iterdir")
                and _classify_expr(node.func.value, env) == "seed_dir"
            ):
                return True
    return False


def _called_names(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                names.add(node.func.attr)
    return names


def find_unmarked_seed_tests(source: str, filename: str = "<string>") -> list[str]:
    """Return `file:lineno: test_name` strings for every test reading committed `data/seed/*.yaml`
    that does not carry `@pytest.mark.seed` (directly, on its class, or via module `pytestmark`)."""
    tree = ast.parse(source, filename=filename)
    if _pytestmark_has_seed(tree.body):
        return []

    mod_env: dict[str, str] = {}
    _record_assignments(tree.body, mod_env)

    # Collect top-level functions (helpers, fixtures, tests) and Test* classes
    funcs: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    fixtures: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs[stmt.name] = stmt
            fx = _fixture_name(stmt)
            if fx is not None:
                fixtures[fx] = stmt

    # Direct seed-reading set across module functions & fixtures
    tainted_funcs: set[str] = {name for name, fn in funcs.items() if _body_reads_seed(fn, mod_env)}
    tainted_fixtures: set[str] = {fx for fx, fn in fixtures.items() if fn.name in tainted_funcs}

    # Fixed-point transitive propagation through helper calls and fixture dependencies
    changed = True
    while changed:
        changed = False
        for name, fn in funcs.items():
            if name in tainted_funcs:
                continue
            params = {a.arg for a in fn.args.args + fn.args.kwonlyargs}
            used_fx = params | _usefixtures_names(fn.decorator_list)
            if (_called_names(fn) & tainted_funcs) or (used_fx & tainted_fixtures):
                tainted_funcs.add(name)
                fx = _fixture_name(fn)
                if fx is not None:
                    tainted_fixtures.add(fx)
                changed = True

    violations: list[str] = []

    # Top-level test_* functions
    for name, fn in funcs.items():
        if not name.startswith("test_"):
            continue
        if name in tainted_funcs and not _has_seed_decorator(fn.decorator_list):
            violations.append(f"{filename}:{fn.lineno}: {name}")

    # Methods inside Test* classes
    for stmt in tree.body:
        if not (isinstance(stmt, ast.ClassDef) and stmt.name.startswith("Test")):
            continue
        class_marked = _has_seed_decorator(stmt.decorator_list) or _pytestmark_has_seed(stmt.body)
        if class_marked:
            continue
        class_usefx = _usefixtures_names(stmt.decorator_list)
        cls_methods: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {
            m.name: m for m in stmt.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        cls_tainted: set[str] = {
            mname for mname, m in cls_methods.items() if _body_reads_seed(m, mod_env)
        }
        c_changed = True
        while c_changed:
            c_changed = False
            for mname, m in cls_methods.items():
                if mname in cls_tainted:
                    continue
                params = {a.arg for a in m.args.args + m.args.kwonlyargs}
                used_fx = params | _usefixtures_names(m.decorator_list) | class_usefx
                called = _called_names(m)
                if (called & (tainted_funcs | cls_tainted)) or (used_fx & tainted_fixtures):
                    cls_tainted.add(mname)
                    c_changed = True
        for mname, m in cls_methods.items():
            if not mname.startswith("test_"):
                continue
            if mname in cls_tainted and not _has_seed_decorator(m.decorator_list):
                violations.append(f"{filename}:{m.lineno}: {stmt.name}.{mname}")

    return violations


# --- audit of all real test files ------------------------------------------------------------


def test_all_committed_seed_tests_carry_seed_marker() -> None:
    """G-65: every `pipeline/tests/test_*.py` reading committed `data/seed/*.yaml` carries
    `@pytest.mark.seed` (or module/class `pytestmark`), so `data/seed/data_qa.sh` runs it."""
    violations: list[str] = []
    for path in sorted(TESTS_DIR.glob("test_*.py")):
        if path.name == Path(__file__).name:
            continue
        violations.extend(find_unmarked_seed_tests(path.read_text(encoding="utf-8"), path.name))
    assert violations == [], (
        "Tests reading committed data/seed/*.yaml without @pytest.mark.seed (G-61/G-65):\n"
        + "\n".join(f"  - {v}" for v in violations)
    )


# --- synthetic unit tests proving the scanner catches unmarked cases -------------------------


def test_audit_catches_unmarked_direct_seed_read() -> None:
    src = """
from pathlib import Path
from ev_pipeline.match.seed import load_seed

REPO = Path(__file__).resolve().parents[2]

def test_unmarked_direct():
    s = load_seed(REPO / "data" / "seed" / "models.yaml")
    assert s
"""
    assert find_unmarked_seed_tests(src, "synthetic.py") == ["synthetic.py:7: test_unmarked_direct"]


def test_audit_catches_module_constant_and_fixture_like_scoped_aliases() -> None:
    """Regression for T-165 retro (G-65): module-level `REAL_SEED` read inside a fixture
    used by an unmarked test must be caught, while marked tests pass."""
    src = """
from pathlib import Path
import pytest
from ev_pipeline.match.seed import load_seed

REAL_SEED = Path(__file__).parents[2] / "data" / "seed" / "models.yaml"

@pytest.fixture(scope="module")
def real():
    return load_seed(REAL_SEED)

def test_forgot_marker(real):
    assert real

@pytest.mark.seed
def test_has_marker(real):
    assert real
"""
    assert find_unmarked_seed_tests(src, "test_fake_aliases.py") == [
        "test_fake_aliases.py:12: test_forgot_marker"
    ]


def test_audit_catches_helper_and_load_links_and_class_methods() -> None:
    src = """
from pathlib import Path
import pytest
from ev_pipeline.derive.links import load_links

REPO_DATA = Path(__file__).resolve().parents[2] / "data"

def _helper():
    return (REPO_DATA / "seed" / "variants.yaml").read_text()

def test_via_helper():
    assert _helper()

def test_via_load_links():
    assert load_links(REPO_DATA)

class TestUnmarked:
    def test_method(self):
        assert _helper()

@pytest.mark.seed
class TestMarked:
    def test_ok(self):
        assert _helper()
"""
    assert find_unmarked_seed_tests(src, "test_helpers.py") == [
        "test_helpers.py:11: test_via_helper",
        "test_helpers.py:14: test_via_load_links",
        "test_helpers.py:18: TestUnmarked.test_method",
    ]


def test_audit_accepts_module_pytestmark_and_ignores_fixtures_and_scripts() -> None:
    marked_module = """
from pathlib import Path
import pytest
from ev_pipeline.match.seed import load_seed

pytestmark = pytest.mark.seed
SEED = load_seed(Path(__file__).resolve().parents[2] / "data" / "seed" / "models.yaml")

def test_uses_module_seed():
    assert SEED
"""
    assert find_unmarked_seed_tests(marked_module, "marked.py") == []

    non_seed = """
from pathlib import Path
import importlib.util

REPO = Path(__file__).resolve().parents[2]
FIX = Path(__file__).parent / "fixtures" / "release"

def test_uses_tmp_and_fixtures_and_scripts(tmp_path):
    (tmp_path / "seed").mkdir()
    (tmp_path / "seed" / "models.yaml").write_text("makes: []")
    assert (FIX / "models.yaml").exists()
    assert (REPO / "data" / "seed" / "validate_variants.py").exists()
    assert (REPO / "data" / "seed" / "data_qa.sh").read_text()
    assert "from data/seed/variant_links.yaml" in "from data/seed/variant_links.yaml"
"""
    assert find_unmarked_seed_tests(non_seed, "non_seed.py") == []


def test_audit_catches_stripped_real_scoped_aliases() -> None:
    """In-memory regression on the real `test_scoped_aliases.py` (T-165 retro): stripping its
    `@pytest.mark.seed` decorators must flag all three real-seed tests."""
    src = (TESTS_DIR / "test_scoped_aliases.py").read_text(encoding="utf-8")
    stripped = "\n".join(ln for ln in src.splitlines() if ln.strip() != "@pytest.mark.seed")
    caught = find_unmarked_seed_tests(stripped, "test_scoped_aliases.py")
    names = {entry.rsplit(": ", 1)[1] for entry in caught}
    assert names == {
        "test_real_seed_migration_is_complete",
        "test_real_seed_scoped",
        "test_real_seed_make_aliases",
    }


def test_audit_handles_multisegment_div_tuple_unpacking_and_tmp_parents() -> None:
    """PR #221 review fixes: multi-segment string literals in `/` chains, module-level tuple
    unpacking (`MANUAL, _ = load_manual_variants(...)`), `__file__`-derived `FIX.parents[...]`,
    and ignoring `tmp_path.parents[0]`."""
    src = """
from pathlib import Path
from ev_pipeline.match.seed import load_manual_variants, load_seed

REPO = Path(__file__).resolve().parents[2]
FIX = Path(__file__).parent / "fixtures" / "release"
MANUAL, _ = load_manual_variants(REPO / "data" / "seed" / "variants.yaml")

def test_multisegment_single_literal():
    assert load_seed(REPO / "data/seed/models.yaml")

def test_multisegment_split_literal():
    assert load_seed(REPO / "data/seed" / "models.yaml")

def test_tuple_unpacked_module_global():
    assert MANUAL

def test_fix_parents_chain():
    assert load_seed(FIX.parents[2].parent / "data" / "seed" / "models.yaml")

def test_tmp_path_parents_is_ignored(tmp_path):
    p = tmp_path.parents[0] / "data" / "seed" / "models.yaml"
    assert p
"""
    caught = find_unmarked_seed_tests(src, "test_edges.py")
    names = [entry.rsplit(": ", 1)[1] for entry in caught]
    assert names == [
        "test_multisegment_single_literal",
        "test_multisegment_split_literal",
        "test_tuple_unpacked_module_global",
        "test_fix_parents_chain",
    ]
