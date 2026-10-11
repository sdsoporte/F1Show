## What this changes

<!-- One or two sentences. What behaviour or artifact changes, and for whom. -->

## The claim this PR makes, and where it was measured

<!--
Every claim in this description names where it was measured. "Tests pass" is not a measurement;
"`uv run --frozen pytest -q` -> 761 passed" is. Hash-based claims state the hash function.
If a number came from a summary rather than from the artifact, say so.
-->

## Checks run

- [ ] `uv run --frozen pytest -q` — the full offline suite, with the observed count pasted above
      (the suite uses recorded fixtures, fake providers and an injected clock; no credential or
      live endpoint is involved)
- [ ] Lint, with the repository's committed selection and the pinned version:
      `uvx ruff@0.17.0 check --no-cache src tests` → `0 findings` expected; if it reports
      findings, they are either fixed here or registered in `docs/CARRIED-FINDINGS.md` with an
      owner and a trigger
- [ ] Native review under RDD — the review switch's own status, and the exact acknowledgement if
      it approved. An approval covers only the bytes it covered: if the candidate changed after
      it, this box is unchecked
- [ ] The Python floor still runs, when the change could touch it:
      `uv run --frozen --python 3.12 pytest -q`

## Failed, skipped and pending checks

<!--
List them. A check that did not run is not a check that passed, and "not applicable" is a
conclusion that needs its reason written down.
-->

## Out of scope

<!--
What a reader might expect here and will not find, and where it is tracked instead. Explicit
non-goals keep a review focused on the change that exists.
-->
