#!/bin/sh
# WS3 pre-push data QA: the data-qa steps CI runs (plus the approvals check, G-57, and seed-pinned
# pipeline tests, G-61) (.github/workflows/ci.yml, job data-qa),
# in the same order, so a seed / taxonomy / editorial change is green before it is pushed.
# Retro 2026-11-17 (WS3 3rd chat): two of four validators run by hand, CI caught the third.
#
# Usage (from anywhere in the repo):   sh data/seed/data_qa.sh
# Exit 0 = all steps pass; otherwise the first failing step's exit code. Needs uv (pipeline env).
set -u
root=$(git rev-parse --show-toplevel) || exit 1
cd "$root/pipeline" || exit 1
fail=0
step() {
  name=$1; shift
  printf '== %s\n' "$name"
  if ! "$@"; then
    printf 'FAIL: %s\n' "$name"
    [ "$fail" -eq 0 ] && fail=1
  fi
}
step "validate seed models" uv run python -I ../data/seed/validate_seed.py ../data/seed/models.yaml
step "validate seed variants" uv run python -I ../data/seed/validate_variants.py
step "validate taxonomy, platforms, packs, links" uv run python -I ../data/taxonomy/validate_taxonomy.py
step "back-test shortlist rules (Decision 038)" uv run python -I ../data/editorial/backtest_rules.py
# G-57 / G-54 (T-158): approved_changes.yaml loads like the build reads it; new approvals
# scoped to an already-published release are warned (not a failure here)
step "approved changes load (G-57)" uv run ev release approvals --base origin/main
# G-61 (T-165): pipeline tests that pin committed data/seed state
step "seed-pinned pipeline tests (G-61)" uv run pytest -m seed -q
if [ "$fail" -ne 0 ]; then
  echo "data QA: FAILED (see above)"; exit 1
fi
echo "data QA: all steps pass"
